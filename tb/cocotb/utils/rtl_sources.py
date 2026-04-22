"""
RTL source list and Verilator build flags shared by all cocotb testbenches.
"""

from pathlib import Path

_TB_COCOTB_DIR = Path(__file__).parents[1]
_REPO_ROOT     = _TB_COCOTB_DIR.parents[1]


def _src(rel: str) -> Path:
    return _REPO_ROOT / rel


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
    # div/sqrt MVP
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

VERILATOR_BUILD_ARGS = [
    "--public-flat-rw",
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
    f"-I{_REPO_ROOT}/external/fpnew/src",
    f"-I{_REPO_ROOT}/external/fpnew/src/common_cells/include",
]
