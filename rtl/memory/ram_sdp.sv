module ram_sdp #(
    parameter int DATA_WIDTH = 16,
    parameter int ADDR_WIDTH = 10,
    parameter bit REG_RD_DATA = 1'b0,
    parameter bit WRITE_FIRST = 1'b0,
    parameter string STYLE = ""
) (
    input  logic                  clk,
    input  logic                  rd_en,
    input  logic [ADDR_WIDTH-1:0] rd_addr,
    output logic [DATA_WIDTH-1:0] rd_data,
    input  logic                  wr_en,
    input  logic [ADDR_WIDTH-1:0] wr_addr,
    input  logic [DATA_WIDTH-1:0] wr_data
);
    // Unlike Quartus, Vivado uses ram_style instead of ramstyle. 
    // Ideally, we would imitate the previous this previous code:
    //
    //(* ram_style = STYLE *) logic [DATA_WIDTH-1:0] ram[2**ADDR_WIDTH];

    // However, Vivado has a bug preventing string parameters from being  
    // used in attributes. So, we can hardcode a string literal, but
    // that doesn't give us the flexibility to support different styles via a
    // parameter.

    // Strangely, the following works in Vivado, but doesn't in most simulators:
    //(* ram_style = $sformatf("%s", STYLE) *) logic [DATA_WIDTH-1:0] ram[2**ADDR_WIDTH];

    // An ugly workaround is to manually specify each possible attribute:
    if (STYLE == "block") begin : l_ram
        (* ram_style = "block" *) logic [DATA_WIDTH-1:0] ram[2**ADDR_WIDTH];
    end else if (STYLE == "distributed") begin : l_ram
        (* ram_style = "distributed" *) logic [DATA_WIDTH-1:0] ram[2**ADDR_WIDTH];
    end else if (STYLE == "registers") begin : l_ram
        (* ram_style = "registers" *) logic [DATA_WIDTH-1:0] ram[2**ADDR_WIDTH];
    end else if (STYLE == "ultra") begin : l_ram
        (* ram_style = "ultra" *) logic [DATA_WIDTH-1:0] ram[2**ADDR_WIDTH];
    end else if (STYLE == "mixed") begin : l_ram
        (* ram_style = "mixed" *) logic [DATA_WIDTH-1:0] ram[2**ADDR_WIDTH];
    end else if (STYLE == "auto") begin : l_ram
        (* ram_style = "auto" *) logic [DATA_WIDTH-1:0] ram[2**ADDR_WIDTH];
    end else if (STYLE == "") begin : l_ram
        logic [DATA_WIDTH-1:0] ram[2**ADDR_WIDTH];
    end else begin : l_ram
        initial begin
            $fatal(1, "Invalid STYLE value %s", STYLE);
        end
    end

    logic [DATA_WIDTH-1:0] rd_data_ram;

    always_ff @(posedge clk) begin
        // To make the earlier workaround work, we need a few small changes here.
        // The ram signal has a scope that's only visible within its if-generate
        // region, so to access it from outside that scope, we need to use a 
        // prefix with the generate label l_ram.
        if (wr_en) l_ram.ram[wr_addr] <= wr_data;
        if (rd_en) rd_data_ram <= l_ram.ram[rd_addr];
    end

    if (WRITE_FIRST) begin : l_write_first
        logic bypass_valid_r = 1'b0;
        logic [DATA_WIDTH-1:0] bypass_data_r;

        always_ff @(posedge clk) begin
            if (rd_en && wr_en) bypass_data_r <= wr_data;
            if (rd_en) bypass_valid_r <= wr_en && rd_addr == wr_addr;
        end

        if (REG_RD_DATA) begin : l_reg_rd_data
            always_ff @(posedge clk) if (rd_en) rd_data <= bypass_valid_r ? bypass_data_r : rd_data_ram;
        end else begin : l_no_reg_rd_data
            assign rd_data = bypass_valid_r ? bypass_data_r : rd_data_ram;
        end
    end else begin : l_read_first
        if (REG_RD_DATA) begin : l_reg_rd_data
            always_ff @(posedge clk) if (rd_en) rd_data <= rd_data_ram;
        end else begin : l_no_reg_rd_data
            assign rd_data = rd_data_ram;
        end
    end
endmodule
