module poly_regression
    import fpnew_pkg::*;
#(
    parameter fp_format_e FP_FORMAT = FP32,
    localparam int unsigned DATA_WIDTH = fp_width(FP_FORMAT),
    parameter string DATA_MEM_INIT = "",
    parameter string COEF_MEM_INIT = "",
    parameter string GRAD_MEM_INIT = "",
    parameter int POLY_DEGREE = 3,
    localparam int DEG_WIDTH = $clog2(POLY_DEGREE) + 1,
    parameter int FMA_LATENCY = 2,
    localparam int CG_ADDR_WIDTH = $clog2(POLY_DEGREE + 1),
    parameter int NUM_SAMPLES = 100,
    localparam int D_ADDR_WIDTH = $clog2(NUM_SAMPLES),
    parameter int MAX_ITERATIONS = 1000,
    parameter logic [DATA_WIDTH-1:0] ALPHA_2M // Must be precalculated
) (
    input logic clk,
    input logic rst,
    input logic start,

    // // Data memory interface
    // input  [DATA_WIDTH-1:0] x_data_in,
    // input  [DATA_WIDTH-1:0] y_data_in,
    // input  [ADDR_WIDTH-1:0] data_addr,
    // input                   data_write_en,

    // // Results interface
    // output [DATA_WIDTH-1:0] coefficients [POLY_DEGREE:0],
    // output [DATA_WIDTH-1:0] final_loss,
    // output                  done,
    // output [31:0]           iterations_completed

    output logic done
);

    // Read enables
    logic fwd_coef_rd;
    logic coef_rd_en;
    logic error_rd_en;
    logic data_rd_en;

    // Write enables
    logic coef_wr_en;
    logic error_wr_en;
    logic data_wr_en;
    assign data_wr_en = 1'b0; // Data mem should be read only

    // Read results
    logic [DATA_WIDTH-1:0] coef_rd_data;
    logic [DATA_WIDTH-1:0] error_rd_data;
    logic [DATA_WIDTH-1:0] x_rd_data;
    logic [DATA_WIDTH-1:0] y_rd_data;

    // Write data
    logic [DATA_WIDTH-1:0] coef_value;
    logic [DATA_WIDTH-1:0] error_wr_data;
    logic [2*DATA_WIDTH-1:0] data_wr_data;
    assign data_wr_data = '0;

    // Addresses
    logic [1:0] coef_addr_sel;
    logic [CG_ADDR_WIDTH-1:0] coef_wr_addr;
    logic [CG_ADDR_WIDTH-1:0] coef_rd_addr;
    logic [CG_ADDR_WIDTH-1:0] coef_idx;
    logic [D_ADDR_WIDTH-1:0] error_rd_addr;
    logic [D_ADDR_WIDTH-1:0] error_wr_addr;
    logic [D_ADDR_WIDTH-1:0] data_rd_addr;
    logic [D_ADDR_WIDTH-1:0] data_wr_addr = '0;

    // Control Signals
    logic fwd_pow_done;
    logic rev_pow_done;
    logic fwd_data_valid;
    logic rev_data_valid;

    // Reverse Pass
    logic [DEG_WIDTH-1:0] k;
    logic rev_accum_rst;

    forward_pass #(
        .FP_FORMAT  (FP_FORMAT),
        .FMA_LATENCY(FMA_LATENCY),
        .WIDTH      (DATA_WIDTH),
        .MAX_DEGREE (POLY_DEGREE),
        .NUM_SAMPLES(NUM_SAMPLES)
    ) forward_pass (
        .clk       (clk),
        .rst       (rst),
        .valid     (fwd_data_valid),
        .x_value   (x_rd_data),
        .y_value   (y_rd_data),
        .coef_value(coef_rd_data),
        .data_rd_addr,
        .coef_idx  (coef_idx),
        .x_pow_out (),
        .error     (error_wr_data),
        .loss      (),
        .error_wr_addr,
        .fwd_pow_done,
        .coef_rd   (fwd_coef_rd),
        .error_rdy (error_wr_en),
        .exp_in_rdy() //this may need to replace fwd_pow_done?
    );

    reverse_pass #(
        .FP_FORMAT  (FP_FORMAT),
        .FMA_LATENCY(FMA_LATENCY),
        .MAX_DEGREE (POLY_DEGREE),
        .SAMPLES    (NUM_SAMPLES)
     ) reverse_pass (
        .clk         (clk),
        .rst         (rst),
        .start       (rev_data_valid),
        .k           (k),
        .rev_accum_rst,
        .x_value     (x_rd_data),
        .error       (error_rd_data),
        .cur_coef    (coef_rd_data),
        .alpha       (ALPHA_2M),
        .updated_coef(coef_value),
        .new_coef_rdy(coef_wr_en),
        .coef_wr_addr,
        .rev_pow_done
    );

    control #(
        .NUM_SAMPLES   (NUM_SAMPLES),
        .MAX_ITERATIONS(MAX_ITERATIONS),
        .MAX_DEGREE    (POLY_DEGREE)
    ) controller (
        .clk           (clk),
        .rst           (rst),
        .go            (start),
        .fwd_pow_done  (fwd_pow_done),
        .rev_pow_done  (rev_pow_done),
        .data_rd_en    (data_rd_en),
        .data_rd_addr  (data_rd_addr), //TODO: expand this to function for err mem
        .fwd_data_valid,
        .rev_data_valid,
        .done          (done),
        .k             (k),
        .rev_accum_rst
    );

    //TODO: rather than read at end of exponentiation might need to read with data & delay in module
    assign coef_rd_en = rev_pow_done || fwd_coef_rd;
    assign coef_addr_sel = {rev_pow_done, fwd_coef_rd};
    assign coef_rd_addr = coef_addr_sel == 2'b01 ? coef_idx :
                          coef_addr_sel == 2'b10 ? k[1:0] : '0; // k may need to be fixed again :/
    (* DONT_TOUCH = "TRUE" *) ram_sdp #(
        .DATA_WIDTH(DATA_WIDTH),
        .ADDR_WIDTH(CG_ADDR_WIDTH), // degree n poly has n+1 coefs
        .WRITE_FIRST(1'b1),
        .STYLE("block"),
        .MEM_INIT(COEF_MEM_INIT)
    ) coef_mem (
        .clk,
        .rd_en(coef_rd_en),
        .rd_addr(coef_rd_addr),
        .rd_data(coef_rd_data),
        .wr_en(coef_wr_en),
        .wr_addr(coef_wr_addr),
        .wr_data(coef_value)
    );

    assign error_rd_addr = data_rd_addr;
    assign error_rd_en = data_rd_en;
    (* DONT_TOUCH = "TRUE" *) ram_sdp #(
        .DATA_WIDTH(DATA_WIDTH),
        .ADDR_WIDTH($clog2(NUM_SAMPLES)),
        .WRITE_FIRST(1'b1),
        .STYLE("block")
    ) error_mem (  // no MEM_INIT: errors are computed at runtime
        .clk,
        .rd_en(error_rd_en),
        .rd_addr(error_rd_addr),
        .rd_data(error_rd_data),
        .wr_en(error_wr_en),
        .wr_addr(error_wr_addr),
        .wr_data(error_wr_data)
    );

    (* DONT_TOUCH = "TRUE" *) ram_sdp #(
        .DATA_WIDTH(2 * DATA_WIDTH),
        .ADDR_WIDTH($clog2(NUM_SAMPLES)),
        .WRITE_FIRST(1'b1),
        .STYLE("block"),
        .MEM_INIT(DATA_MEM_INIT)
    ) data_mem (
        .clk,
        .rd_en(data_rd_en),
        .rd_addr(data_rd_addr),
        .rd_data({y_rd_data, x_rd_data}),
        .wr_en(data_wr_en),
        .wr_addr(data_wr_addr),
        .wr_data(data_wr_data)
    );

endmodule
