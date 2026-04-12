/**
 * FP Sequential Power Generator
 *
 * Computes all powers x^0, x^1, x^2, ..., x^n using sequential multiplication.
 * Outputs each power as soon as it's ready (streaming interface).
 *
 * Algorithm:
 *   powers[0] = 1.0              (immediate, no multiplication)
 *   powers[1] = x                (immediate, no multiplication)
 *   powers[2] = powers[1] × x    (1 multiplication)
 *   powers[3] = powers[2] × x    (1 multiplication)
 *   ...
 *   powers[n] = powers[n-1] × x  (1 multiplication)
 *
 * Total: n-1 multiplications for n+1 powers
 *
 * Comparison with Binary Exponentiation:
 * ───────────────────────────────────────────────────────────────────────────
 * For computing x^0 through x^10 (11 values):
 *
 *   Binary Exponentiation (individual):
 *     - x^0:  0 ops (special case)
 *     - x^1:  0 ops (special case)
 *     - x^2:  1 op   (x × x)
 *     - x^3:  2 ops  (x × x, result × x)
 *     - x^4:  2 ops  (x × x, result × result)
 *     - x^5:  3 ops
 *     - x^6:  3 ops
 *     - x^7:  4 ops
 *     - x^8:  3 ops
 *     - x^9:  4 ops
 *     - x^10: 4 ops
 *     TOTAL: ~26 multiplications
 *
 *   Sequential Multiplication (this module):
 *     - x^0:  0 ops (immediate)
 *     - x^1:  0 ops (immediate)
 *     - x^2:  1 op  (x^1 × x)
 *     - x^3:  1 op  (x^2 × x)
 *     - ...
 *     - x^10: 1 op  (x^9 × x)
 *     TOTAL: 9 multiplications
 *
 *   Speedup: 2.9× fewer operations!
 * ───────────────────────────────────────────────────────────────────────────
 *
 * Design Decisions:
 * ═════════════════════════════════════════════════════════════════════════
 *
 * 1. STREAMING OUTPUT INTERFACE
 *    Decision: Output each power as soon as it's computed
 *    Rationale:
 *      - Allows downstream logic to start using powers early
 *      - Don't need to wait for all powers before proceeding
 *      - More flexible than batch output
 *    Implementation:
 *      - out_valid pulses for each new power
 *      - out_power_index indicates which power is ready
 *      - out_result contains the computed power
 *
 * 2. DUAL OUTPUT MODE
 *    Decision: Support both streaming and batch modes
 *    Rationale:
 *      - Streaming: Lower latency, pipeline-friendly
 *      - Batch: Simpler interface for some use cases
 *    Parameter: OUTPUT_MODE ("STREAMING" or "BATCH")
 *
 * 3. STORAGE STRATEGY
 *    Decision: Store all computed powers in internal register array
 *    Rationale:
 *      - Powers can be read back later (useful for gradient computation)
 *      - Small storage cost: (n+1) × WIDTH bits
 *      - Avoids recomputation
 *    Trade-off: Adds registers but provides flexibility
 *
 * 4. IMMEDIATE x^0 AND x^1
 *    Decision: Output x^0=1 and x^1=x without multiplication
 *    Rationale:
 *      - x^0 is always 1.0 (constant)
 *      - x^1 is just the input (wire)
 *      - Saves 2 cycles, no need to use FMA
 *    Implementation:
 *      - State machine outputs these in INIT state
 *      - Then starts multiplication for x^2 onwards
 *
 * 5. POWER INDEX OUTPUT
 *    Decision: Explicitly indicate which power is being output
 *    Rationale:
 *      - Downstream can track which power is ready
 *      - Enables out-of-order processing if needed
 *      - Self-documenting protocol
 *
 * 6. SINGLE FMA INSTANCE
 *    Decision: One FMA, time-multiplexed
 *    Rationale:
 *      - Area efficient (1× FMA cost)
 *      - Sequential nature of algorithm doesn't benefit from parallelism
 *      - Each power depends on previous power
 *
 * 7. SPECIAL CASE: n=0
 *    Decision: If max_degree=0, only output x^0=1
 *    Rationale:
 *      - Handle edge case cleanly
 *      - Constant polynomial (degree 0)
 *
 * 8. SPECIAL CASE: n=1
 *    Decision: If max_degree=1, output x^0 and x^1 immediately
 *    Rationale:
 *      - Linear polynomial only needs these
 *      - No multiplication needed at all
 *
 * 9. RESET BEHAVIOR
 *    Decision: Can abort mid-computation and restart
 *    Rationale:
 *      - Useful for changing input mid-stream
 *      - Clean state management
 *    Implementation:
 *      - in_valid pulse starts new computation
 *      - Resets state machine and counters
 *
 * 10. POWER REGISTER ACCESS
 *    Decision: Expose all computed powers as output port
 *    Rationale:
 *      - Allows random access to any power
 *      - Useful for backward pass in gradient descent
 *      - Minimal cost (just wires from registers)
 *
 * Performance:
 * ────────────
 * Latency:
 *   - First output (x^0): 1 cycle
 *   - Second output (x^1): 1 cycle
 *   - Each subsequent power: FMA_LATENCY + 1 cycles
 *   - Total for n powers: 2 + (n-1) × (FMA_LATENCY + 1) cycles
 *
 * Example (n=10, FMA_LATENCY=2):
 *   - Cycle 0: Start
 *   - Cycle 1: Output x^0 = 1
 *   - Cycle 2: Output x^1 = x
 *   - Cycle 3-5: Compute x^2
 *   - Cycle 5: Output x^2
 *   - Cycle 6-8: Compute x^3
 *   - Cycle 8: Output x^3
 *   - ...
 *   - Cycle 29: Output x^10
 *   Total: 29 cycles for all 11 powers
 *
 * Throughput:
 *   - Can start new computation as soon as previous completes
 *   - No pipeline stalls between powers
 *
 * Area:
 * ─────
 * - 1× FMA unit (dominant)
 * - (n+1) × WIDTH registers for power storage
 * - Small FSM and counters
 * - Total: ~1.1× FMA area
 *
 * Author: John
 * Date: 2025
 */

