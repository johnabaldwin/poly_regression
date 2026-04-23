"""
Randomized polynomial regression tests across all FP formats.

For each randomly-generated test case the following are compared:
  - Hardware learned coefficients vs the Python FP64 golden model
  - Hardware learned coefficients vs the true polynomial coefficients

Environment variables (set by make test-random):
  TB_NUM_TESTS    - number of random test cases to run (required)
  TB_RANDOM_SEED  - base seed controlling all randomness (default: 0)
  TB_MAX_DEGREE   - maximum polynomial degree to sample (default: 9)

Results are stored under:
  tb/cocotb/results/test_<idx>/<FMT>/hw_results.json

A summary CSV is written to:
  tb/cocotb/results/random_summary.csv

Build strategy: one Verilator build per (format, degree) pair, reused across
all test cases that share the same pair.  Hex files are written to a canonical
per-format path immediately before each simulation run; $readmemh reads them
at simulation startup so different test data is picked up without rebuilding.
"""

import contextlib
import csv
import io
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pytest
from cocotb_tools.runner import get_runner

# ── Path setup ────────────────────────────────────────────────────────────────
TB_COCOTB_DIR = Path(__file__).parents[1]
REPO_ROOT     = TB_COCOTB_DIR.parents[1]
SCRIPTS_DIR   = REPO_ROOT / "scripts"

