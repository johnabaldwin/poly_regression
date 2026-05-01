# =============================================================================
# scripts/synthesize.tcl  --  Standalone Vivado batch synthesis
#
# Usage (from project root):
#   vivado -mode batch -source scripts/synthesize.tcl
#
# Override parameters via tclargs:
#   vivado -mode batch -source scripts/synthesize.tcl \
#          -tclargs FP_FORMAT=0 POLY_DEGREE=5 NUM_SAMPLES=200
#
# ALPHA_2M is the scaled learning rate: alpha / (2 * NUM_SAMPLES).
# Encode as an FP32 bit pattern (hex, no prefix).  Example:
#   python3 -c "import struct; print(struct.pack('>f', 0.01/200).hex())"
#   => 38d1eb85   (5e-5, for alpha=0.01, N=100)
# =============================================================================

# Derive project root from this script's location so the script can be
# sourced from any working directory.
set script_dir [file normalize [file dirname [info script]]]
set proj_root  [file normalize "$script_dir/.."]

# =============================================================================
# Default parameters  (override via -tclargs key=value)
# =============================================================================
set part           "xc7a100tcsg324-1"   ;# Nexys A7-100T
set top_module     "mfp_nexys4_ddr"
set synth_dir      "$proj_root/synth/vivado"

# Design generics (fpnew_pkg::fp_format_e): 0=FP32, 1=FP64, 2=FP16, 4=FP16ALT
set FP_FORMAT      0
set POLY_DEGREE    3
set FMA_LATENCY    2
set NUM_SAMPLES    100
set MAX_ITERATIONS 1000
# ALPHA_2M: alpha/(2*NUM_SAMPLES) as FP32 hex bits (no 0x prefix).
# Default 38d1eb85 = 5.0e-5  (alpha=0.01, N=100)
set ALPHA_2M_HEX   "38d1eb85"

# Parse tclargs (key=value pairs appended after -tclargs)
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

# Map FP_FORMAT number to a human-readable name for directory naming
array set fp_format_names {0 FP32 1 FP64 2 FP16 4 FP16ALT}
if { [info exists fp_format_names($FP_FORMAT)] } {
    set format_name $fp_format_names($FP_FORMAT)
} else {
    set format_name "FP_FORMAT_${FP_FORMAT}"
}

set rpt_dir   "$synth_dir/results_${format_name}"
file mkdir $rpt_dir

puts "=== poly_regression Vivado Synthesis ==="
puts "Part:          $part"
puts "Top:           $top_module"
puts "Format:        $format_name (FP_FORMAT=$FP_FORMAT)"
puts "POLY_DEGREE:   $POLY_DEGREE"
puts "FMA_LATENCY:   $FMA_LATENCY"
puts "NUM_SAMPLES:   $NUM_SAMPLES"
puts "MAX_ITERATIONS:$MAX_ITERATIONS"
puts "ALPHA_2M:      0x$ALPHA_2M_HEX"
puts "Output:        $rpt_dir"
puts ""

# =============================================================================
# Read source files
# =============================================================================

# 1. FPnew package -- must be first (defines types used by all other modules)
puts "Reading FPnew package..."
read_verilog -sv "$fpnew_root/src/fpnew_pkg.sv"

# 2. common_cells -- support library used internally by FPnew
#    Only the non-deprecated, non-testbench sources that FPnew actually needs.
puts "Reading common_cells..."
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
        read_verilog -sv $path
    } else {
        puts "  WARNING: $f not found, skipping"
    }
}

# 3. FPnew core modules (dependency order: leaves before composites)
puts "Reading FPnew core..."
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
        read_verilog -sv $path
    } else {
        puts "  WARNING: $f not found, skipping"
    }
}

# 4. Project RTL (dependency order: primitives before composites)
puts "Reading project RTL..."
read_verilog -sv "$rtl/common/register.sv"
read_verilog -sv "$rtl/fp_formats/fp_madd.sv"
read_verilog -sv "$rtl/fp_formats/fp_power.sv"
read_verilog -sv "$rtl/memory/ram_sdp.sv"
read_verilog -sv "$rtl/memory/register_file.sv"
read_verilog -sv "$rtl/algorithm/control.sv"
read_verilog -sv "$rtl/algorithm/forward_pass.sv"
read_verilog -sv "$rtl/algorithm/reverse_pass.sv"
read_verilog -sv "$rtl/top/poly_regression.sv"
read_verilog    "$rtl/top/mfp_nexys4_ddr.v"

# 5. Constraints
puts "Reading constraints..."
read_xdc "$proj_root/synth/vivado/constraints/mfp_nexys4_ddr.xdc"

# =============================================================================
# Synthesis
# =============================================================================
puts "Running synthesis..."

synth_design \
    -top              $top_module \
    -part             $part \
    -flatten_hierarchy none \
    -include_dirs     [list $cc_src "$rtl/common"] \
    -generic     [list \
        FP_FORMAT=$FP_FORMAT \
        POLY_DEGREE=$POLY_DEGREE \
        FMA_LATENCY=$FMA_LATENCY \
        NUM_SAMPLES=$NUM_SAMPLES \
        MAX_ITERATIONS=$MAX_ITERATIONS \
        DATA_MEM_INIT="" \
        COEF_MEM_INIT="" \
        GRAD_MEM_INIT="" \
        "ALPHA_2M=32'h${ALPHA_2M_HEX}" \
    ]

# =============================================================================
# Reports
# =============================================================================
puts "Generating reports..."
report_utilization    -file "$rpt_dir/utilization_post_synth.rpt"  -quiet
report_timing_summary -file "$rpt_dir/timing_post_synth.rpt"       -quiet
report_clock_interaction \
                      -file "$rpt_dir/clock_interaction.rpt"       -quiet
report_high_fanout_nets \
                      -file "$rpt_dir/high_fanout_nets.rpt"        -quiet

# Write design checkpoint for downstream implementation
write_checkpoint -force "$rpt_dir/post_synth.dcp"

puts ""
puts "=== Synthesis complete ==="
puts "Results:    $rpt_dir"
