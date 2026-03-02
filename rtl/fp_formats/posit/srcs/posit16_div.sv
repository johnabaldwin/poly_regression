//============================================================================
// posit16_div.sv
//
// POSIT16 Division: result = a / b
//
// Algorithm (non-restoring / long division on mantissas):
//   1. Decode a and b.
//   2. Result sign   = sign_a XOR sign_b
//      Result exp    = exp_a - exp_b
//   3. Mantissa division: mant_a / mant_b using integer shift-subtract
//      (restoring division) to produce a (MANT_W + GUARD_W)-bit quotient.
//   4. Normalize, round, and encode.
//
// Latency: Combinational — the for-loop synthesizes as combinational logic.
//          For better timing, pipeline the loop body or use a DSP divider.
//============================================================================

import posit16_pkg::*;

module posit16_div (
  input  logic [15:0] a,        // dividend
  input  logic [15:0] b,        // divisor
  output logic [15:0] result
);

  posit_decoded_t da, db, dr;

  always_comb begin
    da = decode_posit16(a);
    db = decode_posit16(b);

    dr = '0;

    // -----------------------------------------------------------------------
    // Special cases
    // -----------------------------------------------------------------------
    if (da.nar || db.nar || db.zero) begin
      // NaR / x = NaR; x / NaR = NaR; x / 0 = NaR
      dr.nar  = 1'b1;
      dr.sign = 1'b1;
    end else if (da.zero) begin
      // 0 / x = 0  (x != 0)
      dr.zero = 1'b1;
    end else begin
      // -----------------------------------------------------------------------
      // Core division
      // -----------------------------------------------------------------------
      logic signed [EXP_W:0] exp_diff;
      logic [MANT_W + GUARD_W - 1:0] quotient;
      logic [MANT_W + GUARD_W:0]     remainder; // one extra bit for restoring
      logic [MANT_W - 1:0]           divisor_m;
      int                             bit_idx;

      dr.sign  = da.sign ^ db.sign;

      // Exponent
      exp_diff = $signed({da.total_exp[EXP_W-1], da.total_exp})
               - $signed({db.total_exp[EXP_W-1], db.total_exp});

      divisor_m = db.mant;
      quotient  = '0;
      remainder = '0;

      // Restoring integer division of (1.frac_a) / (1.frac_b)
      // Both mantissas have hidden 1 at bit MANT_W-1.
      // We compute (MANT_W + GUARD_W) quotient bits.
      //
      // Shift dividend bit-by-bit into remainder, subtract divisor if possible.
      for (int i = MANT_W + GUARD_W - 1; i >= 0; i--) begin
        // Shift remainder left and bring in next dividend bit
        begin
          int src_bit;
          src_bit = i + (GUARD_W); // index into da.mant (adjusted)
          // Bring in bit from dividend mantissa (padded with zeros)
          if ((i + GUARD_W) < MANT_W)
            remainder = {remainder[MANT_W + GUARD_W - 1:0], da.mant[i + GUARD_W]};
          else
            remainder = {remainder[MANT_W + GUARD_W - 1:0], 1'b0};
        end
        // Try to subtract divisor
        if (remainder[MANT_W + GUARD_W:0] >= {1'b0, divisor_m, {GUARD_W{1'b0}}}) begin
          remainder = remainder - {1'b0, divisor_m, {GUARD_W{1'b0}}};
          quotient[i] = 1'b1;
        end else begin
          quotient[i] = 1'b0;
        end
      end

      // The quotient needs normalization:
      // mant_a / mant_b where both are in [1,2):
      //   if mant_a >= mant_b → quotient ∈ [1,2) → hidden bit at MSB, exp unchanged
      //   if mant_a <  mant_b → quotient ∈ [0.5,1) → shift left 1, exp--
      begin
        posit_decoded_t tmp;
        logic [MANT_W + GUARD_W - 1:0] q_norm;
        logic signed [EXP_W-1:0]       exp_adj;

        exp_adj = exp_diff[EXP_W-1:0];

        if (quotient[MANT_W + GUARD_W - 1]) begin
          // Hidden bit already at MSB — quotient is in [1,2)
          q_norm = quotient;
        end else begin
          // Shift left 1 bit, decrement exponent
          q_norm  = quotient << 1;
          exp_adj = exp_adj - 1'b1;
        end

        tmp = normalize_round(dr.sign, exp_adj, q_norm);
        dr.total_exp = tmp.total_exp;
        dr.mant      = tmp.mant;
        dr.zero      = tmp.zero;
        dr.nar       = tmp.nar;
      end
    end

    result = encode_posit16(dr);
  end

endmodule