sys.path.insert(0, str(TB_COCOTB_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from utils.fp_formats import ALL_FORMATS
from utils.generate_hex import write_data_mem, write_coef_init, write_grad_init
from utils.rtl_sources import VERILOG_SOURCES, VERILATOR_BUILD_ARGS
from poly_test import (
    HyperParameters,
    PolynomialRegressionHardware,
    generate_polynomial_data,
)
from tb_config import (
    NUM_SAMPLES, MAX_ITERATIONS, LEARNING_RATE, NOISE_STD, X_RANGE,
    degree_lr, degree_max_iter, sim_cycle_budget,
)

# ── Test-case generation (evaluated once at collection time) ──────────────────

_NUM_TESTS  = int(os.environ.get("TB_NUM_TESTS",   "5"))
_BASE_SEED  = int(os.environ.get("TB_RANDOM_SEED", "0"))
_MAX_DEGREE = int(os.environ.get("TB_MAX_DEGREE",  "9"))


def _make_test_cases(n: int, base_seed: int, max_degree: int) -> list[dict]:
    rng = np.random.RandomState(base_seed)
    cases = []
    for i in range(n):
        degree = int(rng.randint(1, max_degree + 1))
        # Uniform true coefficients in [-3, 3]
        true_coeffs = rng.uniform(-3.0, 3.0, degree + 1).tolist()
        cases.append({
            "idx":         i,
            "degree":      degree,
            "true_coeffs": true_coeffs,
            # Independent seeds for data noise and coefficient initialisation
            "data_seed": base_seed * 100_000 + i * 17 + 1,
            "coef_seed": base_seed * 100_000 + i * 17 + 2,
        })
    return cases


_TEST_CASES = _make_test_cases(_NUM_TESTS, _BASE_SEED, _MAX_DEGREE)

# ── Per-session build cache: skip Verilator rebuild for seen (fmt, degree) ────
_BUILT: set[tuple[str, int]] = set()

# ── Parametrise over all (test_case × format) combinations ───────────────────
_PARAMS = [(tc, fmt) for tc in _TEST_CASES for fmt in ALL_FORMATS]
_IDS    = [
    f"test{tc['idx']:03d}_deg{tc['degree']}_{fmt.name}"
    for tc, fmt in _PARAMS
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _compute_loss(coeffs: list[float], X: np.ndarray, Y: np.ndarray) -> float:
    try:
        M = len(X)
        total = sum(
            (sum(coeffs[k] * float(X[i]) ** k for k in range(len(coeffs))) - float(Y[i])) ** 2
            for i in range(M)
        )
        return total / M
    except OverflowError:
        return float("inf")


def _is_diverged(hw_coeffs: list[float], hw_loss: float,
                 golden_loss: float, fmt) -> bool:
    """Return True if gradient descent diverged for any of three reasons:
      1. A coefficient is inf or NaN (FP64: IEEE overflow/NaN propagation).
      2. A coefficient is at or above 99 % of the format's max finite value
         (FP32/FP16/FP16ALT: hardware saturated at the format ceiling).
      3. hw_loss exceeds golden_loss by more than 1000× (any format: diverged
         relative to what the same algorithm achieves in FP64).
    """
    sat_threshold = 0.99 * fmt.max_value
    if any(not math.isfinite(c) for c in hw_coeffs):
        return True
    if any(abs(c) >= sat_threshold for c in hw_coeffs):
        return True
    if not math.isfinite(hw_loss):
        return True
    if math.isfinite(golden_loss) and golden_loss > 0 and hw_loss > golden_loss * 1000.0:
        return True
    return False


def _abs_errors(a: list[float], b: list[float]) -> list[float]:
    return [abs(x - y) for x, y in zip(a, b)]


def _rel_errors(a: list[float], b: list[float]) -> list[float]:
    return [abs(x - y) / (abs(y) + 1e-12) for x, y in zip(a, b)]


def _print_report(
    tc: dict,
    fmt_name: str,
    hw_coeffs: list[float],
    hw_loss: float,
    cycles: int,
    golden: dict,
    true_coeffs: list[float],
    diverged: bool = False,
) -> None:
    degree        = tc["degree"]
    golden_coeffs = golden["coefficients"]
    fp_stats      = golden["fp_stats"]
    total_ops     = golden["total_fp_ops"]
    mem           = golden["mem_stats"]

    ae_vs_golden = _abs_errors(hw_coeffs, golden_coeffs)
    re_vs_golden = _rel_errors(hw_coeffs, golden_coeffs)
    ae_vs_true   = _abs_errors(hw_coeffs, true_coeffs)
    re_vs_true   = _rel_errors(hw_coeffs, true_coeffs)

    sep = "=" * 66
    print(f"\n{sep}")
    print(f"  Test {tc['idx']}  |  Degree {degree}  |  {fmt_name}  |  {cycles:,} cycles")
    print(sep)
    print(f"True coefficients: {[f'{c:+.4f}' for c in true_coeffs]}")
    print(f"\nFinal coefficients (hardware):")
    for i, c in enumerate(hw_coeffs):
        print(f"  a[{i}] = {c:+.6f}")
    print(f"\nFinal loss (HW):     {hw_loss:.6e}")
    print(f"Final loss (golden): {golden['loss']:.6e}")
    print(f"Iterations:          {golden['iterations']}")

    print(f"\n--- FP Operation Statistics (golden model) ---")
    print(f"Total FP operations: {total_ops}")
    for op, count in fp_stats.items():
        pct = 100.0 * count / total_ops if total_ops else 0.0
        print(f"  {op:4s}: {count:8d} ({pct:.1f}%)")

    print(f"\n--- Memory Access Statistics (golden model) ---")
    print(f"X data:       {mem['x_reads']} reads")
    print(f"Y data:       {mem['y_reads']} reads")
    print(f"Coefficients: {mem['coef_reads']} reads, {mem['coef_writes']} writes")
    print(f"Gradients:    {mem['grad_reads']} reads, {mem['grad_writes']} writes")

    print(f"\n--- Coefficients: HW vs Python FP64 Golden ---")
    print(f"  {'':6} {'Golden':>14} {'HW':>14} {'|AbsErr|':>12} {'RelErr':>10}")
    print(f"  {'-'*58}")
    for i, (g, h, a, r) in enumerate(zip(golden_coeffs, hw_coeffs, ae_vs_golden, re_vs_golden)):
        print(f"  a[{i}]   {g:>14.6f} {h:>14.6f} {a:>12.2e} {r:>10.2e}")

    print(f"\n--- Coefficients: HW vs True ---")
    print(f"  {'':6} {'True':>14} {'HW':>14} {'|AbsErr|':>12} {'RelErr':>10}")
    print(f"  {'-'*58}")
    for i, (t, h, a, r) in enumerate(zip(true_coeffs, hw_coeffs, ae_vs_true, re_vs_true)):
        print(f"  a[{i}]   {t:>14.6f} {h:>14.6f} {a:>12.2e} {r:>10.2e}")

    if diverged:
        warn = "  !! DIVERGED: gradient descent did not converge  !!"
        bar  = "!" * len(warn)
        print(f"\n{bar}\n{warn}\n{bar}")

    print(sep)


# ── Session fixture: write summary CSV after all tests complete ───────────────

@pytest.fixture(scope="session")
def random_results_collector() -> list[dict]:
    rows: list[dict] = []
    yield rows

    if not rows:
        return

    out_path = TB_COCOTB_DIR / "results" / "random_summary.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nRandom test summary CSV → {out_path}")


# ── Parametrised test ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("tc,fmt", _PARAMS, ids=_IDS)
def test_random_format(tc, fmt, random_results_collector):
    idx         = tc["idx"]
    degree      = tc["degree"]
    true_coeffs = tc["true_coeffs"]

    # ── Dataset and initial coefficients ─────────────────────────────────
    np.random.seed(tc["data_seed"])
    dataset = generate_polynomial_data(
        true_coeffs=true_coeffs,
        x_range=X_RANGE,
        num_samples=NUM_SAMPLES,
        noise_std=NOISE_STD,
        quiet=True,
    )

    np.random.seed(tc["coef_seed"])
    initial_coeffs = np.random.randn(degree + 1) * 0.01

    # ── Per-degree hyperparameters ────────────────────────────────────────
    # lr scales down by 4× per degree above 3 to stay within the gradient
    # descent stability bound; max_iter scales up proportionally (capped) so
    # each degree gets an equivalent effective training budget.
    lr       = degree_lr(degree)
    max_iter = degree_max_iter(degree)

    # ── Golden model (Python FP64 reference) ─────────────────────────────
    # Suppress the verbose training output; results are printed below.
    hp = HyperParameters(
        poly_degree=degree,
        learning_rate=lr,
        max_iterations=max_iter,
    )
    golden_model = PolynomialRegressionHardware(
        hp, dataset, initial_coeffs=initial_coeffs
    )
    with contextlib.redirect_stdout(io.StringIO()):
        golden_model.train(verbose=False)

    fp_stats  = golden_model.fp_unit.get_stats()
    total_ops = sum(fp_stats.values())
    golden = {
        "coefficients": golden_model.get_coefficients().tolist(),
        "loss":         float(golden_model.total_loss),
        "iterations":   golden_model.iteration + 1,
        "fp_stats":     fp_stats,
        "total_fp_ops": total_ops,
        "mem_stats": {
            "x_reads":     golden_model.data_memory_X.read_count,
            "y_reads":     golden_model.data_memory_Y.read_count,
            "coef_reads":  golden_model.coeff_memory.read_count,
            "coef_writes": golden_model.coeff_memory.write_count,
            "grad_reads":  golden_model.gradient_memory.read_count,
            "grad_writes": golden_model.gradient_memory.write_count,
        },
    }

    # ── Hex files ─────────────────────────────────────────────────────────
    # Canonical per-format path; content is overwritten before every sim run.
    # $readmemh reads the file at simulation startup (runtime), so the binary
    # compiled against this path will pick up the freshly written data.
    hex_dir   = REPO_ROOT / "data" / "random" / fmt.name
    hex_dir.mkdir(parents=True, exist_ok=True)
    data_path = hex_dir / "data_mem.hex"
    coef_path = hex_dir / "coef_init.hex"
    grad_path = hex_dir / "grad_init.hex"

    write_data_mem(dataset.X, dataset.Y, fmt, data_path)
    write_coef_init(initial_coeffs, fmt, coef_path)
    write_grad_init(degree + 1, fmt, grad_path)

    # ── Build ─────────────────────────────────────────────────────────────
    build_dir = TB_COCOTB_DIR / f"sim_build_random_{fmt.name}_deg{degree}"
    build_key = (fmt.name, degree)
    # Build once per (format, degree) per session; subsequent tests reuse.
    need_build = build_key not in _BUILT

    alpha_2m = fmt.encode(lr * 2.0 / NUM_SAMPLES)

    runner = get_runner("verilator")
    runner.build(
        sources=VERILOG_SOURCES,
        hdl_toplevel="poly_regression",
        parameters={
            "FP_FORMAT":      fmt.enum_val,
            "POLY_DEGREE":    degree,
            "NUM_SAMPLES":    NUM_SAMPLES,
            "MAX_ITERATIONS": max_iter,
            "ALPHA_2M":       f"{fmt.width}'h{alpha_2m:0{fmt.width // 4}X}",
            "DATA_MEM_INIT":  f'"{data_path}"',
            "COEF_MEM_INIT":  f'"{coef_path}"',
            "GRAD_MEM_INIT":  f'"{grad_path}"',
        },
        build_args=VERILATOR_BUILD_ARGS,
        build_dir=build_dir,
        always=need_build,
        waves=False,
    )
    _BUILT.add(build_key)

    # ── Simulate ──────────────────────────────────────────────────────────
    results_dir  = TB_COCOTB_DIR / "results" / f"test_{idx}" / fmt.name
    results_dir.mkdir(parents=True, exist_ok=True)
    results_file = results_dir / "hw_results.json"

    sim_env = {
        "TB_FP_FORMAT":    fmt.name,
        "TB_FP_WIDTH":     str(fmt.width),
        "TB_POLY_DEGREE":  str(degree),
        "TB_RESULTS_FILE": str(results_file),
        "TB_MAX_CYCLES":   os.environ.get("TB_MAX_CYCLES") or str(sim_cycle_budget(degree, NUM_SAMPLES, max_iter)),
        "PYTHONPATH": os.pathsep.join([
            str(TB_COCOTB_DIR),
            os.environ.get("PYTHONPATH", ""),
        ]),
    }

    runner.test(
        hdl_toplevel="poly_regression",
        test_module="test_dut_run",
        build_dir=build_dir,
        extra_env=sim_env,
        waves=False,
    )

    # ── Parse results ─────────────────────────────────────────────────────
    assert results_file.exists(), (
        f"cocotb did not write results for test {idx} / {fmt.name}. "
        "Check the simulation log above."
    )
    hw        = json.loads(results_file.read_text())
    hw_coeffs = hw["coefficients"]
    cycles    = hw["cycles"]

    golden_coeffs = golden["coefficients"]
    hw_loss       = _compute_loss(hw_coeffs, dataset.X, dataset.Y)
    ae_vs_golden  = _abs_errors(hw_coeffs, golden_coeffs)
    ae_vs_true    = _abs_errors(hw_coeffs, true_coeffs)
    diverged      = _is_diverged(hw_coeffs, hw_loss, golden["loss"], fmt)

    # ── Print report ──────────────────────────────────────────────────────
    _print_report(tc, fmt.name, hw_coeffs, hw_loss, cycles, golden, true_coeffs,
                  diverged=diverged)

    # ── Accumulate summary row ────────────────────────────────────────────
    # Fixed-width columns up to _MAX_DEGREE so all rows share the same schema.
    row: dict = {
        "test_idx":              idx,
        "degree":                degree,
        "format":                fmt.name,
        "learning_rate":         f"{lr:.6e}",
        "max_iter":              max_iter,
        "cycles":                cycles,
        "diverged":              int(diverged),
        "hw_loss":               f"{hw_loss:.6e}",
        "golden_loss":           f"{golden['loss']:.6e}",
        "max_abs_err_vs_golden": f"{max(ae_vs_golden):.4e}",
        "mean_abs_err_vs_golden": f"{float(np.mean(ae_vs_golden)):.4e}",
        "max_abs_err_vs_true":   f"{max(ae_vs_true):.4e}",
        "mean_abs_err_vs_true":  f"{float(np.mean(ae_vs_true)):.4e}",
    }
    for k in range(_MAX_DEGREE + 1):
        if k <= degree:
            row[f"true_{k}"]              = f"{true_coeffs[k]:.8f}"
            row[f"golden_{k}"]            = f"{golden_coeffs[k]:.8f}"
            row[f"hw_{k}"]                = f"{hw_coeffs[k]:.8f}"
            row[f"abs_err_vs_golden_{k}"] = f"{ae_vs_golden[k]:.4e}"
            row[f"abs_err_vs_true_{k}"]   = f"{ae_vs_true[k]:.4e}"
        else:
            row[f"true_{k}"]              = ""
            row[f"golden_{k}"]            = ""
            row[f"hw_{k}"]                = ""
            row[f"abs_err_vs_golden_{k}"] = ""
            row[f"abs_err_vs_true_{k}"]   = ""
    random_results_collector.append(row)
