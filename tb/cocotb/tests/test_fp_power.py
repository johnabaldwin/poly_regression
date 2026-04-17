"""
pytest runner for the fp_power unit test.

Builds fp_power (with only the sources it needs) and runs the cocotb
coroutine in test_fp_power_run.py for FP64 by default.

Usage:
    make test-fp-power               # FP64
    make test-fp-power FMT=FP32      # override format
    pytest tests/test_fp_power.py -v # direct pytest
"""

import os
import sys
from pathlib import Path

import pytest
from cocotb_tools.runner import get_runner

TB_COCOTB_DIR = Path(__file__).parents[1]
REPO_ROOT     = TB_COCOTB_DIR.parents[1]

sys.path.insert(0, str(TB_COCOTB_DIR))
from utils.fp_formats import FORMATS

# ── RTL sources ───────────────────────────────────────────────────────────────
# Only the files fp_power actually needs — keeps elaboration fast.

def _src(rel: str) -> Path:
    return REPO_ROOT / rel

FP_POWER_SOURCES = [
    # FPnew common cells (used by lzc inside fpnew_fma)
    _src("external/fpnew/src/common_cells/src/lzc.sv"),
    _src("external/fpnew/src/common_cells/src/rr_arb_tree.sv"),
    # FPnew package — must come first
    _src("external/fpnew/src/fpnew_pkg.sv"),
    # FPnew FMA pipeline stages
    _src("external/fpnew/src/fpnew_pipe_in.sv"),
    _src("external/fpnew/src/fpnew_pipe_inside_fma.sv"),
    _src("external/fpnew/src/fpnew_pipe_out.sv"),
    # FPnew FMA core
    _src("external/fpnew/src/fpnew_classifier.sv"),
    _src("external/fpnew/src/fpnew_rounding.sv"),
    _src("external/fpnew/src/fpnew_fma.sv"),
    # Project RTL
    _src("rtl/fp_formats/fp_madd.sv"),
    _src("rtl/fp_formats/fp_power.sv"),
]

VERILATOR_BUILD_ARGS = [
    "--public-flat-rw",
    "-Wno-WIDTHEXPAND", "-Wno-WIDTHTRUNC", "-Wno-UNUSED",
    "-Wno-UNOPTFLAT", "-Wno-DECLFILENAME", "-Wno-CASEOVERLAP",
    "-Wno-PINMISSING", "-Wno-ENUMVALUE", "-Wno-ASCRANGE",
    f"-I{REPO_ROOT}/external/fpnew/src",
    f"-I{REPO_ROOT}/external/fpnew/src/common_cells/include",
]

MAX_DEGREE  = 3
FMA_LATENCY = 2


@pytest.mark.parametrize("fmt_name", ["FP64"])
def test_fp_power(fmt_name):
    fmt       = FORMATS[fmt_name]
    build_dir = TB_COCOTB_DIR / f"sim_build_fp_power_{fmt_name}"

    trace_enabled = os.environ.get("TB_TRACE", "0") == "1"

    runner = get_runner("verilator")
    runner.build(
        sources=FP_POWER_SOURCES,
        hdl_toplevel="fp_power",
        parameters={
            "FP_FORMAT":    fmt.enum_val,
            "MAX_DEGREE":   MAX_DEGREE,
            "FMA_LATENCY":  FMA_LATENCY,
        },
        build_args=VERILATOR_BUILD_ARGS,
        build_dir=build_dir,
        always=True,
        waves=trace_enabled,
    )

    runner.test(
        hdl_toplevel="fp_power",
        test_module="test_fp_power_run",
        build_dir=build_dir,
        extra_env={
            "TB_FP_FORMAT":  fmt_name,
            "TB_MAX_DEGREE": str(MAX_DEGREE),
            "PYTHONPATH":    str(TB_COCOTB_DIR),
        },
        waves=trace_enabled,
    )
