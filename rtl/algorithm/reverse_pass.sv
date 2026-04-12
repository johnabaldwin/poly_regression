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
    output logic [DEG_WIDTH-1:0] coef_addr
);

    logic [WIDTH-1:0] x_pow;
    logic [WIDTH-1:0] accumulate;
    logic [WIDTH-1:0] error_accum;

    logic pow_done;
    logic error_accum_rdy;

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
        .out_valid(),
        .out_power_idx(),
        .out_result(x_pow),
        .fma_status(),
        .done(pow_done)
    );
    assign rev_pow_done = pow_done;

    fp_madd #(
        .FP_FORMAT  (FP_FORMAT),
        .MODE       (fpnew_pkg::FNMSUB),
        .FMA_LATENCY(FMA_LATENCY)
    ) error_accumulator (
        .clk       (clk),
        .rst       (rst),
        .vld       (pow_done),
        .sub       ('0),
        .a         (x_pow),
        .b         (error),
        .c         (accumulate),
        .res       (error_accum),
        .rdy       (error_accum_rdy),
        .fma_status()
    );

    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            accumulate <= '0;
        end else begin
            if (error_accum_rdy) begin
                accumulate <= error_accum;
            end else if (rev_accum_rst) begin
                accumulate <= '0;
            end
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
    assign coef_addr = k;

endmodule
