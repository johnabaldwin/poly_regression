# Vivado project creation script for Nexys A7

# Project settings
set project_name "poly_regression"
set project_dir "./vivado_project"
set part "xc7a100tcsg324-1"  # Nexys A7-100T

# Create project
create_project $project_name $project_dir -part $part -force

# Set target language
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]

# Add RTL sources
set rtl_dir "../../../rtl"
add_files [glob $rtl_dir/common/*.sv]
add_files [glob $rtl_dir/fp_formats/*/*.sv]
add_files [glob $rtl_dir/algorithm/*.sv]
add_files [glob $rtl_dir/memory/*.sv]
add_files [glob $rtl_dir/top/*.sv]

# Add constraints
add_files -fileset constrs_1 ./constraints/nexys_a7.xdc
add_files -fileset constrs_1 ./constraints/timing.xdc

# Set top module
set_property top polynomial_regression_fpga [current_fileset]

# Update compile order
update_compile_order -fileset sources_1

puts "Project created successfully!"
