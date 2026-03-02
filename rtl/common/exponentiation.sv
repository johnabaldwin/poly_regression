// =============================================================================
// fpnew_pow.sv
//
// Computes c = a ^ b, where:
//   - a is a floating-point value in the format specified by FpFmt
//   - b is a non-negative integer (unsigned)
//   - c is the floating-point result in the same format as a
//
// This wrapper uses FPNew's fpnew_fma (Fused Multiply-Add) unit iteratively.
// Each iteration computes: acc = acc * a + 0  (i.e., pure multiply via FMA)
// The loop runs b times, starting from acc = 1.0.
//
// ALGORITHM:
//   Uses binary exponentiation (exponentiation by squaring) to compute a^b
//   in O(log2(b)) multiplications rather than O(b), keeping the design
//   efficient for large exponents.
//
// ADDITIONAL INPUTS ADDED (beyond clk, rst, a, b, c):
//
//   1. in_valid_i  (logic)
//      Why: FPNew uses a handshaking protocol. in_valid_i tells the unit
//           that the inputs a and b are valid and computation should begin.
//
//   2. in_ready_o  (logic)
//      Why: Handshake output. Asserted when the wrapper is ready to accept
//           new inputs. The caller must wait for in_ready_o before asserting
//           in_valid_i for a new operation.
//
//   3. out_valid_o (logic)
//      Why: Asserted when the output c is valid and the computation is done.
//
//   4. out_ready_i (logic)
//      Why: The downstream consumer signals it is ready to accept the result.
//           Part of the standard FPNew output handshake.
//
//   5. status_o    (fpnew_pkg::status_t)
//      Why: FPNew reports IEEE 754 exception flags (NV, DZ, OF, UF, NX).
//           Exposing this allows the caller to detect overflow, underflow,
//           invalid operations (e.g., 0^0), etc.
//
//   6. tag_i / tag_o (logic [TagWidth-1:0])
//      Why: FPNew supports pipelined tagging to track in-flight operations.
//           Passed through so the caller can correlate results with requests.
//
// PARAMETERS:
//   FpFmt     - fpnew_pkg::fp_format_e: floating-point format
//               e.g., fpnew_pkg::FP32, fpnew_pkg::FP16, fpnew_pkg::FP64
//   ExpWidth  - Bit width of the integer exponent b (default 8, range 0..255)
//   TagWidth  - Width of the tag signal (set to 1 if unused)
//   PipeRegs  - Number of pipeline registers inside FPNew FMA unit
//
// LIMITATIONS:
//   - b must be a non-negative integer (unsigned). Fractional exponents
//     (e.g., a^0.5) require log/exp which is outside FPNew's scope.
//   - 0^0 returns 1.0 (IEEE convention), but status NV flag is NOT set here;
//     callers requiring strict IEEE 754 handling should check for this case.
//   - Negative base with non-integer exponent is not supported.
// =============================================================================

