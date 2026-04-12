"""
Generate $readmemh-compatible hex initialization files for simulation.

data_mem layout (one entry per sample address):
    bits [2*W-1 : W] = y_bits   (upper half)
    bits [W-1   : 0] = x_bits   (lower half)

  This matches the RTL: .rd_data({y_rd_data, x_rd_data})

coef_init.hex  -- POLY_DEGREE+1 entries, each W bits wide
grad_init.hex  -- POLY_DEGREE+1 zero entries (gradients start at 0)
data_mem.hex   -- NUM_SAMPLES entries, each 2*W bits wide
"""

import sys
from pathlib import Path
from typing import Sequence

import numpy as np

sys.path.insert(0, str(Path(__file__).parents[1]))
from utils.fp_formats import FPFormat, FORMATS


def write_data_mem(
    x: Sequence[float],
    y: Sequence[float],
    fmt: FPFormat,
    out_path: Path,
) -> None:
    """
    Write data_mem.hex.  Each line is one memory word: {y_bits, x_bits}.
    The word is 2*fmt.width bits, written as 2*fmt.hex_chars hex digits.
    """
    assert len(x) == len(y), "x and y must have the same length"
    word_hex_chars = 2 * fmt.hex_chars
    with open(out_path, 'w') as f:
        for xi, yi in zip(x, y):
            x_bits = fmt.encode(float(xi))
            y_bits = fmt.encode(float(yi))
            word = (y_bits << fmt.width) | x_bits
            f.write(f"{word:0{word_hex_chars}x}\n")


def write_coef_init(
    initial_coeffs: Sequence[float],
    fmt: FPFormat,
    out_path: Path,
) -> None:
    """
    Write coef_init.hex.  One coefficient per line, fmt.width bits each.
    The values must match the Python golden model's _initialize_memories()
    (np.random.seed(42); randn * 0.01) so the DUT starts from the same point.
    """
    with open(out_path, 'w') as f:
        for c in initial_coeffs:
            f.write(fmt.hex_str(float(c)) + '\n')


def write_grad_init(n_coeffs: int, fmt: FPFormat, out_path: Path) -> None:
    """Write grad_init.hex: all zeros (gradients accumulate from zero)."""
    zero = '0' * fmt.hex_chars
    with open(out_path, 'w') as f:
        for _ in range(n_coeffs):
            f.write(zero + '\n')


def generate_all(
    x: np.ndarray,
    y: np.ndarray,
    initial_coeffs: np.ndarray,
    output_dir: Path,
) -> dict:
    """
    Generate hex init files for all four FP formats under output_dir/.

    Returns:
        {
          "FP64":    {"data_mem": Path, "coef_init": Path, "grad_init": Path},
          "FP32":    {...},
          "FP16":    {...},
          "FP16ALT": {...},
        }
    """
    n_coeffs = len(initial_coeffs)
    result = {}

    for fmt in FORMATS.values():
        fmt_dir = output_dir / fmt.name
        fmt_dir.mkdir(parents=True, exist_ok=True)

        data_path = fmt_dir / "data_mem.hex"
        coef_path = fmt_dir / "coef_init.hex"
        grad_path = fmt_dir / "grad_init.hex"

        write_data_mem(x, y, fmt, data_path)
        write_coef_init(initial_coeffs, fmt, coef_path)
        write_grad_init(n_coeffs, fmt, grad_path)

        result[fmt.name] = {
            "data_mem": data_path,
            "coef_init": coef_path,
            "grad_init": grad_path,
        }

    return result
