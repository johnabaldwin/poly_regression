"""
Parametrized pytest runner for the poly_regression FP format comparison.

For each of FP64 / FP32 / FP16 / FP16ALT (bfloat16):
  1. Elaborates and builds the DUT with that format's parameters via Verilator.
  2. Runs the cocotb coroutine (test_dut_run.py) to drive reset/start/done.
  3. Reads the learned coefficients from coef_mem (via internal hierarchy).
  4. Computes per-coefficient absolute and relative error vs the Python FP64
     golden model.
  5. Appends a result row to the session-scoped results_collector, which
     writes format_comparison.csv when the session ends.
"""

import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from cocotb_tools.runner import get_runner

# ── Path setup ────────────────────────────────────────────────────────────────
TB_COCOTB_DIR = Path(__file__).parents[1]
REPO_ROOT     = TB_COCOTB_DIR.parents[1]

sys.path.insert(0, str(TB_COCOTB_DIR))

from utils.fp_formats import ALL_FORMATS
from tb_config import POLY_DEGREE, NUM_SAMPLES, MAX_ITERATIONS, LEARNING_RATE

# ── RTL source list ───────────────────────────────────────────────────────────

def _src(rel: str) -> Path:
    return REPO_ROOT / rel

VERILOG_SOURCES = [
    # common_cells (FPnew dependency)
    _src("external/fpnew/src/common_cells/src/lzc.sv"),
    _src("external/fpnew/src/common_cells/src/rr_arb_tree.sv"),
    # FPnew package must be first
    _src("external/fpnew/src/fpnew_pkg.sv"),
    # FPnew pipeline helpers
    _src("external/fpnew/src/fpnew_pipe_in.sv"),
    _src("external/fpnew/src/fpnew_pipe_inside_fma.sv"),
    _src("external/fpnew/src/fpnew_pipe_inside_cast.sv"),
    _src("external/fpnew/src/fpnew_pipe_out.sv"),
    # FPnew core modules
    _src("external/fpnew/src/fpnew_classifier.sv"),
    _src("external/fpnew/src/fpnew_rounding.sv"),
    _src("external/fpnew/src/fpnew_fma.sv"),
    _src("external/fpnew/src/fpnew_fma_multi.sv"),
    _src("external/fpnew/src/fpnew_f2fcast.sv"),
    _src("external/fpnew/src/fpnew_f2icast.sv"),
    _src("external/fpnew/src/fpnew_i2fcast.sv"),
    _src("external/fpnew/src/fpnew_cast_multi.sv"),
    _src("external/fpnew/src/fpnew_noncomp.sv"),
    # div/sqrt MVP (instantiated unconditionally by fpnew_opgroup_block)
    _src("external/fpnew/src/fpu_div_sqrt_mvp/hdl/defs_div_sqrt_mvp.sv"),
    _src("external/fpnew/src/fpu_div_sqrt_mvp/hdl/preprocess_mvp.sv"),
    _src("external/fpnew/src/fpu_div_sqrt_mvp/hdl/iteration_div_sqrt_mvp.sv"),
    _src("external/fpnew/src/fpu_div_sqrt_mvp/hdl/nrbd_nrsc_mvp.sv"),
    _src("external/fpnew/src/fpu_div_sqrt_mvp/hdl/norm_div_sqrt_mvp.sv"),
    _src("external/fpnew/src/fpu_div_sqrt_mvp/hdl/control_mvp.sv"),
    _src("external/fpnew/src/fpu_div_sqrt_mvp/hdl/div_sqrt_top_mvp.sv"),
    _src("external/fpnew/src/fpu_div_sqrt_mvp/hdl/div_sqrt_mvp_wrapper.sv"),
    _src("external/fpnew/src/fpnew_divsqrt_multi.sv"),
    _src("external/fpnew/src/fpnew_opgroup_fmt_slice.sv"),
    _src("external/fpnew/src/fpnew_opgroup_multifmt_slice.sv"),
    _src("external/fpnew/src/fpnew_opgroup_block.sv"),
    _src("external/fpnew/src/fpnew_top.sv"),
    # Project RTL
    _src("rtl/common/register.sv"),
    _src("rtl/memory/ram_sdp.sv"),
    _src("rtl/memory/register_file.sv"),
    _src("rtl/fp_formats/fp_madd.sv"),
    _src("rtl/fp_formats/fp_power.sv"),
    _src("rtl/algorithm/forward_pass.sv"),
    _src("rtl/algorithm/reverse_pass.sv"),
    _src("rtl/algorithm/control.sv"),
    _src("rtl/top/poly_regression.sv"),
]

