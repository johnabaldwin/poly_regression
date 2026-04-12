module register #(
    parameter int WIDTH = 1,
    parameter int N_STAGES = 1,
    parameter logic [WIDTH-1:0] RESET_VALUE = '0
)
(
    input logic clk,
    input logic rst,
    input logic en,
    input logic [WIDTH-1:0] in,
    output logic [WIDTH-1:0] out
);

    initial begin
        if (WIDTH < 1) $fatal(1, "Width must be >= 1.");
        if (N_STAGES < 0) $fatal(1, "Number of stages must be >= .");
    end

    // Register chain.
    logic [WIDTH-1:0] regs [N_STAGES+1];

    // Assign input of register chain.
    assign regs[0] = in;

    // Assign intermediate values of register chain.
    generate
        for (genvar i=1; i <= N_STAGES; i++) begin : gen_dly
            always_ff @(posedge clk or posedge rst) begin
                if (rst) regs[i] <= RESET_VALUE;
                else if (en) regs[i] <= regs[i-1];
            end
        end
    endgenerate

    // Assign overall output.
    assign out = regs[N_STAGES];

endmodule
