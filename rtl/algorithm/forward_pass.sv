module forward_pass
    import fpnew_pkg::*;
#(
    parameter fp_format_e FP_FORMAT = FP32,
    parameter int FMA_LATENCY = 2,
    parameter int WIDTH,
    parameter int MAX_DEGREE = 3,
    localparam int DEG_WIDTH = $clog2(MAX_DEGREE) + 1,
    localparam int FORWARD_LATENCY = FMA_LATENCY*MAX_DEGREE + FMA_LATENCY + 1,
    parameter int NUM_SAMPLES = 100,
    localparam int ADDR_WIDTH = $clog2(NUM_SAMPLES)
) (
    input logic clk,
    input logic rst,
    input logic valid,
    input logic [WIDTH-1:0] x_value,
    input logic [WIDTH-1:0] y_value,
    input logic [WIDTH-1:0] coef_value,
    input logic [ADDR_WIDTH-1:0] data_rd_addr,
    output logic [DEG_WIDTH-1:0] coef_idx,
    output logic [WIDTH-1:0] x_pow_out,
    output logic [WIDTH-1:0] error,
    output logic [WIDTH-1:0] loss,
    output logic [ADDR_WIDTH-1:0] error_wr_addr,
    output logic fwd_pow_done,
    output logic coef_rd,
    output logic error_rdy,
    output logic exp_in_rdy

);

    logic exp_out_valid;
    logic exp_valid_r;
    logic [WIDTH-1:0] x_pow_r;
    logic coef_madd_rdy;

    logic [WIDTH-1:0] y_actual;

    logic [WIDTH-1:0] x_pow;
    logic [WIDTH-1:0] coef_madd;
    logic [WIDTH-1:0] accumulate;

    logic pow_done;
    logic pow_done_dlyd;
    logic error_en;

    register #(
        .WIDTH(WIDTH),
        .N_STAGES(FORWARD_LATENCY)
    ) y_delay (
        .clk,
        .rst,
        .en(valid),
        .in(y_value),
        .out(y_actual)
    );

    register #(
        .WIDTH      (ADDR_WIDTH),
        .N_STAGES   (FORWARD_LATENCY)
    ) addr_delay (
        .clk(clk),
        .rst(rst),
        .en (valid),
        .in (data_rd_addr),
        .out(error_wr_addr)
    );

    fp_power #(
        .FP_FORMAT(FP_FORMAT),
        .MAX_DEGREE(MAX_DEGREE)
    ) exponentiator (
        .clk,
        .rst,
        .in_valid(valid),
        .x_value,
        .degree(MAX_DEGREE),
        .in_ready(exp_in_rdy),
        .out_valid(exp_out_valid),
        .out_power_idx(coef_idx),
        .out_result(x_pow),
        .fma_status(),
        .done(pow_done)
    );
    assign fwd_pow_done = pow_done;
    assign coef_rd = exp_out_valid;

    // Delay pow_done by FMA_LATENCY for accumulate reset (Bug 1 fix)
    register #(
        .WIDTH(1),
        .N_STAGES(FMA_LATENCY)
    ) pow_done_delay (
        .clk,
        .rst,
        .en(1'b1),
        .in(pow_done),
        .out(pow_done_dlyd)
    );

    // 1-cycle delay on exp_out_valid and x_pow so coef RAM data is ready (Bug 2 fix)
    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            exp_valid_r <= 1'b0;
            x_pow_r     <= '0;
        end else begin
            exp_valid_r <= exp_out_valid;
            x_pow_r     <= x_pow;
        end
    end

    // FMA_LATENCY+1 cycles after last pow: +1 because accumulate FMA now fires 1 cycle later
    register #(
        .WIDTH(1),
        .N_STAGES(FMA_LATENCY + 1)
    ) error_ready (
        .clk,
        .rst,
        .en(1'b1),
        .in(pow_done),
        .out(error_en)
    );

    fp_madd #(
        .FP_FORMAT(FP_FORMAT),
        .MODE(fpnew_pkg::FMADD),
        .FMA_LATENCY(FMA_LATENCY)
    ) accumulate_coefficients (
        .clk,
        .rst,
        .vld(exp_valid_r),
        .sub(1'b0),
        .a(x_pow_r),
        .b(coef_value),
        .c(accumulate),
        .res(coef_madd),
        .rdy(coef_madd_rdy),
        .fma_status()
    );

    fp_madd #(
        .FP_FORMAT(FP_FORMAT),
        .MODE(fpnew_pkg::ADD)
    ) error_calc (
        .clk,
        .rst,
        .vld(error_en),
        .sub(1'b1),
        .a('0),
        .b(coef_madd),
        .c(y_actual),
        .res(error),
        .rdy(error_rdy),
        .fma_status()
    );

    /*TODO: Total error and squared error calculations would be useful,
    *       but will consume more resources and are not used in the backward
    *       pass only in reports and convergence checks.
    */

    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            accumulate <= '0;
        end else begin
            if (pow_done_dlyd) begin
                // Reset fires at pow_done+FMA_LATENCY, same cycle as the last
                // coef_madd_rdy — priority here discards the contaminating result
                accumulate <= '0;
            end else if (coef_madd_rdy) begin
                accumulate <= coef_madd;
            end
        end
    end

endmodule
