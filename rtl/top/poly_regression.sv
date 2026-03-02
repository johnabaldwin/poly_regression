module poly_regression #(
    parameter FP_ENCODING = "IEEE754_32",
    parameter DATA_MEM_INIT = "",
    parameter COEF_MEM_INIT = "",
    parameter GRAD_MEM_INIT = "",
    parameter POLY_DEGREE = 3,
    parameter NUM_SAMPLES = 100,
    parameter MAX_ITERATIONS = 1000
) (
    input clk,
    input rst,
    input start
    
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
);

    localparam DATA_WIDTH = 16;

    // Read enables
    logic coef_rd_en;
    logic grad_rd_en;
    logic data_rd_en;

    // Write enables
    logic coef_wr_en;
    logic grad_wr_en;
    logic data_wr_en;
    assign data_wr_en = 1'b0; // Data mem should be read only

    // Read results
    logic [DATA_WIDTH-1:0] coef_rd_data;
    logic [DATA_WIDTH-1:0] grad_rd_data;
    logic [DATA_WIDTH-1:0] x_rd_data;
    logic [DATA_WIDTH-1:0] y_rd_data;

    // Write data
    logic [DATA_WIDTH-1:0] coef_wr_data;
    logic [DATA_WIDTH-1:0] grad_wr_data;
    logic [2*DATA_WIDTH-1:0] data_wr_data;
    assign data_wr_data = '0;

    ram_sdp #(
        .DATA_WIDTH,
        .ADDR_WIDTH($clog2(POLY_DEGREE + 1)), // degree n poly has n+1 coefs
        .WRITE_FIRST(1'b1),
        .STYLE("block")
    ) coef_mem (
        .clk,
        .rd_en(coef_rd_en),
        .rd_addr(coef_rd_addr),
        .rd_data(coef_rd_data),
        .wr_en(coef_wr_en),
        .wr_addr(coef_wr_addr),
        .wr_data(coef_wr_data)
    );

    ram_sdp #(
        .DATA_WIDTH,
        .ADDR_WIDTH($clog2(POLY_DEGREE + 1)), // same num of grads & coefs
        .WRITE_FIRST(1'b1),
        .STYLE("block")
    ) grad_mem (
        .clk,
        .rd_en(grad_rd_en),
        .rd_addr(grad_rd_addr),
        .rd_data(grad_rd_data),
        .wr_en(grad_wr_en),
        .wr_addr(grad_wr_addr),
        .wr_data(grad_wr_data)
    );

    ram_sdp #(
        .DATA_WIDTH(2 * DATA_WIDTH),
        .ADDR_WIDTH($clog2(NUM_SAMPLES)),
        .WRITE_FIRST(1'b1),
        .STYLE("block")
    ) data_mem (
        .clk,
        .rd_en(data_rd_en),
        .rd_addr(data_rd_addr),
        .rd_data(data_rd_data),
        .wr_en(data_wr_en),
        .wr_addr(data_wr_addr),
        .wr_data(data_wr_data)
    );

endmodule
