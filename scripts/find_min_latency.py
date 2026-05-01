#!/usr/bin/env python3
"""
Binary-search the minimum FMA_LATENCY that meets timing for each FP format.

Usage:
    python3 scripts/find_min_latency.py [--max-latency N]

Calls Vivado directly via synthesize.tcl so FMA_LATENCY can be varied freely.
Results land in synth/vivado/results_<FORMAT>/ and are overwritten each run.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (script lives in scripts/, project root is one level up)
# ---------------------------------------------------------------------------
PROJ_ROOT   = Path(__file__).resolve().parent.parent
SYNTH_SCRIPT = PROJ_ROOT / "scripts" / "synthesize.tcl"
SYNTH_DIR   = PROJ_ROOT / "synth" / "vivado"
VIVADO      = "vivado"

# fpnew_pkg::fp_format_e encoding → results directory name
FORMATS = [
    ("FP16",    2),
    ("FP16ALT", 4),
    ("FP32",    0),
    ("FP64",    1),
]

DEFAULT_MAX_LATENCY = 16
MIN_LATENCY         = 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_synth(fp_format_num: int, fma_latency: int) -> bool:
    """Invoke Vivado synthesis. Returns True on clean exit."""
    cmd = [
        VIVADO, "-mode", "batch",
        "-source", str(SYNTH_SCRIPT),
        "-tclargs",
        f"FP_FORMAT={fp_format_num}",
        f"FMA_LATENCY={fma_latency}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(PROJ_ROOT))
    return result.returncode == 0


def read_wns(format_name: str) -> float | None:
    """Return WNS (ns) for CLK100MHZ from the post-synthesis timing report."""
    rpt = SYNTH_DIR / f"results_{format_name}" / "timing_post_synth.rpt"
    if not rpt.exists():
        return None
    text = rpt.read_text()
    # Intra-clock table row: "CLK100MHZ  <WNS>  <TNS> ..."
    m = re.search(r"^CLK100MHZ\s+([-\d.]+)", text, re.MULTILINE)
    return float(m.group(1)) if m else None


# ---------------------------------------------------------------------------
# Binary search
# ---------------------------------------------------------------------------

def search_format(format_name: str, fp_format_num: int, max_latency: int) -> dict:
    """
    Find the minimum FMA_LATENCY in [MIN_LATENCY, max_latency] where timing passes
    (WNS >= 0).  Returns a result dict.
    """
    print(f"\n{'='*62}")
    print(f"  Searching {format_name}  (FP_FORMAT={fp_format_num})")
    print(f"  Latency range: [{MIN_LATENCY}, {max_latency}]")
    print(f"{'='*62}")

    lo, hi      = MIN_LATENCY, max_latency
    min_passing = None   # lowest latency that passes timing
    best_fail   = None   # (wns, latency) best among all failing runs

    while lo <= hi:
        mid = (lo + hi) // 2
        print(f"\n  [ latency={mid:2d} ]  running synthesis ...", flush=True)

        if not run_synth(fp_format_num, mid):
            print(f"  [ latency={mid:2d} ]  ERROR: Vivado exited non-zero — skipping")
            lo = mid + 1
            continue

        wns = read_wns(format_name)
        if wns is None:
            print(f"  [ latency={mid:2d} ]  ERROR: could not parse WNS — skipping")
            lo = mid + 1
            continue

        if wns >= 0.0:
            print(f"  [ latency={mid:2d} ]  PASS  WNS = +{wns:.3f} ns")
            min_passing = mid
            hi = mid - 1       # search for a lower passing latency
        else:
            print(f"  [ latency={mid:2d} ]  FAIL  WNS = {wns:.3f} ns")
            if best_fail is None or wns > best_fail[0]:
                best_fail = (wns, mid)
            lo = mid + 1       # need more pipeline stages

    return {
        "format":              format_name,
        "min_passing_latency": min_passing,
        "best_fail":           best_fail,   # (wns, latency) or None
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-latency", type=int, default=DEFAULT_MAX_LATENCY,
        help=f"Upper bound for binary search (default: {DEFAULT_MAX_LATENCY})"
    )
    parser.add_argument(
        "--formats", nargs="+", choices=[f for f, _ in FORMATS],
        help="Restrict search to specific formats (default: all)"
    )
    args = parser.parse_args()

    target_formats = (
        [(f, n) for f, n in FORMATS if f in args.formats]
        if args.formats else FORMATS
    )

    results = [
        search_format(name, num, args.max_latency)
        for name, num in target_formats
    ]

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print(f"\n{'='*62}")
    print("  SUMMARY")
    print(f"{'='*62}")
    all_pass = True
    for r in results:
        fmt = r["format"]
        if r["min_passing_latency"] is not None:
            print(f"  {fmt:10s}  MEETS TIMING  min FMA_LATENCY = {r['min_passing_latency']}")
        else:
            all_pass = False
            if r["best_fail"] is not None:
                wns, lat = r["best_fail"]
                print(
                    f"  {fmt:10s}  NO PASSING LATENCY found  "
                    f"(best WNS = {wns:.3f} ns at FMA_LATENCY = {lat})"
                )
            else:
                print(f"  {fmt:10s}  NO PASSING LATENCY found  (all runs errored)")

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
