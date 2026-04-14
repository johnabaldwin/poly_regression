module control #(
    parameter int NUM_SAMPLES,
    localparam int D_ADDR_WIDTH = $clog2(NUM_SAMPLES),
    parameter int MAX_ITERATIONS,
    parameter int MAX_DEGREE,
    localparam int DEG_WIDTH = $clog2(MAX_DEGREE) + 1
) (
    input logic clk,
    input logic rst,
    input logic go,
    input logic fwd_pow_done,
    input logic rev_pow_done,
    output logic data_rd_en,
    output logic [D_ADDR_WIDTH-1:0] data_rd_addr,
    output logic fwd_data_valid,
    output logic rev_data_valid,
    output logic done,
    output logic [DEG_WIDTH-1:0] k,
    output logic rev_accum_rst
);

    logic [$clog2(NUM_SAMPLES)-1:0] cur_data_addr, next_data_addr;
    logic [$clog2(MAX_ITERATIONS)-1:0] cur_pass, next_pass;
    logic [DEG_WIDTH-1:0] cur_k, next_k;

    typedef enum logic[3:0] {
        INIT = '0,
        ERR = 4'b0001,
        // FORWARD_PASS_READ,
        FORWARD_PASS_START = 4'b0010,
        FORWARD_PASS_WAIT = 4'b0011,
        REVERSE_PASS_LOOP = 4'b0100,
        REVERSE_PASS_POW = 4'b0101,
        REVERSE_PASS_WAIT = 4'b0110,
        LOOP_BACK = 4'b0111,
        FINISH = 4'b1000,
        XXX = 'X
    } state_t;

    state_t cur_state, next_state;

    always_ff @(posedge clk or posedge rst) begin
        if (rst)
            cur_state <= INIT;
        else begin
            cur_state <= next_state;
            cur_data_addr <= next_data_addr;
            cur_pass <= next_pass;
            cur_k <= next_k;
        end
    end
    assign data_rd_addr = cur_data_addr;
    assign k = cur_k;

    always_comb begin
        done = 1'b0;
        fwd_data_valid = 1'b0;
        rev_data_valid = 1'b0;
        next_data_addr = cur_data_addr;
        next_k = cur_k;
        next_pass = cur_pass;
        rev_accum_rst = '0;
        data_rd_en = 1'b0;

        case (cur_state)

            INIT: begin
                next_data_addr = '0;
                next_pass = '0;
                next_k = '0;
                if (go) begin
                    data_rd_en = 1'b1;
                    next_state = FORWARD_PASS_START;
                end else
                    next_state = INIT;
            end

            FORWARD_PASS_START: begin
                next_data_addr = cur_data_addr + 1'b1;
                fwd_data_valid = 1'b1;
                next_state = FORWARD_PASS_WAIT;
            end

            FORWARD_PASS_WAIT: begin
                if (cur_data_addr == NUM_SAMPLES) begin
                    next_data_addr = '0;
                    next_state = REVERSE_PASS_LOOP;
                end else if (fwd_pow_done) begin
                    data_rd_en = 1'b1;
                    next_state = FORWARD_PASS_START;
                end else
                    next_state = FORWARD_PASS_WAIT;
            end

            REVERSE_PASS_LOOP: begin
                if (cur_k == (MAX_DEGREE + 1)) begin
                    data_rd_en = 1'b1;
                    next_state = LOOP_BACK;
                end else begin
                    data_rd_en = 1'b1;
                    next_state = REVERSE_PASS_POW;
                end
            end

            REVERSE_PASS_POW: begin
                rev_data_valid = 1'b1;
                next_data_addr = cur_data_addr + 1'b1;
                next_state = REVERSE_PASS_WAIT;
            end

            REVERSE_PASS_WAIT: begin
                if (cur_data_addr == NUM_SAMPLES) begin
                    next_data_addr = '0;
                    rev_accum_rst = 1'b1; //TODO: timing of this signal?
                    next_k = cur_k + 1'b1;
                    next_state = REVERSE_PASS_LOOP;
                end else if (rev_pow_done) begin
                    data_rd_en = 1'b1;
                    next_state = REVERSE_PASS_POW;
                end else begin
                    next_state = REVERSE_PASS_WAIT;
                end
            end

            LOOP_BACK: begin
                next_pass = cur_pass + 1'b1;
                next_k = '0;
                if (cur_pass == MAX_ITERATIONS)
                    next_state = FINISH;
                else begin
                    next_state = FORWARD_PASS_START;
                end
            end

            FINISH: begin
                done = 1'b1;
                if (go)
                    next_state = INIT;
                else
                    next_state = FINISH;
            end

            ERR: begin
                next_state = ERR;
            end

            default:
                next_state = ERR;

        endcase
    end

endmodule
