"""
Generate summary plots from a completed make test-random run.

Usage:
    python utils/plot_random_results.py <results_dir>

Reads:
    <results_dir>/random_summary.csv

Writes:
    <results_dir>/plots/random_test_analysis.png   (4-panel overview)
    <results_dir>/plots/error_heatmap.png          (degree x format heatmap)
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
import matplotlib.colors as mcolors


# ── Colour scheme consistent with the four FP formats ─────────────────────────
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


def load_summary(csv_path: Path) -> list[dict]:
    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))
    # Cast numeric columns
    for row in rows:
        row["degree"]                 = int(row["degree"])
        row["test_idx"]               = int(row["test_idx"])
        row["cycles"]                 = int(row["cycles"])
        row["hw_loss"]                = _float(row["hw_loss"])
        row["golden_loss"]            = _float(row["golden_loss"])
        row["max_abs_err_vs_golden"]  = _float(row["max_abs_err_vs_golden"])
        row["mean_abs_err_vs_golden"] = _float(row["mean_abs_err_vs_golden"])
        row["max_abs_err_vs_true"]    = _float(row["max_abs_err_vs_true"])
        row["mean_abs_err_vs_true"]   = _float(row["mean_abs_err_vs_true"])
    return rows


def group_by(rows: list[dict], *keys) -> dict:
    """Group rows into nested dicts keyed by the given field names."""
    result: dict = defaultdict(list)
    for row in rows:
        key = tuple(row[k] for k in keys)
        result[key].append(row)
    return dict(result)


# ── Plot helpers ──────────────────────────────────────────────────────────────

def _safe_log(values: list[float]) -> list[float]:
    return [math.log10(v) if v > 0 and not math.isnan(v) else float("nan")
            for v in values]


def _median_by_degree(rows_by_fmt_deg: dict, fmt: str, metric: str) -> tuple[list, list]:
    """Return (sorted degrees, median metric per degree) for one format."""
    by_deg: dict[int, list[float]] = defaultdict(list)
    for (f, d), rows in rows_by_fmt_deg.items():
        if f != fmt:
            continue
        for row in rows:
            val = row[metric]
            if not math.isnan(val):
                by_deg[d].append(val)
    degrees = sorted(by_deg)
    medians = [float(np.median(by_deg[d])) for d in degrees]
    return degrees, medians


# ── Figure 1: 4-panel overview ────────────────────────────────────────────────

def plot_overview(rows: list[dict], out_path: Path) -> None:
    rows_by_fmt_deg = group_by(rows, "format", "degree")
    fmts = [f for f in FORMAT_ORDER if any(r["format"] == f for r in rows)]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle("Random Polynomial Regression — FP Format Comparison", fontsize=14)

    # ── Panel 1: HW loss vs polynomial degree ─────────────────────────────
    ax = axes[0, 0]
    for fmt in fmts:
        color = FORMAT_COLORS[fmt]
        # Scatter all individual points
        xs, ys = [], []
        for row in rows:
            if row["format"] == fmt and not math.isnan(row["hw_loss"]):
                xs.append(row["degree"])
                ys.append(row["hw_loss"])
        if xs:
            ax.scatter(xs, ys, color=color, alpha=0.35, s=20)
        # Median trend line
        degs, meds = _median_by_degree(rows_by_fmt_deg, fmt, "hw_loss")
        if degs:
            ax.plot(degs, meds, "o-", color=color, label=fmt, linewidth=2, markersize=5)
    ax.set_yscale("log")
    ax.set_xlabel("Polynomial Degree")
    ax.set_ylabel("HW Loss (MSE, log scale)")
    ax.set_title("HW Training Loss vs Degree")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, which="both")
    ax.set_xticks(sorted({r["degree"] for r in rows}))

    # ── Panel 2: Mean |coeff error vs golden| vs degree ───────────────────
    ax = axes[0, 1]
    for fmt in fmts:
        color = FORMAT_COLORS[fmt]
        xs, ys = [], []
        for row in rows:
            if row["format"] == fmt and not math.isnan(row["mean_abs_err_vs_golden"]):
                xs.append(row["degree"])
                ys.append(row["mean_abs_err_vs_golden"])
        if xs:
            ax.scatter(xs, ys, color=color, alpha=0.35, s=20)
        degs, meds = _median_by_degree(rows_by_fmt_deg, fmt, "mean_abs_err_vs_golden")
        if degs:
            ax.plot(degs, meds, "o-", color=color, label=fmt, linewidth=2, markersize=5)
    ax.set_yscale("log")
    ax.set_xlabel("Polynomial Degree")
    ax.set_ylabel("Mean |Coeff Error vs Golden| (log scale)")
    ax.set_title("Coefficient Error vs FP64 Golden")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, which="both")
    ax.set_xticks(sorted({r["degree"] for r in rows}))

    # ── Panel 3: Mean |coeff error vs true| vs degree ─────────────────────
    ax = axes[1, 0]
    for fmt in fmts:
        color = FORMAT_COLORS[fmt]
        xs, ys = [], []
        for row in rows:
            if row["format"] == fmt and not math.isnan(row["mean_abs_err_vs_true"]):
                xs.append(row["degree"])
                ys.append(row["mean_abs_err_vs_true"])
        if xs:
            ax.scatter(xs, ys, color=color, alpha=0.35, s=20)
        degs, meds = _median_by_degree(rows_by_fmt_deg, fmt, "mean_abs_err_vs_true")
        if degs:
            ax.plot(degs, meds, "o-", color=color, label=fmt, linewidth=2, markersize=5)
    ax.set_yscale("log")
    ax.set_xlabel("Polynomial Degree")
    ax.set_ylabel("Mean |Coeff Error vs True| (log scale)")
    ax.set_title("Coefficient Recovery Error vs True Coefficients")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, which="both")
    ax.set_xticks(sorted({r["degree"] for r in rows}))

    # ── Panel 4: Format comparison — box plots of HW loss ─────────────────
    ax = axes[1, 1]
    loss_by_fmt = {fmt: [] for fmt in fmts}
    for row in rows:
        if not math.isnan(row["hw_loss"]):
            loss_by_fmt[row["format"]].append(row["hw_loss"])
    bp_data   = [loss_by_fmt[f] for f in fmts]
    bp_colors = [FORMAT_COLORS[f] for f in fmts]
    bp = ax.boxplot(bp_data, labels=fmts, patch_artist=True, notch=False)
    for patch, color in zip(bp["boxes"], bp_colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax.set_yscale("log")
    ax.set_xlabel("FP Format")
    ax.set_ylabel("HW Loss (MSE, log scale)")
    ax.set_title("Loss Distribution per Format (all degrees)")
    ax.grid(True, alpha=0.3, axis="y", which="both")

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved overview plot → {out_path}")


# ── Figure 2: degree × format heatmap ────────────────────────────────────────

def _build_matrix(rows: list[dict], fmts: list[str], degrees: list[int],
                  metric: str) -> np.ndarray:
    """Build a (degrees × formats) matrix of median values for one metric."""
    mat = np.full((len(degrees), len(fmts)), float("nan"))
    for di, deg in enumerate(degrees):
        for fi, fmt in enumerate(fmts):
            vals = [
                r[metric] for r in rows
                if r["format"] == fmt and r["degree"] == deg
                and not math.isnan(r[metric])
            ]
            if vals:
                mat[di, fi] = float(np.median(vals))
    return mat


def _log_matrix(mat: np.ndarray) -> np.ndarray:
    return np.where((mat > 0) & ~np.isnan(mat), np.log10(mat), float("nan"))


def _draw_heatmap(ax, data: np.ndarray, fmts: list[str], degrees: list[int],
                  title: str, cbar_label: str) -> None:
    valid = data[~np.isnan(data)]
    vmin = float(np.min(valid)) if len(valid) else -10
    vmax = float(np.max(valid)) if len(valid) else 0
    im = ax.imshow(data, aspect="auto", cmap="RdYlGn_r", vmin=vmin, vmax=vmax)
    ax.set_xticks(range(len(fmts)))
    ax.set_xticklabels(fmts, rotation=30, ha="right")
    ax.set_yticks(range(len(degrees)))
    ax.set_yticklabels([f"deg {d}" for d in degrees])
    ax.set_xlabel("FP Format")
    ax.set_ylabel("Polynomial Degree")
    ax.set_title(title)
    plt.colorbar(im, ax=ax, label=cbar_label, fraction=0.046, pad=0.04)
    for di in range(len(degrees)):
        for fi in range(len(fmts)):
            val = data[di, fi]
            if not math.isnan(val):
                color = "white" if abs(val - (vmin + vmax) / 2) > (vmax - vmin) * 0.25 else "black"
                ax.text(fi, di, f"{val:.1f}", ha="center", va="center",
                        fontsize=7, color=color)


def plot_heatmap(rows: list[dict], out_path: Path) -> None:
    fmts    = [f for f in FORMAT_ORDER if any(r["format"] == f for r in rows)]
    degrees = sorted({r["degree"] for r in rows})

    loss_mat = _build_matrix(rows, fmts, degrees, "hw_loss")
    err_mat  = _build_matrix(rows, fmts, degrees, "mean_abs_err_vs_golden")

    fig, axes = plt.subplots(1, 2, figsize=(14, max(4, len(degrees) * 0.6 + 2)))
    fig.suptitle("Degree × Format Heatmaps", fontsize=13)

    _draw_heatmap(axes[0], _log_matrix(loss_mat), fmts, degrees,
                  "Median HW Loss (log₁₀ MSE)", "log₁₀(MSE)")
    _draw_heatmap(axes[1], _log_matrix(err_mat), fmts, degrees,
                  "Median Coeff Error vs Golden (log₁₀)", "log₁₀(mean|err|)")

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved heatmap plot      → {out_path}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main(results_dir: Path) -> None:
    csv_path = results_dir / "random_summary.csv"
    if not csv_path.exists():
        print(f"No summary CSV found at {csv_path}; skipping plots.")
        return

    rows = load_summary(csv_path)
    if not rows:
        print("Summary CSV is empty; skipping plots.")
        return

    plots_dir = results_dir / "plots"
    print(f"Loaded {len(rows)} result rows — generating plots in {plots_dir}/")

    plot_overview(rows, plots_dir / "random_test_analysis.png")
    plot_heatmap(rows,  plots_dir / "error_heatmap.png")

    print("Done.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <results_dir>")
        sys.exit(1)
    main(Path(sys.argv[1]))
