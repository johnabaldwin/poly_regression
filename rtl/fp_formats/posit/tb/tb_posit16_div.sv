//============================================================================
// tb_posit16_div.sv
//
// Testbench for posit16_div module.
//
// Tests:
//   - Identity: a / 1 = a
//   - Self-division: a / a = 1 (for nonzero, non-NaR a)
//   - Division by zero: x / 0 = NaR
//   - Zero dividend: 0 / x = 0
//   - NaR propagation
//   - Negation: a / (-1) = -a
//   - Known-value quotients
//   - Reciprocal: a / b * b ≈ a (multiply-back check)
//============================================================================

`timescale 1ns/1ps

import posit16_pkg::*;

module tb_posit16_div;

  logic [15:0] a, b;
  logic [15:0] result;

  posit16_div dut (
    .a      (a),
    .b      (b),
    .result (result)
  );

  // Also instantiate multiply for reciprocal cross-check
  logic [15:0] mul_a, mul_b, mul_result;
  posit16_mul mul_check (
    .a      (mul_a),
    .b      (mul_b),
    .result (mul_result)
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
      $display("PASS [%0d] %-38s  got=%04h exp=%04h",
               test_cnt, name, got, expected);
      pass_cnt++;
    end else begin
      $display("FAIL [%0d] %-38s  got=%04h (%0.5f)  exp=%04h (%0.5f)",
               test_cnt, name,
               got, posit_to_real(got),
               expected, posit_to_real(expected));
      fail_cnt++;
    end
  endtask

  task automatic check_approx(
    input string       name,
    input logic [15:0] got,
    input logic [15:0] expected,
    input int          ulp_tol = 2
  );
    int diff;
    diff = int'(got) - int'(expected);
    if (diff < 0) diff = -diff;
    test_cnt++;
    if (diff <= ulp_tol) begin
      $display("PASS [%0d] %-38s  got=%04h exp=%04h diff=%0d ULP",
               test_cnt, name, got, expected, diff);
      pass_cnt++;
    end else begin
      $display("FAIL [%0d] %-38s  got=%04h (%0.5f)  exp=%04h (%0.5f) diff=%0d ULP",
               test_cnt, name,
               got, posit_to_real(got),
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
    $display("  POSIT16 Division Testbench");
    $display("========================================");

    // ------------------------------------------------------------------
    // Group 1: Identity (÷1 = identity)
    // ------------------------------------------------------------------
    $display("\n--- Group 1: Division by One ---");

    a = P_ONE;  b = P_ONE;  #1; check("1 / 1 = 1",     result, P_ONE);
    a = P_TWO;  b = P_ONE;  #1; check("2 / 1 = 2",     result, P_TWO);
    a = P_HALF; b = P_ONE;  #1; check("0.5 / 1 = 0.5", result, P_HALF);
    a = P_FOUR; b = P_ONE;  #1; check("4 / 1 = 4",     result, P_FOUR);
    a = P_NONE; b = P_ONE;  #1; check("-1 / 1 = -1",   result, P_NONE);

    // ------------------------------------------------------------------
    // Group 2: Self-division = 1
    // ------------------------------------------------------------------
    $display("\n--- Group 2: Self-division = 1 ---");

    a = P_ONE;  b = P_ONE;  #1; check("1 / 1 = 1",      result, P_ONE);
    a = P_TWO;  b = P_TWO;  #1; check("2 / 2 = 1",      result, P_ONE);
    a = P_HALF; b = P_HALF; #1; check("0.5 / 0.5 = 1",  result, P_ONE);
    a = P_FOUR; b = P_FOUR; #1; check("4 / 4 = 1",      result, P_ONE);
    a = P_NONE; b = P_NONE; #1; check("-1 / -1 = 1",    result, P_ONE);

    // ------------------------------------------------------------------
    // Group 3: Division by zero → NaR
    // ------------------------------------------------------------------
    $display("\n--- Group 3: Division by Zero → NaR ---");

    a = P_ONE;  b = P_ZERO; #1; check("1 / 0 = NaR",   result, P_NAR);
    a = P_TWO;  b = P_ZERO; #1; check("2 / 0 = NaR",   result, P_NAR);
    a = P_ZERO; b = P_ZERO; #1; check("0 / 0 = NaR",   result, P_NAR);
    a = P_NONE; b = P_ZERO; #1; check("-1 / 0 = NaR",  result, P_NAR);

    // ------------------------------------------------------------------
    // Group 4: Zero dividend
    // ------------------------------------------------------------------
    $display("\n--- Group 4: Zero Dividend → Zero ---");

    a = P_ZERO; b = P_ONE;  #1; check("0 / 1 = 0",  result, P_ZERO);
    a = P_ZERO; b = P_TWO;  #1; check("0 / 2 = 0",  result, P_ZERO);
    a = P_ZERO; b = P_HALF; #1; check("0 / 0.5 = 0",result, P_ZERO);
    a = P_ZERO; b = P_NONE; #1; check("0 / -1 = 0", result, P_ZERO);

    // ------------------------------------------------------------------
    // Group 5: NaR propagation
    // ------------------------------------------------------------------
    $display("\n--- Group 5: NaR Propagation ---");

    a = P_NAR;  b = P_ONE;  #1; check("NaR / 1 = NaR",   result, P_NAR);
    a = P_ONE;  b = P_NAR;  #1; check("1 / NaR = NaR",   result, P_NAR);
    a = P_NAR;  b = P_ZERO; #1; check("NaR / 0 = NaR",   result, P_NAR);
    a = P_ZERO; b = P_NAR;  #1; check("0 / NaR = NaR",   result, P_NAR);

    // ------------------------------------------------------------------
    // Group 6: Sign rules
    // ------------------------------------------------------------------
    $display("\n--- Group 6: Sign Rules ---");

    a = P_TWO;  b = P_NONE; #1; check("2 / (-1) = -2",  result, 16'hA000);
    a = P_NONE; b = P_TWO;  #1;
    // -1 / 2 = -0.5
    check("-1 / 2 = -0.5", result, 16'hD000);
    a = P_NONE; b = P_NONE; #1; check("(-1)/(-1) = 1",  result, P_ONE);

    // ------------------------------------------------------------------
    // Group 7: Known quotients
    // ------------------------------------------------------------------
    $display("\n--- Group 7: Known Quotients ---");

    // 4 / 2 = 2
    a = P_FOUR; b = P_TWO; #1;
    check("4 / 2 = 2", result, P_TWO);

    // 2 / 4 = 0.5
    a = P_TWO; b = P_FOUR; #1;
    check("2 / 4 = 0.5", result, P_HALF);

    // 1 / 2 = 0.5
    a = P_ONE; b = P_TWO; #1;
    check("1 / 2 = 0.5", result, P_HALF);

    // 1 / 4 = 0.25
    a = P_ONE; b = P_FOUR; #1;
    check("1 / 4 = 0.25", result, P_QRTR);

    // 0.5 / 2 = 0.25
    a = P_HALF; b = P_TWO; #1;
    check("0.5 / 2 = 0.25", result, P_QRTR);

    // 4 / 1 = 4
    a = P_FOUR; b = P_ONE; #1;
    check("4 / 1 = 4", result, P_FOUR);

    // ------------------------------------------------------------------
    // Group 8: Reciprocal cross-check (a/b * b ≈ a)
    // ------------------------------------------------------------------
    $display("\n--- Group 8: Reciprocal Cross-Check (a/b * b ≈ a) ---");

    begin
      logic [15:0] test_a[6], test_b[6];
      logic [15:0] quot, prod;
      test_a[0] = P_ONE;  test_b[0] = P_TWO;
      test_a[1] = P_FOUR; test_b[1] = P_TWO;
      test_a[2] = 16'h4800; test_b[2] = P_HALF;  // ~1.5 / 0.5
      test_a[3] = 16'h5000; test_b[3] = P_TWO;   // ~3 / 2
      test_a[4] = 16'h6800; test_b[4] = P_FOUR;  // ~3 / 4
      test_a[5] = 16'h3800; test_b[5] = P_HALF;  // ~0.75 / 0.5

      foreach (test_a[i]) begin
        // Compute a/b
        a = test_a[i]; b = test_b[i]; #1; quot = result;
        // Multiply quot * b to recover a
        mul_a = quot; mul_b = test_b[i]; #1; prod = mul_result;

        begin
          int diff;
          diff = int'(prod) - int'(test_a[i]);
          if (diff < 0) diff = -diff;
          if (diff <= 2)
            $display("PASS [recip] a=%04h b=%04h: a/b=%04h (a/b)*b=%04h≈a diff=%0d ULP",
                     test_a[i], test_b[i], quot, prod, diff);
          else
            $display("FAIL [recip] a=%04h b=%04h: a/b=%04h (a/b)*b=%04h≠a diff=%0d ULP (%0.5f vs %0.5f)",
                     test_a[i], test_b[i], quot, prod, diff,
                     posit_to_real(prod), posit_to_real(test_a[i]));
        end
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
