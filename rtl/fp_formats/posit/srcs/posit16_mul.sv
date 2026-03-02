//============================================================================
// posit16_mul.sv
//
// POSIT16 Multiplication: result = a * b
//
// Algorithm:
//   1. Decode a and b.
//   2. Result sign   = sign_a XOR sign_b
//      Result exp    = exp_a + exp_b
//      Result mant   = mant_a * mant_b  (MANT_W × MANT_W → 2*MANT_W product)
//   3. Normalize: if product has hidden bit at position [2*MANT_W-1] (expected)
//      or [2*MANT_W-2] (if no carry), shift accordingly.
//   4. Round and encode.
//
// Latency: Combinational (single cycle).  For large MANT_W the multiplier
//          will be pipelined in physical synthesis; add pipeline registers
//          around the multiply if needed.
//============================================================================

import posit16_pkg::*;

module posit16_mul (
  input  logic [15:0] a,
  input  logic [15:0] b,
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
    if (da.nar || db.nar) begin
      // NaR * anything = NaR
      dr.nar  = 1'b1;
      dr.sign = 1'b1;
    end else if (da.zero || db.zero) begin
      // 0 * anything = 0
      dr.zero = 1'b1;
    end else begin
      // -----------------------------------------------------------------------
      // Core multiply
      // -----------------------------------------------------------------------
      logic [2*MANT_W - 1:0] prod;
      logic signed [EXP_W:0] exp_sum; // one extra bit to catch overflow
      logic [MANT_W + GUARD_W - 1:0] mant_norm;

      // Sign
      dr.sign = da.sign ^ db.sign;

      // Exponent sum (both exponents are EXP_W-bit signed; sum needs one more bit)
      exp_sum = $signed({da.total_exp[EXP_W-1], da.total_exp})
              + $signed({db.total_exp[EXP_W-1], db.total_exp});

      // Mantissa product: both are (MANT_W)-bit unsigned with hidden 1 at MSB.
      // Product is 2*MANT_W bits; hidden bit of result is at [2*MANT_W-1] or
      // [2*MANT_W-2] depending on whether a carry occurred.
      prod = da.mant * db.mant; // unsigned multiply

      // Normalize: product hidden bit position
      // If prod[2*MANT_W-1] == 1 → result has extra integer bit, shift right 1
      if (prod[2*MANT_W - 1]) begin
        // Hidden bit at position 2*MANT_W-1; exponent increases by 1
        exp_sum = exp_sum + 1;
        // Take top MANT_W+GUARD_W bits (skip the leading 1 of this double-wide int)
        // We keep the leading 1 as the hidden bit of the output:
        mant_norm = prod[2*MANT_W-1 -: MANT_W + GUARD_W];
      end else begin
        // Hidden bit at position 2*MANT_W-2
        mant_norm = prod[2*MANT_W-2 -: MANT_W + GUARD_W];
      end

      // Use package normalize_round (handles rounding and encoding prep)
      begin
        posit_decoded_t tmp;
        tmp = normalize_round(dr.sign, exp_sum[EXP_W-1:0], mant_norm);
        dr.total_exp = tmp.total_exp;
        dr.mant      = tmp.mant;
        dr.zero      = tmp.zero;
        dr.nar       = tmp.nar;
      end
    end

    result = encode_posit16(dr);
  end

endmodule
