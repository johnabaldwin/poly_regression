# =============================================================================
# scripts/create_project.tcl  --  Create Vivado GUI project
#
# Creates a persistent Vivado project that can be opened in the GUI.
# Run once to set up the project; afterwards open the .xpr directly.
#
# Usage (from project root):
#   vivado -mode batch -source scripts/create_project.tcl
#
# Override defaults via tclargs:
#   vivado -mode batch -source scripts/create_project.tcl \
#          -tclargs FP_FORMAT=0 POLY_DEGREE=3 NUM_SAMPLES=100
#
# After this script completes, open the project with:
#   vivado synth/vivado/vivado_project/poly_regression.xpr
# Top module is mfp_nexys4_ddr; generics flow through to poly_regression.
# =============================================================================

set script_dir [file normalize [file dirname [info script]]]
set proj_root  [file normalize "$script_dir/.."]

# =============================================================================
# Settings
# =============================================================================
set part         "xc7a100tcsg324-1"   ;# Nexys A7-100T
set proj_name    "poly_regression"
set proj_dir     "$proj_root/synth/vivado/vivado_project"

# Design generics (fpnew_pkg::fp_format_e: 0=FP32, 1=FP64, 2=FP16, 4=FP16ALT)
set FP_FORMAT      0
set POLY_DEGREE    3
set FMA_LATENCY    2
set NUM_SAMPLES    100
set MAX_ITERATIONS 1000
# ALPHA_2M = alpha/(2*NUM_SAMPLES) as FP32 hex bits.
# Compute: python3 -c "import struct; print(struct.pack('>f', ALPHA/(2*N)).hex())"
# Default 38d1eb85 = 5.0e-5  (alpha=0.01, N=100)
set ALPHA_2M_HEX   "38d1eb85"

# Parse tclargs overrides (key=value)
if { [info exists argv] && [llength $argv] > 0 } {
    foreach arg $argv {
        if { [regexp {^([A-Za-z_][A-Za-z0-9_]*)=(.+)$} $arg -> key val] } {
            set $key $val
        }
    }
}

# =============================================================================
# Derived paths
# =============================================================================
set fpnew_root "$proj_root/external/fpnew"
set cc_src     "$fpnew_root/src/common_cells/src"
set rtl        "$proj_root/rtl"
set constraints_dir "$proj_root/synth/vivado/constraints"

# =============================================================================
# Create project
# =============================================================================
puts "Creating project: $proj_name in $proj_dir"
create_project $proj_name $proj_dir -part $part -force

set_property target_language  SystemVerilog [current_project]
set_property simulator_language Mixed       [current_project]
set_property default_lib       work         [current_project]

# =============================================================================
# Add source files
# =============================================================================

# 1. FPnew package (must elaborate first)
add_files -norecurse "$fpnew_root/src/fpnew_pkg.sv"

# 2. common_cells (FPnew internal dependencies)
set cc_files {
    lzc.sv
    rr_arb_tree.sv
    shift_reg.sv
    spill_register.sv
    fall_through_register.sv
    fifo_v3.sv
    stream_register.sv
    stream_mux.sv
    stream_demux.sv
    stream_fork.sv
    stream_filter.sv
    sync.sv
    sync_wedge.sv
    popcount.sv
    onehot_to_bin.sv
    rstgen.sv
    rstgen_bypass.sv
    counter.sv
}
foreach f $cc_files {
    set path "$cc_src/$f"
    if { [file exists $path] } {
        add_files -norecurse $path
    } else {
        puts "WARNING: common_cells/$f not found, skipping"
    }
}

# 3. FPnew core modules
set fpnew_files {
    fpnew_classifier.sv
    fpnew_rounding.sv
    fpnew_pipe_in.sv
    fpnew_pipe_out.sv
    fpnew_pipe_inside_fma.sv
    fpnew_pipe_inside_cast.sv
    fpnew_fma.sv
    fpnew_fma_multi.sv
    fpnew_noncomp.sv
    fpnew_f2fcast.sv
    fpnew_f2icast.sv
    fpnew_i2fcast.sv
    fpnew_cast_multi.sv
    fpnew_divsqrt_multi.sv
    fpnew_opgroup_fmt_slice.sv
    fpnew_opgroup_multifmt_slice.sv
    fpnew_opgroup_block.sv
    fpnew_top.sv
}
foreach f $fpnew_files {
    set path "$fpnew_root/src/$f"
    if { [file exists $path] } {
        add_files -norecurse $path
    } else {
        puts "WARNING: fpnew/$f not found, skipping"
    }
}

# 4. Project RTL
set rtl_files [list \
    "$rtl/common/register.sv" \
    "$rtl/fp_formats/fp_madd.sv" \
    "$rtl/fp_formats/fp_power.sv" \
    "$rtl/memory/ram_sdp.sv" \
    "$rtl/memory/register_file.sv" \
    "$rtl/algorithm/control.sv" \
    "$rtl/algorithm/forward_pass.sv" \
    "$rtl/algorithm/reverse_pass.sv" \
    "$rtl/top/poly_regression.sv" \
]
foreach f $rtl_files {
    add_files -norecurse $f
}
add_files -norecurse "$rtl/top/mfp_nexys4_ddr.v"

# Mark all added sources as SystemVerilog
set_property file_type {SystemVerilog} [get_files *.sv]

# Set the include path so Vivado can find common_cells headers
set_property include_dirs [list $cc_src "$rtl/common"] [current_fileset]

# =============================================================================
# Constraints
# =============================================================================
# Add constraint files when they are created.  Vivado will show a warning if
# the directory does not exist, so only add if files are present.
if { [file exists "$constraints_dir/nexys_a7.xdc"] } {
    add_files -fileset constrs_1 -norecurse "$constraints_dir/nexys_a7.xdc"
}
if { [file exists "$constraints_dir/timing.xdc"] } {
    add_files -fileset constrs_1 -norecurse "$constraints_dir/timing.xdc"
}

# =============================================================================
# Set top module and generics
# =============================================================================
set_property top mfp_nexys4_ddr [current_fileset]

# Generics are set on the synthesis run so the GUI picks them up automatically.
set_property generic [list \
    FP_FORMAT=$FP_FORMAT \
    POLY_DEGREE=$POLY_DEGREE \
    FMA_LATENCY=$FMA_LATENCY \
    NUM_SAMPLES=$NUM_SAMPLES \
    MAX_ITERATIONS=$MAX_ITERATIONS \
    DATA_MEM_INIT="" \
    COEF_MEM_INIT="" \
    GRAD_MEM_INIT="" \
    "ALPHA_2M=32'h${ALPHA_2M_HEX}" \
] [get_runs synth_1]

update_compile_order -fileset sources_1

# =============================================================================
# Done
# =============================================================================
puts ""
puts "=== Project created ==="
puts "Open in GUI:  vivado $proj_dir/$proj_name.xpr"
puts "Or run:       make synth  (batch synthesis)"
