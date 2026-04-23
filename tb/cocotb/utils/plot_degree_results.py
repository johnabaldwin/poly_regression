"""
Generate summary plots from a completed make test-degree run.

Usage:
    python utils/plot_degree_results.py <results_dir>

Reads:
    <results_dir>/summary.csv

Writes:
    <results_dir>/plots/coeff_errors.png     (per-coefficient error vs true & golden)
    <results_dir>/plots/loss_comparison.png  (total loss: distribution & hw vs golden)
"""

import sys
import csv
import math
from pathlib import Path
from collections import defaultdict

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FORMAT_COLORS = {
    "FP64":    "#1f77b4",
    "FP32":    "#ff7f0e",
    "FP16":    "#2ca02c",
    "FP16ALT": "#d62728",
}
FORMAT_ORDER = ["FP64", "FP32", "FP16", "FP16ALT"]


# ── CSV helpers ───────────────────────────────────────────────────────────────

def _float(s: str) -> float:
    try:
        return float(s)
    except (ValueError, TypeError):
        return float("nan")


def load_summary(csv_path: Path) -> tuple[list[dict], int]:
    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return [], 0
    degree = int(rows[0]["degree"])
    for row in rows:
        row["degree"]      = int(row["degree"])
        row["test_idx"]    = int(row["test_idx"])
        row["cycles"]      = int(row["cycles"])
        row["hw_loss"]     = _float(row["hw_loss"])
        row["golden_loss"] = _float(row["golden_loss"])
        for k in range(degree + 1):
            row[f"abs_err_vs_golden_{k}"] = _float(row.get(f"abs_err_vs_golden_{k}", ""))
            row[f"abs_err_vs_true_{k}"]   = _float(row.get(f"abs_err_vs_true_{k}", ""))
    return rows, degree


# ── Plot 1: per-coefficient errors ────────────────────────────────────────────

def plot_coeff_errors(rows: list[dict], degree: int, fmts: list[str],
                      out_path: Path) -> None:
    """Two side-by-side panels: |hw − true| and |hw − golden| per coefficient."""
    coeff_idxs = list(range(degree + 1))
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(f"Per-Coefficient Error — Degree {degree}", fontsize=13)

    panels = [
        ("abs_err_vs_true",   "Coefficient Recovery Error vs True Coefficients",
         "| HW − True | (log scale)"),
        ("abs_err_vs_golden", "Coefficient Error vs FP64 Golden Model",
         "| HW − Golden | (log scale)"),
    ]

    for ax, (metric, title, ylabel) in zip(axes, panels):
        for fmt in fmts:
            color     = FORMAT_COLORS[fmt]
            fmt_rows  = [r for r in rows if r["format"] == fmt]
            medians   = []

            for k in coeff_idxs:
                col  = f"{metric}_{k}"
                vals = [r[col] for r in fmt_rows
                        if not math.isnan(r[col]) and r[col] > 0]
                if vals:
                    ax.scatter([k] * len(vals), vals,
                               color=color, alpha=0.35, s=20, zorder=2)
                medians.append(float(np.median(vals)) if vals else float("nan"))

            valid = [(k, m) for k, m in zip(coeff_idxs, medians)
                     if not math.isnan(m) and m > 0]
            if valid:
                kx, ky = zip(*valid)
                ax.plot(kx, ky, "o-", color=color, label=fmt,
                        linewidth=2, markersize=5, zorder=3)

        ax.set_yscale("log")
        ax.set_xticks(coeff_idxs)
        ax.set_xticklabels([f"a[{k}]" for k in coeff_idxs])
        ax.set_xlabel("Coefficient")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3, which="both")

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved coefficient error plot → {out_path}")


# ── Plot 2: total loss comparison ─────────────────────────────────────────────

