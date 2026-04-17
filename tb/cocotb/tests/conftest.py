"""
pytest session fixtures for the polynomial regression format comparison testbench.

Session flow (runs once across all parametrized format tests):
  1. Generate a single noisy dataset with a fixed seed.
  2. Run the Python FP64 golden model on it; capture reference coefficients.
  3. Derive the initial coefficient values the DUT will be loaded with.
  4. Encode and write $readmemh hex files for all four FP formats.
  5. Collect per-format hardware results and write a summary CSV at session end.
"""

import csv
import sys
from pathlib import Path

import numpy as np
import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
TB_COCOTB_DIR = Path(__file__).parents[1]
REPO_ROOT     = TB_COCOTB_DIR.parents[1]
SCRIPTS_DIR   = REPO_ROOT / "scripts"

sys.path.insert(0, str(TB_COCOTB_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from utils.generate_hex import generate_all
from poly_test import (
    HyperParameters,
    TrainingData,
    PolynomialRegressionHardware,
    generate_polynomial_data,
)
from tb_config import (
    POLY_DEGREE, NUM_SAMPLES, MAX_ITERATIONS, LEARNING_RATE,
    NOISE_STD, TRUE_COEFFS, X_RANGE,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def dataset() -> TrainingData:
    """Reproducible noisy polynomial dataset shared by all format tests."""
    np.random.seed(0)
    return generate_polynomial_data(
        true_coeffs=TRUE_COEFFS,
        x_range=X_RANGE,
        num_samples=NUM_SAMPLES,
        noise_std=NOISE_STD,
    )


@pytest.fixture(scope="session")
def initial_coeffs() -> np.ndarray:
    """
    Initial coefficient values written into coef_init.hex.

    Must exactly match PolynomialRegressionHardware._initialize_memories(),
    which does: np.random.seed(42); randn(n+1) * 0.01
    Both the DUT (via hex file) and the golden model start from these values.
    """
    np.random.seed(42)
    return np.random.randn(POLY_DEGREE + 1) * 0.01


@pytest.fixture(scope="session")
def golden_result(dataset: TrainingData) -> dict:
    """
    Python FP64 reference: train the golden model and capture its output.

    This is the baseline all hardware format outputs are compared against.
    The golden model uses the same initial coefficients (seed=42 inside
    _initialize_memories), same dataset, and same hyperparameters.
    """
    hp = HyperParameters(
        poly_degree=POLY_DEGREE,
        learning_rate=LEARNING_RATE,
        max_iterations=MAX_ITERATIONS,
    )
    model = PolynomialRegressionHardware(hp, dataset)
    model.train(verbose=False)
    fp_stats  = model.fp_unit.get_stats()
    total_ops = sum(fp_stats.values())
    return {
        "coefficients": model.get_coefficients().tolist(),
        "loss":         float(model.total_loss),
        "iterations":   model.iteration + 1,
        "fp_stats":     fp_stats,
        "total_fp_ops": total_ops,
        "mem_stats": {
            "x_reads":     model.data_memory_X.read_count,
            "y_reads":     model.data_memory_Y.read_count,
            "coef_reads":  model.coeff_memory.read_count,
            "coef_writes": model.coeff_memory.write_count,
            "grad_reads":  model.gradient_memory.read_count,
            "grad_writes": model.gradient_memory.write_count,
        },
    }


@pytest.fixture(scope="session")
def hex_data(dataset: TrainingData, initial_coeffs: np.ndarray) -> dict:
    """
    $readmemh hex files for all four FP formats, written to data/ in the repo.

    Files are deterministic (fixed seeds) so they are regenerated only when
    missing, keeping the same paths across runs for easy inspection.

    Returns:
        {
          "FP64":    {"data_mem": Path, "coef_init": Path, "grad_init": Path},
          "FP32":    {...},
          ...
        }
    """
    out_dir = REPO_ROOT / "data"
    return generate_all(dataset.X, dataset.Y, initial_coeffs, out_dir)


@pytest.fixture(scope="session")
def results_collector() -> list:
    """
    Accumulates one dict per format run; writes format_comparison.csv at the
    end of the session so all four runs contribute to a single table.
    """
    rows: list[dict] = []
    yield rows

    if not rows:
        return

    out_path = TB_COCOTB_DIR / "results" / "format_comparison.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nResults CSV → {out_path}")
