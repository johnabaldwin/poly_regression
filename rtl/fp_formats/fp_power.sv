module fp_power
    import fpnew_pkg::*;
#(
    parameter fp_format_e FP_FORMAT,
    localparam int unsigned WIDTH = fp_width(FP_FORMAT),
    parameter int unsigned FMA_LATENCY = 2,
    parameter int unsigned MAX_DEGREE = 10,
    localparam int unsigned DEG_WIDTH = $clog2(MAX_DEGREE) + 1
) (
    input logic clk,
    input logic rst,
    input logic in_valid, // start computing powers,
    input logic [WIDTH-1:0] x_value, // exponent base
    input logic [DEG_WIDTH-1:0] degree, // compute up to this exponent
    output logic in_ready, // ready for new input
    output logic out_valid, // new power ready
    output logic [DEG_WIDTH-1:0] out_power_idx, // which power
    output logic [WIDTH-1:0] out_result,
    output logic done,
    output status_t fma_status
);

    // Floating point constants
    function automatic logic [WIDTH-1:0] fp_one();
        case (FP_FORMAT)
            FP32:    return 32'h3F800000;
            FP64:    return 64'h3FF0000000000000;
            FP16:    return 16'h3C00;
            FP16ALT: return 16'h3F80;
            FP8:     return 8'h38;
            default: return '0;
        endcase
    endfunction

    function automatic logic [WIDTH-1:0] fp_zero();
        return '0;
    endfunction

    // =========================================================================
    // State Machine
    // =========================================================================

    typedef enum logic [2:0] {
        IDLE          = 3'b000,  // Waiting for input
        OUTPUT_X0     = 3'b001,  // Output x^0 = 1
        OUTPUT_X1     = 3'b010,  // Output x^1 = x
        MULTIPLY      = 3'b011,  // Start multiplication: x^k = x^(k-1) × x
        WAIT_MULT     = 3'b100,  // Wait for FMA to complete
        OUTPUT_POWER  = 3'b101,  // Output newly computed power
        DONE_STATE    = 3'b110,   // All powers computed
        XXX = 'x
    } state_t;

    state_t cur_state, next_state;

    logic ready;

    logic [WIDTH-1:0] x_value_r;
    logic [WIDTH-1:0] cur_x_pow, next_x_pow;
    logic [DEG_WIDTH-1:0] degree_r;
    logic [DEG_WIDTH-1:0] cur_degree, next_degree;

    // Wait counter for FMA latency
    logic [$clog2(FMA_LATENCY+1)-1:0] wait_cnt, wait_cnt_next;


    // FMA inputs and control values

    logic [WIDTH-1:0] fma_op_a;
    logic [WIDTH-1:0] fma_op_b;
    logic fma_in_vld;
    logic [WIDTH-1:0] fma_res;
    logic fma_out_vld;

    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            cur_state <= IDLE;
            x_value_r <= '0;
            degree_r <= '0;
            cur_degree <= '0;
        end else begin
            cur_state <= next_state;
            cur_degree <= next_degree;
            wait_cnt <= wait_cnt_next;
            cur_x_pow <= next_x_pow;
            if (in_valid && ready) begin
                x_value_r <= x_value;
                degree_r <= degree;
            end
        end
    end

    always_comb begin
        case(cur_state)
            IDLE: begin
                if (in_valid && ready) begin
                    next_state = OUTPUT_X0;
                end else begin
                    next_state = IDLE;
                end
            end

            OUTPUT_X0: begin
                if (degree_r == '0) begin
                    next_state = DONE_STATE;
                end else begin
                    next_state = OUTPUT_X1;
                end
            end

            OUTPUT_X1: begin
                if (degree_r == 1) begin
                    next_state = DONE_STATE;
                end else begin
                    next_state = MULTIPLY;
                end
            end

            MULTIPLY: begin
                if (FMA_LATENCY == 0) begin
                    next_state = OUTPUT_POWER;
                end else begin
                    next_state = WAIT_MULT;
                end
            end

            WAIT_MULT: begin
                if (wait_cnt == FMA_LATENCY) begin
                    next_state = OUTPUT_POWER;
                end else begin
                    next_state = WAIT_MULT;
                end
            end

            OUTPUT_POWER: begin
                if (cur_degree >= degree_r) begin
                    next_state = DONE_STATE;
                end else begin
                    next_state = MULTIPLY;
                end
            end

            DONE_STATE: begin
                if (in_valid && ready) begin
                    next_state = OUTPUT_X0;
                end else begin
                    next_state = DONE_STATE;
                end
            end

            default: begin
                next_state = IDLE;
            end
        endcase
    end

    always_comb begin

        next_x_pow = cur_x_pow;
        next_degree = cur_degree;
        wait_cnt_next = wait_cnt;

        fma_op_a = fp_zero();
        fma_op_b = fp_zero();
        fma_in_vld = 1'b0;

        ready = 1'b0;
        out_valid = 1'b0;
        out_power_idx = cur_degree;
        out_result = '0;
        done = 1'b0;

        case (cur_state)
            IDLE: begin
                ready = 1'b1;

                if (in_valid) begin
                    next_x_pow = x_value;
                    next_degree = '0;
                    wait_cnt_next = '0;
                end
            end

            OUTPUT_X0: begin
                out_valid = 1'b1;
                out_power_idx = cur_degree;
                out_result = fp_one();

                next_degree = 1;
            end

            OUTPUT_X1: begin
                out_valid = 1'b1;
                out_power_idx = cur_degree;
                out_result = cur_x_pow;

                next_degree = 2;
            end

            MULTIPLY: begin
                fma_op_a = cur_x_pow;
                fma_op_b = x_value_r;
                fma_in_vld = 1'b1;

                wait_cnt_next = '0;
            end

            WAIT_MULT: begin
                wait_cnt_next = wait_cnt + 1'b1;
                if (wait_cnt == FMA_LATENCY) begin
                    next_x_pow = fma_res;
                end
            end

            OUTPUT_POWER: begin
                out_valid = 1'b1;
                out_power_idx = cur_degree;
                out_result = cur_x_pow;
                next_degree = cur_degree + 1'b1;
            end

            DONE_STATE: begin
                done = 1'b1;
                ready = 1'b1;

                if (in_valid) begin
                    next_x_pow = x_value;
                    next_degree = '0;
                    wait_cnt_next = '0;
                end
            end

            default: begin
                next_degree = '0;
                wait_cnt_next = '0;
            end
        endcase
    end
    assign in_ready = ready;

    fp_madd #(
        .FP_FORMAT(FP_FORMAT),
        .MODE(fpnew_pkg::MUL)
    ) power (
        .clk,
        .rst,
        .vld(fma_in_vld),
        .sub(1'b0),
        .a(fma_op_a),
        .b(fma_op_b),
        .c(fp_zero()),
        .res(fma_res),
        .rdy(fma_out_vld),
        .fma_status(fma_status)
    );

endmodule
