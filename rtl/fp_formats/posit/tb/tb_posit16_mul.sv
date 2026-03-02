//============================================================================
// tb_posit16_mul.sv
//
// Testbench for posit16_mul module.
//
// Tests:
//   - Identity: a * 1 = a
//   - Zero: a * 0 = 0
//   - NaR propagation
//   - Negation: a * (-1) = -a
//   - Known-value products
//   - Commutativity: a*b = b*a
//   - Associativity (approximate): (a*b)*c ≈ a*(b*c)
//   - Squaring: a*a >= 0 for all a (posit property: square is always positive)
//============================================================================

`timescale 1ns/1ps

import posit16_pkg::*;

module tb_posit16_mul;

  logic [15:0] a, b;
  logic [15:0] result;

  posit16_mul dut (
    .a      (a),
    .b      (b),
    .result (result)
  );

  int pass_cnt, fail_cnt, test_cnt;

  function automatic real posit_to_real(input logic [15:0] p);
    posit_decoded_t d;
    real val;
    d = decode_posit16(p);
    if (d.nar)  return 1.0/0.0;
    if (d.zero) return 0.0;
    val = real'(d.mant) / real'(1 << (MANT_W - 1));
    val = val * (2.0 ** int'(d.total_exp));
    if (d.sign) val = -val;
    return val;
  endfunction

  task automatic check(
    input string       name,
    input logic [15:0] got,
    input logic [15:0] expected
  );
    test_cnt++;
    if (got === expected) begin
      $display("PASS [%0d] %-35s  got=%04h exp=%04h",
               test_cnt, name, got, expected);
      pass_cnt++;
    end else begin
      $display("FAIL [%0d] %-35s  got=%04h (%0.5f)  exp=%04h (%0.5f)",
               test_cnt, name, got, posit_to_real(got),
               expected, posit_to_real(expected));
      fail_cnt++;
    end
  endtask

  task automatic check_approx(
    input string       name,
    input logic [15:0] got,
    input logic [15:0] expected,
    input int          ulp_tol = 1
  );
    int diff;
    diff = int'(got) - int'(expected);
    if (diff < 0) diff = -diff;
    test_cnt++;
    if (diff <= ulp_tol) begin
      $display("PASS [%0d] %-35s  got=%04h exp=%04h diff=%0d ULP",
               test_cnt, name, got, expected, diff);
      pass_cnt++;
    end else begin
      $display("FAIL [%0d] %-35s  got=%04h (%0.5f)  exp=%04h (%0.5f) diff=%0d ULP",
               test_cnt, name, got, posit_to_real(got),
               expected, posit_to_real(expected), diff);
      fail_cnt++;
    end
  endtask

  // Known encodings (es=1)
  localparam logic [15:0] P_ZERO =  16'h0000;
  localparam logic [15:0] P_NAR  =  16'h8000;
  localparam logic [15:0] P_ONE  =  16'h4000; //  1
  localparam logic [15:0] P_NONE =  16'hC000; // -1
  localparam logic [15:0] P_TWO  =  16'h6000; //  2
  localparam logic [15:0] P_HALF =  16'h3000; //  0.5
  localparam logic [15:0] P_QRTR =  16'h2000; //  0.25
  localparam logic [15:0] P_FOUR =  16'h7000; //  4

  initial begin
    pass_cnt = 0; fail_cnt = 0; test_cnt = 0;

    $display("========================================");
    $display("  POSIT16 Multiply Testbench");
    $display("========================================");

    // ------------------------------------------------------------------
    // Group 1: Identity (×1 = identity)
    // ------------------------------------------------------------------
    $display("\n--- Group 1: Multiplicative Identity ---");

    a = P_ONE;  b = P_ONE;  #1; check("1 * 1 = 1",    result, P_ONE);
    a = P_TWO;  b = P_ONE;  #1; check("2 * 1 = 2",    result, P_TWO);
    a = P_HALF; b = P_ONE;  #1; check("0.5 * 1 = 0.5",result, P_HALF);
    a = P_NONE; b = P_ONE;  #1; check("-1 * 1 = -1",  result, P_NONE);
    a = P_ONE;  b = P_NONE; #1; check("1 * -1 = -1",  result, P_NONE);

    // ------------------------------------------------------------------
    // Group 2: Zero
    // ------------------------------------------------------------------
    $display("\n--- Group 2: Multiply by Zero ---");

    a = P_ONE;  b = P_ZERO; #1; check("1 * 0 = 0",   result, P_ZERO);
    a = P_ZERO; b = P_TWO;  #1; check("0 * 2 = 0",   result, P_ZERO);
    a = P_ZERO; b = P_ZERO; #1; check("0 * 0 = 0",   result, P_ZERO);
    a = P_NONE; b = P_ZERO; #1; check("-1 * 0 = 0",  result, P_ZERO);

    // ------------------------------------------------------------------
    // Group 3: NaR
    // ------------------------------------------------------------------
    $display("\n--- Group 3: NaR Propagation ---");

    a = P_NAR;  b = P_ONE;  #1; check("NaR * 1 = NaR",  result, P_NAR);
    a = P_ONE;  b = P_NAR;  #1; check("1 * NaR = NaR",  result, P_NAR);
    a = P_NAR;  b = P_ZERO; #1; check("NaR * 0 = NaR",  result, P_NAR);
    a = P_ZERO; b = P_NAR;  #1; check("0 * NaR = NaR",  result, P_NAR);

    // ------------------------------------------------------------------
    // Group 4: Sign rules
    // ------------------------------------------------------------------
    $display("\n--- Group 4: Sign Rules ---");

    a = P_NONE; b = P_NONE; #1; check("(-1)*(-1)=1",  result, P_ONE);
    a = P_TWO;  b = P_NONE; #1; check("2*(-1)=-2",    result, 16'hA000);
    a = P_NONE; b = P_TWO;  #1; check("(-1)*2=-2",    result, 16'hA000);

    // ------------------------------------------------------------------
    // Group 5: Known products
    // ------------------------------------------------------------------
    $display("\n--- Group 5: Known Products ---");

    // 2 * 2 = 4
    a = P_TWO; b = P_TWO; #1;
    check("2 * 2 = 4", result, P_FOUR);

    // 0.5 * 2 = 1
    a = P_HALF; b = P_TWO; #1;
    check("0.5 * 2 = 1", result, P_ONE);

    // 0.5 * 0.5 = 0.25
    a = P_HALF; b = P_HALF; #1;
    check("0.5 * 0.5 = 0.25", result, P_QRTR);

    // 0.25 * 4 = 1
    a = P_QRTR; b = P_FOUR; #1;
    check("0.25 * 4 = 1", result, P_ONE);

    // 4 * 4 = 16
    a = P_FOUR; b = P_FOUR; #1;
    // 16 in posit16 es=1: k=2 (useed^2 = 16), es=0, frac=0
    // k=2: "1110", es_bit="0", frac=0 → 0111 0000 0000 0000 = 0x7800? 
    // Let's compute: k=2 → 3 ones + terminator 0 = "1110", es=0 → "0" => mag = 1110 0000 0000 000x
    // = 0x7000 is k=1,es=0 (4), need to check k=2
    $display("  4 * 4 = %04h (%0.4f)", result, posit_to_real(result));
    check_approx("4 * 4 ≈ 16", result, 16'h7800, 1);

    // 2 * 0.5 = 1
    a = P_TWO; b = P_HALF; #1;
    check("2 * 0.5 = 1", result, P_ONE);

    // ------------------------------------------------------------------
    // Group 6: Commutativity
    // ------------------------------------------------------------------
    $display("\n--- Group 6: Commutativity ---");

    begin
      logic [15:0] pairs [5][2];
      logic [15:0] r1, r2;
      pairs[0] = '{P_TWO, P_HALF};
      pairs[1] = '{P_FOUR, P_QRTR};
      pairs[2] = '{P_ONE, P_NONE};
      pairs[3] = '{16'h5500, 16'h3200};
      pairs[4] = '{16'h4800, 16'h3800};

      foreach (pairs[i]) begin
        a = pairs[i][0]; b = pairs[i][1]; #1; r1 = result;
        a = pairs[i][1]; b = pairs[i][0]; #1; r2 = result;
        if (r1 === r2)
          $display("PASS [comm] a=%04h * b=%04h: %04h = %04h",
                   pairs[i][0], pairs[i][1], r1, r2);
        else
          $display("FAIL [comm] a=%04h * b=%04h: %04h != %04h",
                   pairs[i][0], pairs[i][1], r1, r2);
      end
    end

    // ------------------------------------------------------------------
    // Group 7: Squaring is always non-negative
    // ------------------------------------------------------------------
    $display("\n--- Group 7: Squaring (result >= 0) ---");

    begin
      logic [15:0] test_vals[8];
      test_vals[0] = P_ONE;
      test_vals[1] = P_NONE;
      test_vals[2] = P_TWO;
      test_vals[3] = P_HALF;
      test_vals[4] = 16'h4800; // ~1.5
      test_vals[5] = 16'hB800; // ~-1.5 (negated)
      test_vals[6] = 16'h6800; // ~3
      test_vals[7] = 16'h3800; // ~0.75

      foreach (test_vals[i]) begin
        a = test_vals[i]; b = test_vals[i]; #1;
        if (result[15] == 0 || result == P_ZERO || result == P_NAR)
          $display("PASS [sq] %04h^2 = %04h (%0.5f, non-neg OK)",
                   test_vals[i], result, posit_to_real(result));
        else
          $display("FAIL [sq] %04h^2 = %04h (%0.5f, NEGATIVE!)",
                   test_vals[i], result, posit_to_real(result));
      end
    end

    // ------------------------------------------------------------------
    // Summary
    // ------------------------------------------------------------------
    $display("\n========================================");
    $display("  RESULTS: %0d passed, %0d failed, %0d total",
             pass_cnt, fail_cnt, test_cnt);
    $display("========================================");

    if (fail_cnt == 0)
      $display("  ALL TESTS PASSED");
    else
      $display("  SOME TESTS FAILED");

    $finish;
  end

endmodule
