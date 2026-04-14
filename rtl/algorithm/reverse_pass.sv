module reverse_pass
    import fpnew_pkg::*;
#(
    parameter fp_format_e FP_FORMAT = FP32,
    parameter int FMA_LATENCY = 2,
    localparam int WIDTH = fp_width(FP_FORMAT),
    parameter int MAX_DEGREE = 3,
    localparam int DEG_WIDTH = $clog2(MAX_DEGREE) + 1,
    parameter int SAMPLES
) (
    input logic clk,
    input logic rst,
    input logic start,
    input logic rev_accum_rst,
    input logic [DEG_WIDTH-1:0] k,
    input logic [WIDTH-1:0] x_value,
    input logic [WIDTH-1:0] error,
    input logic [WIDTH-1:0] cur_coef,
    input logic [WIDTH-1:0] alpha,
    output logic [WIDTH-1:0] updated_coef,
    output logic new_coef_rdy,
    output logic rev_pow_done,
    output logic [DEG_WIDTH-1:0] coef_wr_addr
);

    logic [WIDTH-1:0] x_pow;
    logic [WIDTH-1:0] x_pow_last;
    logic [WIDTH-1:0] accumulate;
    logic [WIDTH-1:0] error_accum;
    logic [DEG_WIDTH-1:0] dly_k;
    logic [DEG_WIDTH-1:0] wr_k;

    logic pow_done;
    logic pow_out_valid;
    logic error_accum_rdy;
    logic rev_accum_rst_d;

    fp_power #(
        .FP_FORMAT(FP_FORMAT),
        .MAX_DEGREE(MAX_DEGREE)
    ) exponentiator (
        .clk,
        .rst,
        .in_valid(start),
        .x_value,
        .degree(k),
        .in_ready(),
        .out_valid(pow_out_valid),
        .out_power_idx(),
        .out_result(x_pow),
        .fma_status(),
        .done(pow_done)
    );
    assign rev_pow_done = pow_done;

    // Latch x_pow while it is valid; out_result='0 in DONE_STATE when pow_done fires
    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            x_pow_last <= '0;
        end else if (pow_out_valid) begin
            x_pow_last <= x_pow;
        end
    end

    fp_madd #(
        .FP_FORMAT  (FP_FORMAT),
        .MODE       (fpnew_pkg::FNMSUB),
        .FMA_LATENCY(FMA_LATENCY)
    ) error_accumulator (
        .clk       (clk),
        .rst       (rst),
        .vld       (pow_done),
        .sub       ('0),
        .a         (x_pow_last),
        .b         (error),
        .c         (accumulate),
        .res       (error_accum),
        .rdy       (error_accum_rdy),
        .fma_status()
    );

    // Delay rev_accum_rst by 1 cycle for the accumulate reset only.
    // At the k boundary, error_accum_rdy and rev_accum_rst fire simultaneously;
    // the delayed version fires 1 cycle later when error_accum_rdy is already gone,
    // so the reset wins cleanly without discarding the final gradient.
    always_ff @(posedge clk or posedge rst) begin
        if (rst) rev_accum_rst_d <= 1'b0;
        else     rev_accum_rst_d <= rev_accum_rst;
    end

    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            accumulate <= '0;
        end else begin
            if (error_accum_rdy) begin
                accumulate <= error_accum;
            end else if (rev_accum_rst_d) begin
                accumulate <= '0;
            end
            // Delay k an extra two cycles to use as the address
            dly_k <= k;
            wr_k <= dly_k;
        end
    end

    fp_madd #(
        .FP_FORMAT  (FP_FORMAT),
        .MODE       (fpnew_pkg::FNMSUB),
        .FMA_LATENCY(FMA_LATENCY)
    ) coefficient_update (
        .clk       (clk),
        .rst       (rst),
        .vld       (rev_accum_rst), // TODO how to tell when done processing errors
        .sub       ('0),
        .a         (alpha),
        .b         (error_accum),
        .c         (cur_coef),
        .res       (updated_coef),
        .rdy       (new_coef_rdy),
        .fma_status()
    );
    assign coef_wr_addr = wr_k;

endmodule