# Verilator flags shared across all format builds
VERILATOR_BUILD_ARGS = [
    "--public-flat-rw",    # exposes internal signals to cocotb
    "--trace",
    "--trace-structs",
    "-Wno-WIDTHEXPAND",
    "-Wno-WIDTHTRUNC",
    "-Wno-UNUSED",
    "-Wno-UNOPTFLAT",
    "-Wno-DECLFILENAME",
    "-Wno-CASEOVERLAP",
    "-Wno-PINMISSING",
    "-Wno-ENUMVALUE",
    "-Wno-ASCRANGE",
    # FPnew include paths: registers.svh (and common_cells/ variant)
    f"-I{REPO_ROOT}/external/fpnew/src",
    f"-I{REPO_ROOT}/external/fpnew/src/common_cells/include",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _alpha_2m_bits(fmt, learning_rate: float, num_samples: int) -> int:
    """Encode (learning_rate * 2 / num_samples) as the target FP bit pattern."""
    return fmt.encode(learning_rate * 2.0 / num_samples)


def _abs_errors(hw: list, golden: list) -> list[float]:
    return [abs(h - g) for h, g in zip(hw, golden)]


def _rel_errors(hw: list, golden: list) -> list[float]:
    return [abs(h - g) / (abs(g) + 1e-12) for h, g in zip(hw, golden)]


def _compute_loss(coeffs: list, X: np.ndarray, Y: np.ndarray) -> float:
    M = len(X)
    total = 0.0
    for i in range(M):
        y_hat = sum(coeffs[k] * float(X[i]) ** k for k in range(len(coeffs)))
        total += (y_hat - float(Y[i])) ** 2
    return total / M


def _print_hw_report(fmt_name: str, hw_coeffs: list, hw_loss: float,
                     cycles: int, golden_result: dict) -> None:
    fp_stats  = golden_result["fp_stats"]
    total_ops = golden_result["total_fp_ops"]
    mem       = golden_result["mem_stats"]
    iters     = golden_result["iterations"]

    print(f"\n{'='*60}")
    print(f"  {fmt_name} Hardware Report  |  {cycles:,} simulation cycles")
    print(f"{'='*60}")
    print(f"Final coefficients:")
    for i, c in enumerate(hw_coeffs):
        print(f"  a[{i}] = {c:+.6f}")
    print(f"\nFinal loss: {hw_loss:.6e}")
    print(f"Iterations: {iters}")
    print(f"\n--- Hardware Operation Statistics ---")
    print(f"Total FP operations: {total_ops}")
    for op, count in fp_stats.items():
        pct = 100.0 * count / total_ops if total_ops else 0.0
        print(f"  {op:4s}: {count:8d} ({pct:.1f}%)")
    print(f"\n--- Memory Access Statistics ---")
    print(f"X data: {mem['x_reads']} reads")
    print(f"Y data: {mem['y_reads']} reads")
    print(f"Coefficients: {mem['coef_reads']} reads, {mem['coef_writes']} writes")
    print(f"Gradients: {mem['grad_reads']} reads, {mem['grad_writes']} writes")
    print(f"{'='*60}")


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fmt", ALL_FORMATS, ids=[f.name for f in ALL_FORMATS])
def test_format(
    fmt,
    dataset,
    golden_result,
    hex_data,
    results_collector,
    monkeypatch,
):
    results_file = TB_COCOTB_DIR / f"results_{fmt.name}.json"
    build_dir    = TB_COCOTB_DIR / f"sim_build_{fmt.name}"

    hex_paths     = hex_data[fmt.name]
    alpha_2m_bits = _alpha_2m_bits(fmt, LEARNING_RATE, NUM_SAMPLES)

    # Paths passed to Verilator as string parameters need embedded quotes so
    # Verilator treats them as Verilog string literals: -GPARAM="value"
    def qstr(p: Path) -> str:
        return f'"{p}"'

    # Large integer parameters must be passed as Verilog hex literals to
    # prevent Verilator from truncating them to 32 bits and sign-extending.
    def fp_bits(val: int, width: int) -> str:
        return f"{width}'h{val:0{width//4}X}"

    # Set TB_TRACE=1 to enable VCD output (written to sim_build_<fmt>/dump.vcd).
    # Set TB_MAX_CYCLES=N to limit simulation length (default: 2_000_000).
    trace_enabled = os.environ.get("TB_TRACE", "0") == "1"

    # ── Build ─────────────────────────────────────────────────────────────
    runner = get_runner("verilator")
    runner.build(
        sources=VERILOG_SOURCES,
        hdl_toplevel="poly_regression",
        parameters={
            "FP_FORMAT":      fmt.enum_val,
            "POLY_DEGREE":    POLY_DEGREE,
            "NUM_SAMPLES":    NUM_SAMPLES,
            "MAX_ITERATIONS": MAX_ITERATIONS,
            "ALPHA_2M":       fp_bits(alpha_2m_bits, fmt.width),
            "DATA_MEM_INIT":  qstr(hex_paths["data_mem"]),
            "COEF_MEM_INIT":  qstr(hex_paths["coef_init"]),
            "GRAD_MEM_INIT":  qstr(hex_paths["grad_init"]),
        },
        build_args=VERILATOR_BUILD_ARGS,
        build_dir=build_dir,
        always=True,
        waves=trace_enabled,
    )

    # ── Simulate ──────────────────────────────────────────────────────────
    # Environment variables are the interface between pytest and the cocotb
    # coroutine running inside the simulator subprocess.
    sim_env = {
        "TB_FP_FORMAT":    fmt.name,
        "TB_FP_WIDTH":     str(fmt.width),
        "TB_POLY_DEGREE":  str(POLY_DEGREE),
        "TB_RESULTS_FILE": str(results_file),
        "PYTHONPATH":      os.pathsep.join([
            str(TB_COCOTB_DIR),
            os.environ.get("PYTHONPATH", ""),
        ]),
    }

    max_cycles = os.environ.get("TB_MAX_CYCLES", "2000000")
    sim_env["TB_MAX_CYCLES"] = max_cycles

    runner.test(
        hdl_toplevel="poly_regression",
        test_module="test_dut_run",
        build_dir=build_dir,
        extra_env=sim_env,
        waves=trace_enabled,
    )

    # ── Parse results ─────────────────────────────────────────────────────
    assert results_file.exists(), (
        f"cocotb did not produce a results file for {fmt.name}. "
        "Check the simulation log above."
    )
    hw        = json.loads(results_file.read_text())
    hw_coeffs = hw["coefficients"]
    golden    = golden_result["coefficients"]

    ae      = _abs_errors(hw_coeffs, golden)
    re      = _rel_errors(hw_coeffs, golden)
    hw_loss = _compute_loss(hw_coeffs, dataset.X, dataset.Y)

    # ── Accumulate for CSV ────────────────────────────────────────────────
    row: dict = {"format": fmt.name, "cycles": hw["cycles"], "hw_loss": f"{hw_loss:.6e}"}
    for i, (g, h, a, r) in enumerate(zip(golden, hw_coeffs, ae, re)):
        row[f"a{i}_golden"]  = f"{g:.8f}"
        row[f"a{i}_hw"]      = f"{h:.8f}"
        row[f"a{i}_abs_err"] = f"{a:.4e}"
        row[f"a{i}_rel_err"] = f"{r:.4e}"
    results_collector.append(row)

    # ── Hardware report ───────────────────────────────────────────────────
    _print_hw_report(fmt.name, hw_coeffs, hw_loss, hw["cycles"], golden_result)

    # ── Coefficient comparison table ──────────────────────────────────────
    w = fmt.width
    print(f"\n  {fmt.name} ({w}-bit) vs Golden")
    print(f"  {'Coeff':<8} {'Golden':>14} {'Hardware':>14} {'|Abs err|':>12} {'Rel err':>10}")
    print(f"  {'-'*60}")
    for i, (g, h, a, r) in enumerate(zip(golden, hw_coeffs, ae, re)):
        print(f"  a[{i}]     {g:>14.6f} {h:>14.6f} {a:>12.2e} {r:>10.2e}")
