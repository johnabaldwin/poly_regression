module register_file #(
    parameter int POLY_DEGREE = 3, 
    parameter int DATA_WIDTH = 32
) (
    input logic clk,
    input logic rst,
    input logic [$clog2(POLY_DEGREE):0] r_addr,
    input logic [$clog2(POLY_DEGREE):0] w_addr,
    input logic [DATA_WIDTH-1:0] w_data,
    input logic w_en,
    output logic [DATA_WIDTH-1:0] r_data
);

    logic [DATA_WIDTH-1:0] reg_file [POLY_DEGREE + 1];

    always_comb begin
        r_data <= reg_file[r_addr];
    end

    always_ff @(posedge clk or posedge rst) begin
        if (w_en) begin
            reg_file[w_addr] = w_data;
        end
    end

endmodule
