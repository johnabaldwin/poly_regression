# Vivado synthesis script

# Open project
open_project ./vivado_project/poly_regression.xpr

# Reset runs
reset_run synth_1

# Launch synthesis
launch_runs synth_1 -jobs 4
wait_on_run synth_1

# Generate reports
open_run synth_1
report_utilization -file ./reports/utilization_post_synth.rpt
report_timing_summary -file ./reports/timing_post_synth.rpt

puts "Synthesis complete!"
