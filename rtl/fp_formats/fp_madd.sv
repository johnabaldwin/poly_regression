module fp_madd
    import fpnew_pkg::*;
#(
    parameter fp_format_e FP_FORMAT,
    parameter operation_e MODE,
    parameter int FMA_LATENCY = 2,
    localparam int WIDTH = fp_width(FP_FORMAT)
) (
    input logic clk,
    input logic rst,
    input logic vld,
    input logic sub,
    input logic [WIDTH-1:0] a,
    input logic [WIDTH-1:0] b,
    input logic [WIDTH-1:0] c,
    output logic [WIDTH-1:0] res,
    output logic rdy,
    output status_t fma_status
);
    fpnew_fma #(
        .FpFormat    (FP_FORMAT),
        .NumPipeRegs (FMA_LATENCY),
        .PipeConfig  (fpnew_pkg::DISTRIBUTED),
        .TagType     (logic),
        .AuxType     (logic)
    ) fma_inst (
        .clk_i          (clk),
        .rst_ni         (~rst),

        .operands_i     ({c, b, a}),
        .is_boxed_i     (3'b111),

        .rnd_mode_i     (fpnew_pkg::RNE),
        .op_i           (MODE),
        .op_mod_i       (sub),

        // .src_fmt_i      (FP_FORMAT),
        // .dst_fmt_i      (FP_FORMAT),
        // .vectorial_op_i (1'b0),
        .tag_i          (1'b0),
        .aux_i          (1'b0),

        .in_valid_i     (vld),
        .in_ready_o     (),
        .flush_i        (1'b0),

        .result_o       (res),
        .status_o       (fma_status),
        .tag_o          (),
        .aux_o          (),

        .out_valid_o    (rdy),
        .out_ready_i    (1'b1),

        .busy_o         ()
    );
endmodule