def plot_loss_comparison(rows: list[dict], degree: int, fmts: list[str],
                         out_path: Path) -> None:
    """Left: hw/golden loss distributions per format.  Right: hw vs golden scatter."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(f"Total Loss Comparison — Degree {degree}", fontsize=13)

    # ── Panel 1: paired box plots — hw loss (colour) vs golden loss (grey) ──
    ax = axes[0]
    n_fmts = len(fmts)
    positions = list(range(n_fmts))
    hw_offset     = -0.22
    golden_offset =  0.22
    width         =  0.35

    legend_handles = []
    for i, fmt in enumerate(fmts):
        color     = FORMAT_COLORS[fmt]
        fmt_rows  = [r for r in rows if r["format"] == fmt]

        hw_vals = [r["hw_loss"] for r in fmt_rows
                   if not math.isnan(r["hw_loss"]) and not math.isinf(r["hw_loss"])
                   and r["hw_loss"] > 0]
        gd_vals = [r["golden_loss"] for r in fmt_rows
                   if not math.isnan(r["golden_loss"]) and not math.isinf(r["golden_loss"])
                   and r["golden_loss"] > 0]

        if hw_vals:
            bp = ax.boxplot(hw_vals, positions=[i + hw_offset], widths=width,
                            patch_artist=True, notch=False,
                            boxprops=dict(facecolor=color, alpha=0.75),
                            medianprops=dict(color="black", linewidth=1.5),
                            whiskerprops=dict(color=color),
                            capprops=dict(color=color),
                            flierprops=dict(marker="o", color=color, alpha=0.5, markersize=4))
            legend_handles.append(
                plt.Line2D([0], [0], color=color, linewidth=6, alpha=0.75, label=fmt)
            )
        if gd_vals:
            ax.boxplot(gd_vals, positions=[i + golden_offset], widths=width,
                       patch_artist=True, notch=False,
                       boxprops=dict(facecolor="#cccccc", alpha=0.85),
                       medianprops=dict(color="black", linewidth=1.5),
                       whiskerprops=dict(color="#888888"),
                       capprops=dict(color="#888888"),
                       flierprops=dict(marker="o", color="#888888", alpha=0.5, markersize=4))

    legend_handles.append(
        plt.Line2D([0], [0], color="#cccccc", linewidth=6, alpha=0.85, label="Golden (FP64 ref)")
    )
    ax.set_yscale("log")
    ax.set_xticks(positions)
    ax.set_xticklabels(fmts)
    ax.set_xlabel("FP Format")
    ax.set_ylabel("MSE Loss (log scale)")
    ax.set_title("HW Loss (colour) vs Golden Loss (grey)")
    ax.legend(handles=legend_handles, fontsize=8)
    ax.grid(True, alpha=0.3, axis="y", which="both")

    # ── Panel 2: hw_loss vs golden_loss scatter ──────────────────────────
    ax = axes[1]
    all_finite: list[float] = []
    for fmt in fmts:
        color = FORMAT_COLORS[fmt]
        xs, ys = [], []
        for r in rows:
            if r["format"] != fmt:
                continue
            gl, hl = r["golden_loss"], r["hw_loss"]
            if (math.isfinite(gl) and math.isfinite(hl) and gl > 0 and hl > 0):
                xs.append(gl)
                ys.append(hl)
                all_finite.extend([gl, hl])
        ax.scatter(xs, ys, color=color, label=fmt, alpha=0.75, s=45, zorder=3)

    if all_finite:
        mn, mx = min(all_finite), max(all_finite)
        pad = (mx / mn) ** 0.05
        ax.plot([mn / pad, mx * pad], [mn / pad, mx * pad],
                "k--", alpha=0.35, linewidth=1.2, label="y = x (perfect tracking)")

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Golden Loss — FP64 MSE")
    ax.set_ylabel("Hardware Loss — MSE")
    ax.set_title("HW Loss vs Golden Loss")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, which="both")

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved loss comparison plot   → {out_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main(results_dir: Path) -> None:
    csv_path = results_dir / "summary.csv"
    if not csv_path.exists():
        print(f"No summary CSV found at {csv_path}; skipping plots.")
        return

    rows, degree = load_summary(csv_path)
    if not rows:
        print("Summary CSV is empty; skipping plots.")
        return

    fmts      = [f for f in FORMAT_ORDER if any(r["format"] == f for r in rows)]
    plots_dir = results_dir / "plots"
    print(f"Loaded {len(rows)} result rows (degree {degree}) — generating plots in {plots_dir}/")

    plot_coeff_errors(rows, degree, fmts, plots_dir / "coeff_errors.png")
    plot_loss_comparison(rows, degree, fmts, plots_dir / "loss_comparison.png")
    print("Done.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <results_dir>")
        sys.exit(1)
    main(Path(sys.argv[1]))
