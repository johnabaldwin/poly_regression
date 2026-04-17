
from cocotb_tools.runner import get_runner
from pathlib import Path
import os

TB = Path("/home/john/poly_regression/tb/cocotb")
REPO = Path("/home/john/poly_regression")

def src(r): return REPO / r
sources = [
    src("external/fpnew/src/common_cells/src/lzc.sv"),
    src("external/fpnew/src/common_cells/src/rr_arb_tree.sv"),
    src("external/fpnew/src/fpnew_pkg.sv"),
    src("external/fpnew/src/fpnew_pipe_in.sv"),
    src("external/fpnew/src/fpnew_pipe_inside_fma.sv"),
    src("external/fpnew/src/fpnew_pipe_inside_cast.sv"),
    src("external/fpnew/src/fpnew_pipe_out.sv"),
    src("external/fpnew/src/fpnew_classifier.sv"),
    src("external/fpnew/src/fpnew_rounding.sv"),
    src("external/fpnew/src/fpnew_fma.sv"),
    src("external/fpnew/src/fpnew_fma_multi.sv"),
    src("external/fpnew/src/fpnew_f2fcast.sv"),
    src("external/fpnew/src/fpnew_f2icast.sv"),
    src("external/fpnew/src/fpnew_i2fcast.sv"),
    src("external/fpnew/src/fpnew_cast_multi.sv"),
    src("external/fpnew/src/fpnew_noncomp.sv"),
    src("external/fpnew/src/fpu_div_sqrt_mvp/hdl/defs_div_sqrt_mvp.sv"),
    src("external/fpnew/src/fpu_div_sqrt_mvp/hdl/preprocess_mvp.sv"),
    src("external/fpnew/src/fpu_div_sqrt_mvp/hdl/iteration_div_sqrt_mvp.sv"),
    src("external/fpnew/src/fpu_div_sqrt_mvp/hdl/nrbd_nrsc_mvp.sv"),
    src("external/fpnew/src/fpu_div_sqrt_mvp/hdl/norm_div_sqrt_mvp.sv"),
    src("external/fpnew/src/fpu_div_sqrt_mvp/hdl/control_mvp.sv"),
    src("external/fpnew/src/fpu_div_sqrt_mvp/hdl/div_sqrt_top_mvp.sv"),
    src("external/fpnew/src/fpu_div_sqrt_mvp/hdl/div_sqrt_mvp_wrapper.sv"),
    src("external/fpnew/src/fpnew_divsqrt_multi.sv"),
    src("external/fpnew/src/fpnew_opgroup_fmt_slice.sv"),
    src("external/fpnew/src/fpnew_opgroup_multifmt_slice.sv"),
    src("external/fpnew/src/fpnew_opgroup_block.sv"),
    src("external/fpnew/src/fpnew_top.sv"),
    src("rtl/common/register.sv"),
    src("rtl/memory/ram_sdp.sv"),
    src("rtl/memory/register_file.sv"),
    src("rtl/fp_formats/fp_madd.sv"),
    src("rtl/fp_formats/fp_power.sv"),
    src("rtl/algorithm/forward_pass.sv"),
    src("rtl/algorithm/reverse_pass.sv"),
    src("rtl/algorithm/control.sv"),
    src("rtl/top/poly_regression.sv"),
]

import struct
alpha_2m = 0.01*2/50
alpha_bits = struct.unpack("Q", struct.pack("d", alpha_2m))[0]

runner = get_runner("verilator")
runner.build(
    sources=sources,
    hdl_toplevel="poly_regression",
    parameters={
        "FP_FORMAT": 1,
        "POLY_DEGREE": 3,
        "NUM_SAMPLES": 50,
        "MAX_ITERATIONS": 1,
        "ALPHA_2M": f"64\'h{alpha_bits:016X}",
        "DATA_MEM_INIT": f'"{REPO}/data/FP64/data_mem.hex"',
        "COEF_MEM_INIT": f'"{REPO}/data/FP64/coef_init.hex"',
        "GRAD_MEM_INIT": f'"{REPO}/data/FP64/grad_init.hex"',
    },
    build_args=[
        "--public-flat-rw", "--trace", "--trace-structs",
        "-Wno-WIDTHEXPAND", "-Wno-WIDTHTRUNC", "-Wno-UNUSED", "-Wno-UNOPTFLAT",
        "-Wno-DECLFILENAME", "-Wno-CASEOVERLAP", "-Wno-PINMISSING", "-Wno-ENUMVALUE", "-Wno-ASCRANGE",
        f"-I{REPO}/external/fpnew/src",
        f"-I{REPO}/external/fpnew/src/common_cells/include",
    ],
    build_dir=TB/"sim_build_diag",
    always=True,
)
runner.test(
    hdl_toplevel="poly_regression",
    test_module="test_diag",
    build_dir=TB/"sim_build_diag",
    extra_env={
        "TB_FP_FORMAT": "FP64", "TB_FP_WIDTH": "64",
        "TB_POLY_DEGREE": "3",
        "TB_RESULTS_FILE": str(TB/"results_diag.json"),
        "PYTHONPATH": str(TB),
    },
)