`include "common_cells/registers.svh"

module exponentiation
  import fpnew_pkg::*;
#(
  parameter fpnew_pkg::fp_format_e FpFmt    = fpnew_pkg::FP32,
  parameter int unsigned           ExpWidth = 8,    // bits for integer exponent b
  parameter int unsigned           TagWidth = 1,    // passthrough tag width
  parameter int unsigned           PipeRegs = 0     // FMA pipeline depth
) (
  input  logic                    clk_i,
  input  logic                    rst_ni,           // active-low reset

  // --- Floating-point base ---
  input  logic [WIDTH-1:0]        a_i,              // base (float)

  // --- Integer exponent ---
  input  logic [ExpWidth-1:0]     b_i,              // exponent (unsigned int)

  // --- Result ---
  output logic [WIDTH-1:0]        c_o,              // result (float): a^b

  // --- Handshake (ADDED - required by FPNew protocol) ---
  input  logic                    in_valid_i,
  output logic                    in_ready_o,
  output logic                    out_valid_o,
  input  logic                    out_ready_i,

  // --- Status flags (ADDED - IEEE 754 exception reporting) ---
  output fpnew_pkg::status_t      status_o,

  // --- Tag passthrough (ADDED - operation tracking in pipelined use) ---
  input  logic [TagWidth-1:0]     tag_i,
  output logic [TagWidth-1:0]     tag_o
);

  // -------------------------------------------------------------------------
  // Derived parameters
  // -------------------------------------------------------------------------
  localparam int unsigned WIDTH = fpnew_pkg::fp_width(FpFmt);

  // Floating-point constant: 1.0 in the selected format
  // IEEE 754: sign=0, exponent=bias, mantissa=0
  localparam int unsigned EXP_BITS  = fpnew_pkg::exp_bits(FpFmt);
  localparam int unsigned MAN_BITS  = fpnew_pkg::man_bits(FpFmt);
  localparam int unsigned BIAS      = (1 << (EXP_BITS - 1)) - 1;

  // 1.0 encoding: sign=0, exp=BIAS, mantissa=0
  localparam logic [WIDTH-1:0] FP_ONE = WIDTH'({1'b0,
                                               EXP_BITS'(BIAS),
                                               MAN_BITS'(0)});

  // -------------------------------------------------------------------------
  // FMA port types
  // The FPNew FMA unit performs: result = A*B + C
  // For pure multiply: set C = 0.0 and op = fpnew_pkg::MUL
  // -------------------------------------------------------------------------
  localparam fpnew_pkg::operation_e FMA_OP = fpnew_pkg::MUL;

  // -------------------------------------------------------------------------
  // State machine
  // -------------------------------------------------------------------------
  typedef enum logic [1:0] {
    IDLE,       // waiting for valid input
    COMPUTE,    // iterating multiply steps
    DONE        // result ready, waiting for downstream
  } state_e;

  state_e state_q, state_d;

  // Working registers
  logic [WIDTH-1:0]    acc_q,   acc_d;   // running accumulator (result)
  logic [WIDTH-1:0]    base_q,  base_d;  // current base (squares each step)
  logic [ExpWidth-1:0] exp_q,   exp_d;   // remaining exponent bits
  logic [TagWidth-1:0] tag_q,   tag_d;

  // FMA signals
  logic [WIDTH-1:0]    fma_op_a, fma_op_b, fma_op_c;
  logic [WIDTH-1:0]    fma_result;
  logic                fma_in_valid, fma_in_ready;
  logic                fma_out_valid, fma_out_ready;
  fpnew_pkg::status_t  fma_status;
  fpnew_pkg::roundmode_e rnd_mode = fpnew_pkg::RNE; // round to nearest even

  // Pending FMA transaction tracking
  logic waiting_fma_q, waiting_fma_d;
  logic fma_for_acc;   // 1=result goes to acc, 0=result goes to base

  // -------------------------------------------------------------------------
  // FPNew FMA instantiation
  // Computes: result = op_a * op_b (with op_c = 0, using MUL mode)
  // -------------------------------------------------------------------------
  fpnew_fma #(
    .FpFormat    ( FpFmt    ),
    .NumPipeRegs ( PipeRegs ),
    .PipeConfig  ( fpnew_pkg::AFTER ),
    .TagType     ( logic    ),  // 1-bit internal tag (we use 1 bit to flag acc vs base)
    .AuxType     ( logic    )
  ) u_fma (
    .clk_i,
    .rst_ni,

    .operands_i  ( {fma_op_c, fma_op_b, fma_op_a} ), // {C, B, A} -> A*B+C
    .is_boxed_i  ( 3'b111                          ), // all operands properly NaN-boxed
    .rnd_mode_i  ( rnd_mode                        ),
    .op_i        ( FMA_OP                          ),
    .op_mod_i    ( 1'b0                            ),
    .tag_i       ( fma_for_acc                     ), // reuse 1-bit tag to track purpose
    .mask_i      ( 1'b1                            ),
    .aux_i       ( 1'b0                            ),

    .in_valid_i  ( fma_in_valid                    ),
    .in_ready_o  ( fma_in_ready                    ),
    .flush_i     ( 1'b0                            ),

    .result_o    ( fma_result                      ),
    .status_o    ( fma_status                      ),
    .extension_bit_o ( /* unused */                ),
    .tag_o       ( fma_tag_out                     ),
    .mask_o      ( /* unused */                    ),
    .aux_o       ( /* unused */                    ),

    .out_valid_o ( fma_out_valid                   ),
    .out_ready_i ( fma_out_ready                   ),
    .busy_o      ( /* unused */                    )
  );

  logic fma_tag_out; // 1 = result is for accumulator, 0 = for base

  // -------------------------------------------------------------------------
  // Binary exponentiation (exponentiation by squaring) controller
  //
  // Invariant maintained: result = acc * base^exp  (initially acc=1, base=a)
  // Each step:
  //   if exp[0]==1: acc  = acc * base  (issue FMA: acc*base+0)
  //                 base = base * base (issue FMA: base*base+0)
  //                 exp  = exp >> 1
  //   else:
  //                 base = base * base
  //                 exp  = exp >> 1
  // When exp == 0: result = acc
  // -------------------------------------------------------------------------

  // We can only issue one FMA at a time (single FMA unit).
  // When exp[0]==1 we need two FMAs this step (acc*base AND base*base).
  // We serialize: first do acc*base -> store to acc_next,
  //               then do base*base -> store to base, advance exp.

  logic [WIDTH-1:0] acc_next_q, acc_next_d; // holds intermediate acc result
  logic             need_base_sq_q, need_base_sq_d; // second FMA pending

  fpnew_pkg::status_t status_q, status_d; // accumulated status

  // -------------------------------------------------------------------------
  // Combinational next-state logic
  // -------------------------------------------------------------------------
  always_comb begin
    // Defaults
    state_d         = state_q;
    acc_d           = acc_q;
    base_d          = base_q;
    exp_d           = exp_q;
    tag_d           = tag_q;
    acc_next_d      = acc_next_q;
    need_base_sq_d  = need_base_sq_q;
    status_d        = status_q;

    // FMA defaults
    fma_op_a        = '0;
    fma_op_b        = '0;
    fma_op_c        = '0;
    fma_in_valid    = 1'b0;
    fma_for_acc     = 1'b0;
    fma_out_ready   = 1'b0;

    // Output defaults
    in_ready_o      = 1'b0;
    out_valid_o     = 1'b0;
    c_o             = acc_q;
    status_o        = status_q;
    tag_o           = tag_q;

    case (state_q)

      // -----------------------------------------------------------------------
      IDLE: begin
        in_ready_o = 1'b1;
        if (in_valid_i) begin
          tag_d          = tag_i;
          status_d       = '0;
          // Special case: b == 0 => result is 1.0 (any a^0 = 1)
          if (b_i == '0) begin
            acc_d   = FP_ONE;
            state_d = DONE;
          end else begin
            acc_d          = FP_ONE;
            base_d         = a_i;
            exp_d          = b_i;
            need_base_sq_d = 1'b0;
            state_d        = COMPUTE;
          end
        end
      end

      // -----------------------------------------------------------------------
      COMPUTE: begin
        // exp == 0 means we're done
        if (exp_q == '0) begin
          state_d = DONE;

        end else if (need_base_sq_q) begin
          // Second pending FMA: base = base * base
          fma_op_a     = base_q;
          fma_op_b     = base_q;
          fma_op_c     = '0;
          fma_for_acc  = 1'b0;  // result -> base
          fma_in_valid = 1'b1;

          if (fma_in_ready) begin
            need_base_sq_d = 1'b0;
            // advance exponent now (we already handled acc*base)
            exp_d = exp_q >> 1;
          end

          // Collect result when ready
          fma_out_ready = 1'b1;
          if (fma_out_valid && !fma_tag_out) begin // tag==0 => base result
            base_d   = fma_result;
            status_d = status_q | fma_status;
          end

        end else begin
          // Normal step
          if (exp_q[0]) begin
            // Odd exponent: issue acc = acc * base
            fma_op_a     = acc_q;
            fma_op_b     = base_q;
            fma_op_c     = '0;
            fma_for_acc  = 1'b1;  // result -> acc
            fma_in_valid = 1'b1;

            if (fma_in_ready) begin
              need_base_sq_d = 1'b1; // will also need base^2
            end

            fma_out_ready = 1'b1;
            if (fma_out_valid && fma_tag_out) begin // tag==1 => acc result
              acc_d    = fma_result;
              status_d = status_q | fma_status;
            end

          end else begin
            // Even exponent: just square the base
            fma_op_a     = base_q;
            fma_op_b     = base_q;
            fma_op_c     = '0;
            fma_for_acc  = 1'b0;
            fma_in_valid = 1'b1;

            if (fma_in_ready) begin
              exp_d = exp_q >> 1;
            end

            fma_out_ready = 1'b1;
            if (fma_out_valid && !fma_tag_out) begin
              base_d   = fma_result;
              status_d = status_q | fma_status;
            end
          end
        end
      end

      // -----------------------------------------------------------------------
      DONE: begin
        out_valid_o = 1'b1;
        c_o         = acc_q;
        status_o    = status_q;
        tag_o       = tag_q;

        if (out_ready_i) begin
          state_d = IDLE;
        end
      end

      default: state_d = IDLE;

    endcase
  end

  // -------------------------------------------------------------------------
  // Sequential logic
  // -------------------------------------------------------------------------
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      state_q        <= IDLE;
      acc_q          <= FP_ONE;
      base_q         <= '0;
      exp_q          <= '0;
      tag_q          <= '0;
      acc_next_q     <= '0;
      need_base_sq_q <= 1'b0;
      status_q       <= '0;
    end else begin
      state_q        <= state_d;
      acc_q          <= acc_d;
      base_q         <= base_d;
      exp_q          <= exp_d;
      tag_q          <= tag_d;
      acc_next_q     <= acc_next_d;
      need_base_sq_q <= need_base_sq_d;
      status_q       <= status_d;
    end
  end

endmodule : fpnew_pow
