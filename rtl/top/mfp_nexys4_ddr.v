// mfp_nexys4_ddr.v
//
// Nexys4 DDR board top-level wrapper for poly_regression.
//
// Board I/O mapping:
//   CLK100MHZ  -> clk_wiz_0 (50 MHz) -> poly_regression.clk
//   BTNC       -> debounced reset  -> poly_regression.rst
//   CPU_RESETN -> board reset      -> poly_regression.rst (active-low, OR'd)
//   BTNU       -> debounced start  -> poly_regression.start
//   LED[0]     <- poly_regression.done
//   LED[1]     <- start (debounced BTNU, shows button registered)
//   LED[2]     <- locked (PLL status, lit once clock is stable)
//   LED[15:3]  <- 0

`include "mfp_ahb_const.vh"

module mfp_nexys4_ddr #(
    // Passed through to poly_regression.  See poly_regression.sv for full docs.
    // fpnew_pkg::fp_format_e encoding: 3'b000=FP32, 3'b001=FP64, 3'b010=FP16, 3'b100=FP16ALT
    parameter [2:0]  FP_FORMAT      = 3'b000,   // FP32
    parameter integer POLY_DEGREE   = 3,
    parameter integer FMA_LATENCY   = 3,
    parameter integer NUM_SAMPLES   = 100,
    parameter integer MAX_ITERATIONS = 1000,
    // ALPHA_2M: alpha/(2*NUM_SAMPLES) as an FP bit pattern.
    // Width matches FP32 (32 bits).  Redefine as [63:0] when using FP64.
    // Compute: python3 -c "import struct; print(struct.pack('>f', LR/2/N).hex())"
    // Default 32'h38D1EB85 = 5.0e-5  (LR=0.01, N=100, FP32)
    parameter [31:0] ALPHA_2M       = 32'h38D1EB85,
    parameter        DATA_MEM_INIT  = "/home/john/poly_regression/data/FP32/data_mem.hex",
    parameter        COEF_MEM_INIT  = "/home/john/poly_regression/data/FP32/coef_mem.hex",
    parameter        GRAD_MEM_INIT  = "/home/john/poly_regression/data/FP32/grad_mem.hex"
) (
    input                    CLK100MHZ,
    input                    CPU_RESETN,
    input                    BTNU, BTND, BTNL, BTNC, BTNR,
    input  [`MFP_N_SW-1 :0] SW,
    output [`MFP_N_LED-1:0] LED,
    inout  [4           :1] JA,
    inout  [8           :1] JB,
    output [7           :0] AN,
    output                  CA, CB, CC, CD, CE, CF, CG,
    output [10           :1] JC,
    output [4           :1] JD,
    input                    UART_TXD_IN
);

    // ── Reset ─────────────────────────────────────────────────────────────────
    // Held high (reset asserted) while the PLL is not locked, while BTNC is
    // pressed, or while the board reset button (CPU_RESETN, active-low) is held.

    // button_debounce #(
    //     .DEBOUNCE_PERIOD(1000000)   // 10 ms at 100 MHz
    // ) reset_debouncer (
    //     .clk          (CLK100MHZ),
    //     .btn_in       (BTNC),
    //     .btn_debounced(reset_btn)
    // );

    wire rst;
    assign rst = BTNC | ~CPU_RESETN;

    // ── Start ─────────────────────────────────────────────────────────────────
    // BTNU triggers a single debounced pulse to start gradient descent.

    wire start;
    assign start = BTNU;

    // button_debounce #(
    //     .DEBOUNCE_PERIOD(1000000)   // 10 ms at 100 MHz
    // ) start_debouncer (
    //     .clk          (CLK100MHZ),
    //     .btn_in       (BTNU),
    //     .btn_debounced(start)
    // );




    // ── Polynomial regression core ────────────────────────────────────────────
    // FP_FORMAT: fpnew_pkg::fp_format_e encoding — 3'b000 = FP32
    // ALPHA_2M:  learning_rate / (2 * NUM_SAMPLES) as an FP32 bit pattern.
    //   Compute: python3 -c "import struct; print(struct.pack('>f', LR/2/N).hex())"
    //   Default 32'h38D1EB85 = 5.0e-5  (learning_rate=0.01, NUM_SAMPLES=100)

    wire done;

    poly_regression #(
        .FP_FORMAT     (FP_FORMAT),
        .POLY_DEGREE   (POLY_DEGREE),
        .FMA_LATENCY   (FMA_LATENCY),
        .NUM_SAMPLES   (NUM_SAMPLES),
        .MAX_ITERATIONS(MAX_ITERATIONS),
        .ALPHA_2M      (ALPHA_2M),
        .DATA_MEM_INIT (DATA_MEM_INIT),
        .COEF_MEM_INIT (COEF_MEM_INIT),
        .GRAD_MEM_INIT (GRAD_MEM_INIT)
    ) poly_reg_inst (
        .clk  (CLK100MHZ),
        .rst  (rst),
        .start(BTNU),
        .done (done)
    );

    // ── LED indicators ────────────────────────────────────────────────────────
    assign LED = {{(`MFP_N_LED-1){1'b0}}, done};

    // ── 7-segment display: off ────────────────────────────────────────────────
    assign AN                       = 8'hFF;        // all anodes off (active low)
    assign {CA, CB, CC, CD, CE, CF, CG} = 7'b1111111;  // all segments off

    // ── PMOD connectors: unused ───────────────────────────────────────────────
    assign JC = 10'b0;
    assign JD =  4'b0;
    assign JA =  4'bz;  // inout: high-Z, nothing to drive
    assign JB =  8'bz;  // inout: high-Z, nothing to drive

endmodule
