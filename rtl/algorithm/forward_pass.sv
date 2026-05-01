module forward_pass
    import fpnew_pkg::*;
#(
    parameter fp_format_e FP_FORMAT = FP32,
    parameter int FMA_LATENCY = 2,
    parameter int WIDTH,
    parameter int MAX_DEGREE = 3,
    localparam int DEG_WIDTH = $clog2(MAX_DEGREE) + 1,
    // fp_power state machine: 1(IDLE)+1(X0)+1(X1)+(MAX_DEGREE-1)*(1+FMA_LATENCY+1+1)+1(DONE)
    // = 3 + (MAX_DEGREE-1)*(FMA_LATENCY+3) clocks from valid to pow_done
    // error_en  fires pow_done + FMA_LATENCY+1 later  (error_ready has FMA_LATENCY+1 stages)
    // error_rdy fires error_en + FMA_LATENCY  later
    localparam int POW_DONE_LAT   = 3 + (MAX_DEGREE-1)*(FMA_LATENCY+3),
    localparam int Y_DELAY_STAGES = POW_DONE_LAT + FMA_LATENCY + 1,
    localparam int ADDR_DELAY_STAGES = Y_DELAY_STAGES + FMA_LATENCY,
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
    logic exp_valid_r;        // 1-cycle delayed: coef RAM data now valid (Bug 2 fix)
    logic [WIDTH-1:0] x_pow_r;
    logic [DEG_WIDTH-1:0] coef_idx_r; // 1-cycle delayed coef_idx, matches exp_valid_r
    logic coef_madd_rdy;

    logic [WIDTH-1:0] y_actual;

    logic [WIDTH-1:0] x_pow;
    logic [WIDTH-1:0] coef_madd;
    logic [WIDTH-1:0] accumulate;

    logic pow_done;
    logic pow_done_dlyd;
    logic error_en;

    // ── fp_power ──────────────────────────────────────────────────────────────
    fp_power #(
        .FP_FORMAT(FP_FORMAT),
        .MAX_DEGREE(MAX_DEGREE)
    ) exponentiator (
        .clk,
        .rst,
        .in_valid(valid),
        .x_value,
        .degree(DEG_WIDTH'(MAX_DEGREE)),
        .in_ready(exp_in_rdy),
        .out_valid(exp_out_valid),
        .out_power_idx(coef_idx),
        .out_result(x_pow),
        .fma_status(),
        .done(pow_done)
    );
    assign fwd_pow_done = pow_done;
    // coef_rd starts the RAM read; coef_value is valid 1 cycle later (at exp_valid_r)
    assign coef_rd = exp_out_valid;

    // ── 1-cycle delay for Bug 2: align FMA inputs with coef RAM output ────────
    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            exp_valid_r  <= 1'b0;
            x_pow_r      <= '0;
            coef_idx_r   <= '0;
        end else begin
            exp_valid_r <= exp_out_valid;
            x_pow_r     <= x_pow;
            coef_idx_r  <= coef_idx;
        end
    end

    // ── Delay pow_done by FMA_LATENCY for accumulate reset (Bug 1 fix) ────────
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

    // ── Y alignment: fixed clock-cycle delay (not sample-gated) ──────────────
    // Needs Y_DELAY_STAGES clock cycles to align y_actual with error_en firing.
    register #(
        .WIDTH(WIDTH),
        .N_STAGES(Y_DELAY_STAGES)
    ) y_delay (
        .clk,
        .rst,
        .en(1'b1),
        .in(y_value),
        .out(y_actual)
    );

    // ── Address alignment: align error_wr_addr with error_rdy ─────────────────
    register #(
        .WIDTH(ADDR_WIDTH),
        .N_STAGES(ADDR_DELAY_STAGES)
    ) addr_delay (
        .clk,
        .rst,
        .en(1'b1),
        .in(data_rd_addr),
        .out(error_wr_addr)
    );

    // ── FMA: error_en fires FMA_LATENCY+1 cycles after pow_done ──────────────
    // (+1 because accumulate_coefficients FMA now fires 1 cycle later)
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

    // ── Polynomial accumulation FMA ────────────────────────────────────────────
    // Fires for x^1 and above (x^0 is handled directly in the always_ff below).
    fp_madd #(
        .FP_FORMAT(FP_FORMAT),
        .MODE(fpnew_pkg::FMADD),
        .FMA_LATENCY(FMA_LATENCY)
    ) accumulate_coefficients (
        .clk,
        .rst,
        .vld(exp_valid_r && (coef_idx_r != '0)),
        .sub(1'b0),
        .a(x_pow_r),
        .b(coef_value),
        .c(accumulate),
        .res(coef_madd),
        .rdy(coef_madd_rdy),
        .fma_status()
    );

    // ── Error calculation ──────────────────────────────────────────────────────
    fp_madd #(
        .FP_FORMAT(FP_FORMAT),
        .MODE(fpnew_pkg::ADD)
    ) error_calc (
        .clk,
        .rst,
        .vld(error_en),
        .sub(1'b1),
        .a('0),
        .b(y_actual),   // sub=1 → b-c = y_actual - coef_madd = y - y_hat
        .c(coef_madd),
        .res(error),
        .rdy(error_rdy),
        .fma_status()
    );

    // ── Accumulate register ────────────────────────────────────────────────────
    // Priority (high to low):
    //   1. pow_done_dlyd: reset after last coef_madd_rdy (sample done)
    //   2. exp_valid_r && coef_idx_r==0: x^0 term: load coef[0] directly,
    //      bypassing the FMA (avoids consecutive-cycle chain break)
    //   3. coef_madd_rdy: accumulate FMA result (x^1 .. x^MAX_DEGREE terms)
    always_ff @(posedge clk or posedge rst) begin
        if (rst) begin
            accumulate <= '0;
        end else begin
            if (exp_valid_r && coef_idx_r == '0) begin
                // x^0 = 1, so x^0 * coef[0] = coef[0]. Load directly from RAM.
                // Higher priority than pow_done_dlyd: at sample boundaries both fire
                // simultaneously (pow_done_dlyd from sample N, x^0 from sample N+1),
                // and the new sample's coef[0] must win to seed the accumulate chain.
                accumulate <= coef_value;
            end else if (pow_done_dlyd) begin
                accumulate <= '0;
            end else if (coef_madd_rdy) begin
                accumulate <= coef_madd;
            end
        end
    end

endmodule
