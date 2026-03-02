//============================================================================
// posit16_pkg.sv
//
// POSIT16: N=16, es=1
//   useed = 2^(2^es) = 2^2 = 4
//   Value = (-1)^sign * 4^k * 2^es_field * (1 + fraction)
//
// Special values:
//   16'h0000 = exact zero
//   16'h8000 = NaR (Not-a-Real)
//
// Regime encoding (applied to the magnitude, i.e. unsigned posit bits):
//   First regime bit = 1 → run of 1s of length m, then 0; k = m-1
//   First regime bit = 0 → run of 0s of length m, then 1; k = -m
//
// Decoded internal representation:
//   total_exp (signed, 7 bits) = k * 2 + es_field   [range ≈ -56..56]
//   mant      (16 bits)        = {hidden_1, frac[14:0]}
//============================================================================

package posit16_pkg;

  localparam int N         = 16;
  localparam int ES        = 1;
  localparam int USEED_EXP = 2;   // log2(useed) = 2^ES
  localparam int MANT_W    = 16;  // mantissa width including hidden bit
  localparam int EXP_W     = 7;   // signed exponent width

  typedef struct packed {
    logic                    nar;
    logic                    zero;
    logic                    sign;
    logic signed [EXP_W-1:0] total_exp;
    logic [MANT_W-1:0]       mant;      // hidden 1 at bit [MANT_W-1]
  } posit_decoded_t;

  //--------------------------------------------------------------------------
  // decode_posit16 — combinational decode
  //--------------------------------------------------------------------------
  function automatic posit_decoded_t decode_posit16(input logic [15:0] p);
    posit_decoded_t d;
    logic [14:0] mag;
    int          k, rlen, frac_msb;
    logic [ES-1:0] es_field;
    logic [14:0]   frac;

    d = '0;

    // --- Special values ---
    if (p == 16'h8000) begin
      d.nar  = 1'b1;
      d.sign = 1'b1;
      return d;
    end
    if (p == 16'h0000) begin
      d.zero = 1'b1;
      return d;
    end

    d.sign = p[15];
    // Convert negative posit to magnitude (two's complement negate)
    mag = d.sign ? (~p[14:0] + 1'b1) : p[14:0];

    // --- Decode regime ---
    // Use a 'found' flag instead of break (break not supported in iverilog)
    rlen = 0;
    if (mag[14]) begin
      // Regime: leading 1s — count until a 0 is seen
      begin
        logic found;
        found = 1'b0;
        for (int i = 14; i >= 0; i--) begin
          if (!found) begin
            if (mag[i] == 1'b1) rlen++;
            else                found = 1'b1;
          end
        end
      end
      k    = rlen - 1;
      rlen = (rlen + 1 > 15) ? 15 : rlen + 1; // +1 for terminator 0
    end else begin
      // Regime: leading 0s — count until a 1 is seen
      begin
        logic found;
        found = 1'b0;
        for (int i = 14; i >= 0; i--) begin
          if (!found) begin
            if (mag[i] == 1'b0) rlen++;
            else                found = 1'b1;
          end
        end
      end
      k    = -rlen;
      rlen = (rlen + 1 > 15) ? 15 : rlen + 1; // +1 for terminator 1
    end

    // --- Extract ES field ---
    frac_msb = 14 - rlen; // index in mag[] of the first es bit
    es_field = '0;
    for (int i = ES - 1; i >= 0; i--) begin
      if (frac_msb >= 0) begin
        es_field[i] = mag[frac_msb];
        frac_msb--;
      end
    end

    // --- Extract fraction bits (fill from MSB of frac[]) ---
    frac = '0;
    for (int i = 14; i >= 0; i--) begin
      int src;
      src = frac_msb - (14 - i);
      if (src >= 0) frac[i] = mag[src];
    end

    // --- Fill decoded struct ---
    d.total_exp = $signed(EXP_W'(signed'(k))) * EXP_W'(USEED_EXP)
                + EXP_W'({1'b0, es_field});
    d.mant      = {1'b1, frac[14:0]};

    return d;
  endfunction

  //--------------------------------------------------------------------------
  // encode_posit16 — combinational encode
  // Expects d.mant[MANT_W-1] = 1 (normalized) for non-special values.
  //--------------------------------------------------------------------------
  function automatic logic [15:0] encode_posit16(input posit_decoded_t d);
    logic [15:0]   result;
    int            k, rem, bit_pos;
    logic [ES-1:0] es_field;
    logic [14:0]   mag;

    if (d.nar)  return 16'h8000;
    if (d.zero) return 16'h0000;

    // --- Decompose total_exp → k and es_field ---
    begin
      int te = int'(d.total_exp);
      // Floor division: es_field must be in [0, USEED_EXP)
      if (te >= 0) begin
        k   = te / USEED_EXP;
        rem = te % USEED_EXP;
      end else begin
        k   = (te - (USEED_EXP - 1)) / USEED_EXP;
        rem = te - k * USEED_EXP;
      end
      es_field = ES'(rem);
    end

    // Saturate k
    if (k >  (N - 2)) k =  N - 2;
    if (k < -(N - 2)) k = -(N - 2);

    // --- Build magnitude field ---
    mag     = '0;
    bit_pos = 14;

    if (k >= 0) begin
      for (int i = 0; i <= k && bit_pos >= 0; i++) begin
        mag[bit_pos] = 1'b1; bit_pos--;
      end
      if (bit_pos >= 0) begin mag[bit_pos] = 1'b0; bit_pos--; end // terminator 0
    end else begin
      for (int i = 0; i < -k && bit_pos >= 0; i++) begin
        mag[bit_pos] = 1'b0; bit_pos--;
      end
      if (bit_pos >= 0) begin mag[bit_pos] = 1'b1; bit_pos--; end // terminator 1
    end

    // Write ES field (MSB first)
    for (int i = ES - 1; i >= 0; i--) begin
      if (bit_pos >= 0) begin mag[bit_pos] = es_field[i]; bit_pos--; end
    end

    // Write fraction bits (skip hidden 1 at mant[MANT_W-1])
    for (int i = MANT_W - 2; i >= 0 && bit_pos >= 0; i--) begin
      mag[bit_pos] = d.mant[i]; bit_pos--;
    end

    result[15]   = d.sign;
    result[14:0] = d.sign ? (~mag + 1'b1) : mag;
    return result;
  endfunction

  //--------------------------------------------------------------------------
  // normalize_and_round — shift mantissa so hidden bit is at MANT_W-1,
  // adjust exponent accordingly, and apply round-to-nearest-even.
  // Extra guard bits (low bits of mant_ext) are used for rounding.
  // mant_ext is (MANT_W + GUARD_W) bits wide.
  //--------------------------------------------------------------------------
  localparam int GUARD_W = 4;

  function automatic posit_decoded_t normalize_round(
    input logic                           sign,
    input logic signed [EXP_W-1:0]       exp_in,
    input logic [MANT_W + GUARD_W - 1:0] mant_ext  // hidden bit expected near MSB
  );
    posit_decoded_t d;
    logic [MANT_W + GUARD_W - 1:0] m;
    int shift;
    logic guard, round_bit, sticky;
    logic do_round;

    d      = '0;
    d.sign = sign;
    m      = mant_ext;

    // Find leading 1 to normalize
    shift = 0;
    if (m == '0) begin
      d.zero = 1'b1;
      return d;
    end

    // Left-shift until bit [MANT_W+GUARD_W-1] is 1
    // (bound iterations to MANT_W+GUARD_W; stop once leading 1 is found)
    begin
      logic norm_done;
      norm_done = 1'b0;
      for (int i = 0; i < MANT_W + GUARD_W; i++) begin
        if (!norm_done) begin
          if (m[MANT_W + GUARD_W - 1] == 1'b0) begin
            m     = m << 1;
            shift = shift + 1;
          end else begin
            norm_done = 1'b1;
          end
        end
      end
    end

    d.total_exp = exp_in - EXP_W'(shift);

    // Round-to-nearest-even using guard bits
    guard     = m[GUARD_W - 1];
    round_bit = m[GUARD_W - 2];
    sticky    = |m[GUARD_W - 3:0];
    do_round  = guard && (round_bit || sticky || m[GUARD_W]);

    m = m >> GUARD_W; // discard guard bits
    if (do_round) begin
      m = m + 1'b1;
      // Re-normalize if rounding caused carry into hidden bit position
      if (m[MANT_W]) begin
        m           = m >> 1;
        d.total_exp = d.total_exp + 1'b1;
      end
    end

    d.mant = m[MANT_W-1:0];
    return d;
  endfunction

endpackage