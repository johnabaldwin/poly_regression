"""
cocotb test module for the poly_regression DUT.

This module is invoked by the cocotb runner (not directly by pytest).
Configuration is passed via environment variables set by test_formats.py:

  TB_FP_FORMAT     format name: "FP64" | "FP32" | "FP16" | "FP16ALT"
  TB_FP_WIDTH      bit width of the format: 64 | 32 | 16
  TB_POLY_DEGREE   number of polynomial terms minus one (int)
  TB_RESULTS_FILE  absolute path to write the JSON results file
  TB_MAX_CYCLES    simulation timeout in clock cycles (default: 2_000_000)
"""

import os
import json
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles

# Ensure tb/cocotb/ is on the path so `utils` is importable
sys.path.insert(0, str(Path(__file__).parent))
from utils.fp_formats import FORMATS


@cocotb.test()
async def run_poly_regression(dut):
    fp_format_name = os.environ["TB_FP_FORMAT"]
    poly_degree    = int(os.environ["TB_POLY_DEGREE"])
    results_file   = Path(os.environ["TB_RESULTS_FILE"])
    max_cycles     = int(os.environ.get("TB_MAX_CYCLES", "2000000"))

    fmt = FORMATS[fp_format_name]

    # ── Clock ─────────────────────────────────────────────────────────────
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    # ── Reset ─────────────────────────────────────────────────────────────
    dut.rst.value   = 1
    dut.start.value = 0
    await ClockCycles(dut.clk, 8)
    dut.rst.value = 0
    await ClockCycles(dut.clk, 2)

    # ── Start training ────────────────────────────────────────────────────
    dut.start.value = 1
    await RisingEdge(dut.clk)
    dut.start.value = 0

    # ── Wait for done ─────────────────────────────────────────────────────
    cycles_elapsed = 0
    for cycles_elapsed in range(max_cycles):
        await RisingEdge(dut.clk)
        if dut.done.value == 1:
            break
    else:
        raise AssertionError(
            f"[{fp_format_name}] done not asserted within {max_cycles} cycles"
        )

    dut._log.info(f"[{fp_format_name}] done asserted at cycle {cycles_elapsed + 1}")

    # ── Read coef_mem via internal hierarchy ──────────────────────────────
    # Path: dut.coef_mem.gen_l_ram.ram[i]
    # Requires Verilator built with --public-flat-rw.
    coefficients = []
    for i in range(poly_degree + 1):
        raw = int(dut.coef_mem.gen_l_ram.ram[i].value)
        coefficients.append(fmt.decode(raw))

    dut._log.info(
        f"[{fp_format_name}] coefficients = "
        f"{[f'{c:.6f}' for c in coefficients]}"
    )

    # ── Write results for pytest ──────────────────────────────────────────
    results_file.parent.mkdir(parents=True, exist_ok=True)
    results_file.write_text(json.dumps({
        "format":       fp_format_name,
        "coefficients": coefficients,
        "cycles":       cycles_elapsed + 1,
    }, indent=2))
