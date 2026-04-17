"""
Cocotb test coroutine for fp_power.

Drives the DUT through a set of (x, degree) test cases and checks that
every out_valid pulse carries the correct x^k value. Configured via env:

  TB_FP_FORMAT   format name: "FP64" | "FP32" | "FP16" | "FP16ALT"
  TB_MAX_DEGREE  MAX_DEGREE parameter the DUT was built with (default: 3)
"""

import os
import math
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles

sys.path.insert(0, str(Path(__file__).parent))
from utils.fp_formats import FORMATS

# Relative tolerance: 16 ULPs is plenty for chained FP multiplications.
_REL_TOL = {
    "FP64":    16 * 2**-52,   # ~3.6e-15
    "FP32":    16 * 2**-23,   # ~1.9e-6
    "FP16":    16 * 2**-10,   # ~1.6e-2
    "FP16ALT": 16 * 2**-7,    # ~1.3e-1
}

TIMEOUT_PER_CASE = 300   # clock cycles before declaring a hang


async def _drive_and_collect(dut, fmt, x_float, degree):
    """
    Assert in_valid for one cycle then collect every out_valid pulse until
    done fires.  Returns (results_dict, done_seen) where results_dict maps
    power_index -> decoded float.
    """
    # Wait for the DUT to be ready to accept new input.
    for _ in range(TIMEOUT_PER_CASE):
        if dut.in_ready.value == 1:
            break
        await RisingEdge(dut.clk)
    else:
        return {}, False

    dut.in_valid.value = 1
    dut.x_value.value  = fmt.encode(x_float)
    dut.degree.value   = degree
    await RisingEdge(dut.clk)
    dut.in_valid.value = 0

    results = {}
    for _ in range(TIMEOUT_PER_CASE):
        await RisingEdge(dut.clk)
        if dut.out_valid.value == 1:
            idx = int(dut.out_power_idx.value)
            raw = int(dut.out_result.value)
            val = fmt.decode(raw)
            results[idx] = val
            dut._log.info(
                f"  x^{idx:>2} = {val:>14.8g}  "
                f"(raw={raw:#0{fmt.hex_chars + 2}x})"
            )
        if dut.done.value == 1:
            return results, True

    return results, False


@cocotb.test()
async def test_powers(dut):
    fmt_name   = os.environ.get("TB_FP_FORMAT", "FP64")
    max_degree = int(os.environ.get("TB_MAX_DEGREE", "3"))
    fmt        = FORMATS[fmt_name]
    tol        = _REL_TOL[fmt_name]

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    # Reset
    dut.rst.value      = 1
    dut.in_valid.value = 0
    dut.x_value.value  = 0
    dut.degree.value   = 0
    await ClockCycles(dut.clk, 4)
    dut.rst.value = 0
    await ClockCycles(dut.clk, 2)

    # ── Test vectors ─────────────────────────────────────────────────────────
    # (x_float, degree)  — choose values that are exact in the target format.
    test_cases = [
        ( 2.0,        max_degree),
        (-1.5,        max_degree),
        ( 0.5,        max_degree),
        ( 1.0,        0),           # degree=0 edge case: only x^0 output
        ( 3.0,        1),           # degree=1 edge case: x^0 and x^1 only
        (-2.0,        min(2, max_degree)),
    ]

    failures = []

    for x_float, degree in test_cases:
        expected = {k: x_float ** k for k in range(degree + 1)}
        dut._log.info(
            f"{'─'*56}\n"
            f"  Testing x={x_float:>6}, degree={degree}  "
            f"expected={[f'{v:.4g}' for v in expected.values()]}"
        )

        results, done_seen = await _drive_and_collect(dut, fmt, x_float, degree)

        if not done_seen:
            failures.append(
                f"x={x_float} deg={degree}: done never asserted within "
                f"{TIMEOUT_PER_CASE} cycles"
            )
            continue

        for k in range(degree + 1):
            exp = expected[k]

            if k not in results:
                failures.append(
                    f"x={x_float} deg={degree}: x^{k} never output"
                )
                continue

            got = results[k]

            # Relative error, guarding against exp==0 (x^0 is never 0).
            denom    = abs(exp) if exp != 0 else 1.0
            rel_err  = abs(got - exp) / denom

            status = "PASS" if rel_err <= tol else "FAIL"
            dut._log.info(
                f"  [{status}] x^{k}: got={got:.8g} exp={exp:.8g} "
                f"rel_err={rel_err:.2e} (tol={tol:.2e})"
            )

            if rel_err > tol:
                failures.append(
                    f"x={x_float} x^{k}: got {got:.8g}, "
                    f"expected {exp:.8g}, rel_err={rel_err:.2e}"
                )

    assert not failures, (
        f"\n{len(failures)} fp_power correctness failure(s) [{fmt_name}]:\n"
        + "\n".join(f"  • {f}" for f in failures)
    )