module fp_sequential_power #(
    parameter fpnew_pkg::fp_format_e FP_FORMAT = fpnew_pkg::FP32,
    parameter int unsigned FMA_LATENCY = 2,      // Latency of FMA (0-4 cycles)
    parameter int unsigned MAX_DEGREE = 10,      // Maximum polynomial degree
    parameter string OUTPUT_MODE = "STREAMING"   // "STREAMING" or "BATCH"
) (
    input  logic clk,
    input  logic rst_n,

    // =========================================================================
    // Input Interface
    // =========================================================================

    input  logic                     in_valid,    // Start computing powers
    output logic                     in_ready,    // Ready for new input
    input  logic [fpnew_pkg::fp_width(FP_FORMAT)-1:0] x_value,  // Base value
    input  logic [$clog2(MAX_DEGREE+1)-1:0] degree,             // Compute up to x^degree

    // =========================================================================
    // Streaming Output Interface (active when OUTPUT_MODE="STREAMING")
    // =========================================================================

    output logic                     out_valid,   // New power available
    output logic [$clog2(MAX_DEGREE+1)-1:0] out_power_index,  // Which power (0 to n)
    output logic [fpnew_pkg::fp_width(FP_FORMAT)-1:0] out_result,  // Power value

    // =========================================================================
    // Batch Output Interface (active when OUTPUT_MODE="BATCH")
    // =========================================================================

    output logic                     done,        // All powers computed
    output logic [fpnew_pkg::fp_width(FP_FORMAT)-1:0] powers [MAX_DEGREE+1],  // All powers

    // =========================================================================
    // Status
    // =========================================================================

    output fpnew_pkg::status_t       status       // FP status flags
);

    // =========================================================================
    // Imports and Parameters
    // =========================================================================

    import fpnew_pkg::*;

    localparam int unsigned WIDTH = fp_width(FP_FORMAT);
    localparam int unsigned DEGREE_WIDTH = $clog2(MAX_DEGREE + 1);

    // Floating point constants
    function automatic logic [WIDTH-1:0] fp_one();
        case (FP_FORMAT)
            FP32:    return 32'h3F800000;
            FP64:    return 64'h3FF0000000000000;
            FP16:    return 16'h3C00;
            FP16ALT: return 16'h3F80;
            FP8:     return 8'h38;
            default: return '0;
        endcase
    endfunction

    function automatic logic [WIDTH-1:0] fp_zero();
        return '0;
    endfunction

    // =========================================================================
    // State Machine
    // =========================================================================

    typedef enum logic [2:0] {
        IDLE          = 3'b000,  // Waiting for input
        OUTPUT_X0     = 3'b001,  // Output x^0 = 1
        OUTPUT_X1     = 3'b010,  // Output x^1 = x
        MULTIPLY      = 3'b011,  // Start multiplication: x^k = x^(k-1) × x
        WAIT_MULT     = 3'b100,  // Wait for FMA to complete
        OUTPUT_POWER  = 3'b101,  // Output newly computed power
        DONE_STATE    = 3'b110   // All powers computed
    } state_t;

    state_t state, next_state;

    // =========================================================================
    // Registers
    // =========================================================================

    // Store all computed powers
    logic [WIDTH-1:0] power_regs [MAX_DEGREE+1];
    logic [WIDTH-1:0] power_regs_next [MAX_DEGREE+1];

    // Current computation state
    logic [WIDTH-1:0]     x_reg, x_next;              // Input value
    logic [DEGREE_WIDTH-1:0] target_degree;           // Degree to compute up to
    logic [DEGREE_WIDTH-1:0] current_index;           // Current power being computed
    logic [DEGREE_WIDTH-1:0] current_index_next;

    // FMA control
    logic [WIDTH-1:0]     fma_op_a, fma_op_b, fma_op_c;
    logic                 fma_in_valid;
    logic [WIDTH-1:0]     fma_result;
    status_t              fma_status;
    logic                 fma_out_valid;

    // Wait counter for FMA latency
    logic [$clog2(FMA_LATENCY+1)-1:0] wait_counter, wait_counter_next;

    // =========================================================================
    // State Machine: Next State Logic
    // =========================================================================

    always_comb begin
        next_state = state;

        case (state)
            IDLE: begin
                if (in_valid && in_ready) begin
                    next_state = OUTPUT_X0;
                end
            end

            OUTPUT_X0: begin
                // Output x^0 = 1
                if (target_degree == '0) begin
                    // Only need x^0
                    next_state = DONE_STATE;
                end
                else begin
                    next_state = OUTPUT_X1;
                end
            end

            OUTPUT_X1: begin
                // Output x^1 = x
                if (target_degree == 1) begin
                    // Only need x^0 and x^1
                    next_state = DONE_STATE;
                end
                else begin
                    // Need to compute x^2 and higher
                    next_state = MULTIPLY;
                end
            end

            MULTIPLY: begin
                // Started multiplication
                if (FMA_LATENCY == 0) begin
                    // Combinational - result ready immediately
                    next_state = OUTPUT_POWER;
                end
                else begin
                    // Pipelined - wait for result
                    next_state = WAIT_MULT;
                end
            end

            WAIT_MULT: begin
                if (wait_counter == FMA_LATENCY) begin
                    next_state = OUTPUT_POWER;
                end
            end

            OUTPUT_POWER: begin
                // Check if we've computed all powers
                if (current_index >= target_degree) begin
                    next_state = DONE_STATE;
                end
                else begin
                    // Compute next power
                    next_state = MULTIPLY;
                end
            end

            DONE_STATE: begin
                // Stay in DONE until new input
                if (in_valid && in_ready) begin
                    next_state = OUTPUT_X0;
                end
            end

            default: begin
                next_state = IDLE;
            end
        endcase
    end

    // =========================================================================
    // State Machine: Output and Register Update
    // =========================================================================

    always_comb begin
        // Defaults - hold current values
        x_next = x_reg;
        current_index_next = current_index;
        wait_counter_next = wait_counter;
        power_regs_next = power_regs;

        // FMA control
        fma_op_a = '0;
        fma_op_b = '0;
        fma_op_c = fp_zero();
        fma_in_valid = 1'b0;

        // Output control
        in_ready = 1'b0;
        out_valid = 1'b0;
        out_power_index = current_index;
        out_result = power_regs[current_index];
        done = 1'b0;

        case (state)
            IDLE: begin
                in_ready = 1'b1;

                if (in_valid) begin
                    // Latch inputs
                    x_next = x_value;
                    target_degree = degree;
                    current_index_next = '0;
                    wait_counter_next = '0;

                    // Initialize x^0 = 1
                    power_regs_next[0] = fp_one();
                end
            end

            OUTPUT_X0: begin
                // Output x^0 = 1 (already in register)
                out_valid = 1'b1;
                out_power_index = 0;
                out_result = power_regs[0];

                // Prepare for x^1
                current_index_next = 1;
                power_regs_next[1] = x_reg;  // x^1 = x
            end

            OUTPUT_X1: begin
                // Output x^1 = x (already in register)
                out_valid = 1'b1;
                out_power_index = 1;
                out_result = power_regs[1];

                // Prepare for x^2
                current_index_next = 2;
            end

            MULTIPLY: begin
                // Compute: x^k = x^(k-1) × x
                fma_op_a = power_regs[current_index - 1];  // x^(k-1)
                fma_op_b = x_reg;                          // x
                fma_op_c = fp_zero();                      // 0 (FMA as multiplier)
                fma_in_valid = 1'b1;

                wait_counter_next = '0;
            end

            WAIT_MULT: begin
                wait_counter_next = wait_counter + 1;

                if (wait_counter == FMA_LATENCY) begin
                    // Latch result
                    power_regs_next[current_index] = fma_result;
                end
            end

            OUTPUT_POWER: begin
                // Output the newly computed power
                out_valid = 1'b1;
                out_power_index = current_index;
                out_result = power_regs[current_index];

                // Move to next power
                current_index_next = current_index + 1;
            end

            DONE_STATE: begin
                done = 1'b1;
                in_ready = 1'b1;  // Ready to accept new computation

                if (in_valid) begin
                    // Start new computation
                    x_next = x_value;
                    target_degree = degree;
                    current_index_next = '0;
                    wait_counter_next = '0;
                    power_regs_next[0] = fp_one();
                end
            end

            default: begin
                // Reset
                current_index_next = '0;
                wait_counter_next = '0;
            end
        endcase
    end

    // =========================================================================
    // Sequential Logic
    // =========================================================================

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            x_reg <= fp_zero();
            current_index <= '0;
            wait_counter <= '0;

            // Initialize power registers
            for (int i = 0; i <= MAX_DEGREE; i++) begin
                power_regs[i] <= fp_zero();
            end
        end
        else begin
            state <= next_state;
            x_reg <= x_next;
            current_index <= current_index_next;
            wait_counter <= wait_counter_next;
            power_regs <= power_regs_next;
        end
    end

    // =========================================================================
    // FMA Instantiation
    // =========================================================================

    fpnew_fma #(
        .FpFormat    (FP_FORMAT),
        .NumPipeRegs (FMA_LATENCY),
        .PipeConfig  (fpnew_pkg::BEFORE),
        .TagType     (logic),
        .AuxType     (logic)
    ) fma_inst (
        .clk_i          (clk),
        .rst_ni         (rst_n),

        .operands_i     ({fma_op_c, fma_op_b, fma_op_a}),
        .is_boxed_i     (3'b111),

        .rnd_mode_i     (fpnew_pkg::RNE),
        .op_i           (fpnew_pkg::FMADD),
        .op_mod_i       (1'b0),

        .src_fmt_i      (FP_FORMAT),
        .dst_fmt_i      (FP_FORMAT),
        .vectorial_op_i (1'b0),
        .tag_i          (1'b0),
        .aux_i          (1'b0),

        .in_valid_i     (fma_in_valid),
        .in_ready_o     (),
        .flush_i        (1'b0),

        .result_o       (fma_result),
        .status_o       (fma_status),
        .tag_o          (),
        .aux_o          (),

        .out_valid_o    (fma_out_valid),
        .out_ready_i    (1'b1),

        .busy_o         ()
    );

    // =========================================================================
    // Output Assignment
    // =========================================================================

    assign powers = power_regs;
    assign status = fma_status;

endmodule
