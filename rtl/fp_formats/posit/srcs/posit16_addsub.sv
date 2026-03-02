//============================================================================
// posit16_addsub.sv
//
// POSIT16 Addition and Subtraction
//
// Operation: result = a + b   (when sub=0)
//            result = a - b   (when sub=1, i.e. result = a + (-b))
//
// Algorithm:
//   1. Decode both operands.
//   2. Align mantissas by shifting the smaller operand right.
//   3. Add or subtract aligned mantissas.
//   4. Normalize result (find leading 1, shift).
//   5. Round and encode back to posit16.
//
// Latency: Combinational (single cycle)
//============================================================================

import posit16_pkg::*;

module posit16_addsub (
  input  logic [15:0] a,
  input  logic [15:0] b,
  input  logic        sub,     // 0=add, 1=subtract (negates b)
  output logic [15:0] result
);

  // Internal decoded values
  posit_decoded_t da, db, dr;

  // Effective operand B (negated if sub=1)
  posit_decoded_t db_eff;

  // Extended mantissas for alignment (extra bits for shift and guard)
  // We use MANT_W + EXP_RANGE guard bits; EXP range ≈ 56, so 64 bits is safe
  localparam int ALIGN_W = MANT_W + 64;

  logic [ALIGN_W-1:0] mant_a_ext, mant_b_ext;
  logic signed [EXP_W-1:0] exp_diff;
  logic signed [EXP_W-1:0] exp_result;

  // Sum mantissa (one extra bit for carry/borrow)
  logic [ALIGN_W:0]   mant_sum;
  logic               sum_sign;
  logic [ALIGN_W-1:0] mant_sum_abs;

  // Result before encode
  posit_decoded_t dnorm;

  always_comb begin
    // -----------------------------------------------------------------------
    // 1. Decode
    // -----------------------------------------------------------------------
    da = decode_posit16(a);
    db = decode_posit16(b);

    // Negate B if subtraction
    db_eff       = db;
    db_eff.sign  = db.sign ^ sub;

    // -----------------------------------------------------------------------
    // 2. Handle special cases: NaR propagates; zero identity
    // -----------------------------------------------------------------------
    dr = '0;

    if (da.nar || db_eff.nar) begin
      dr.nar  = 1'b1;
      dr.sign = 1'b1;
    end else if (da.zero && db_eff.zero) begin
      dr.zero = 1'b1;
    end else if (da.zero) begin
      dr = db_eff;
    end else if (db_eff.zero) begin
      dr = da;
    end else begin
      // -----------------------------------------------------------------------
      // 3. Align mantissas
      // Bring both to the larger exponent by right-shifting the smaller one.
      // Place hidden bit at position ALIGN_W-1 initially.
      // -----------------------------------------------------------------------
      exp_diff = da.total_exp - db_eff.total_exp;

      // Place both mantissas in the wide accumulator, shifted so the
      // larger exponent's mantissa occupies the MSB region.
      if (exp_diff >= 0) begin
        // A has larger or equal exponent
        exp_result  = da.total_exp;
        mant_a_ext  = ALIGN_W'(da.mant) << (ALIGN_W - MANT_W);
        mant_b_ext  = ALIGN_W'(db_eff.mant) << (ALIGN_W - MANT_W);
        // Shift B right by exp_diff (with sticky bits captured)
        if (exp_diff >= ALIGN_W)
          mant_b_ext = '0;
        else
          mant_b_ext = mant_b_ext >> exp_diff;
      end else begin
        // B has larger exponent
        exp_result  = db_eff.total_exp;
        mant_a_ext  = ALIGN_W'(da.mant) << (ALIGN_W - MANT_W);
        mant_b_ext  = ALIGN_W'(db_eff.mant) << (ALIGN_W - MANT_W);
        if ((-exp_diff) >= ALIGN_W)
          mant_a_ext = '0;
        else
          mant_a_ext = mant_a_ext >> (-exp_diff);
      end

      // -----------------------------------------------------------------------
      // 4. Add or subtract signed mantissas
      // Signs are handled via two's complement on the extended mantissas.
      // -----------------------------------------------------------------------
      begin
        logic [ALIGN_W:0] sa, sb;
        // Sign-extend to ALIGN_W+1 bits (treat as signed magnitudes)
        if (da.sign) begin
          sa = {1'b1, ~mant_a_ext} + 1'b1; // negate
        end else begin
          sa = {1'b0, mant_a_ext};
        end

        if (db_eff.sign) begin
          sb = {1'b1, ~mant_b_ext} + 1'b1;
        end else begin
          sb = {1'b0, mant_b_ext};
        end

        mant_sum = $signed(sa) + $signed(sb);
      end

      // -----------------------------------------------------------------------
      // 5. Extract sign and absolute value of sum
      // -----------------------------------------------------------------------
      if (mant_sum[ALIGN_W]) begin
        sum_sign     = 1'b1;
        mant_sum_abs = (~mant_sum[ALIGN_W-1:0]) + 1'b1;
      end else begin
        sum_sign     = 1'b0;
        mant_sum_abs = mant_sum[ALIGN_W-1:0];
      end

      // -----------------------------------------------------------------------
      // 6. Normalize: find leading 1 and shift left
      // -----------------------------------------------------------------------
      begin
        int norm_shift;
        logic [MANT_W + GUARD_W - 1:0] mant_norm;

        norm_shift = 0;
        // Find leading 1 — count zeros from MSB downward
        begin
          logic found;
          found = 1'b0;
          for (int i = ALIGN_W - 1; i >= 0; i--) begin
            if (!found) begin
              if (mant_sum_abs[i]) found = 1'b1;
              else                 norm_shift++;
            end
          end
        end

        // Check for exact zero result
        if (norm_shift == ALIGN_W) begin
          dr.zero = 1'b1;
        end else begin
          // Adjust exponent for normalization
          // After left-shift, hidden bit is at position ALIGN_W-1
          // We need the hidden bit aligned to MANT_W-1 in output
          // But the accumulator MSB position is ALIGN_W-1 = MANT_W + 63
          // So the shift from accumulator MSB to output MSB is 64 bits
          // exp_result accounts for position ALIGN_W-1 corresponding to
          // a multiplier of 2^(ALIGN_W-MANT_W) = 2^64 extra, but we
          // already set exp_result to the actual total_exp when we placed
          // mant at ALIGN_W-1 after a left shift of (ALIGN_W-MANT_W).
          // Normalize shift decreases exponent:
          exp_result = exp_result - EXP_W'(norm_shift);

          // Extract top MANT_W+GUARD_W bits for rounding
          begin
            int src_msb;
            src_msb = ALIGN_W - 1 - norm_shift;
            mant_norm = '0;
            for (int i = MANT_W + GUARD_W - 1; i >= 0; i--) begin
              int src;
              src = src_msb - (MANT_W + GUARD_W - 1 - i);
              if (src >= 0) mant_norm[i] = mant_sum_abs[src];
            end
          end

          // Use normalize_round helper
          dnorm = normalize_round(sum_sign, exp_result, mant_norm);
          dr    = dnorm;
        end
      end
    end

    // -----------------------------------------------------------------------
    // 7. Encode result
    // -----------------------------------------------------------------------
    result = encode_posit16(dr);
  end

endmodule