##############################################################################
# Makefile — POSIT16 SystemVerilog simulation
#
# Targets:
#   make sim_add    — compile + run addsub testbench
#   make sim_mul    — compile + run multiply testbench
#   make sim_div    — compile + run divide testbench
#   make sim_all    — run all three
#   make clean      — remove build artifacts
#
# Tools: iverilog + vvp  (install: sudo apt install iverilog)
#        or VCS (change TOOL variable below)
##############################################################################

TOOL ?= iverilog   # or vcs

SRC_PKG   = srcs/posit16_pkg.sv
SRC_ADD   = srcs/posit16_addsub.sv
SRC_MUL   = srcs/posit16_mul.sv
SRC_DIV   = srcs/posit16_div.sv

TB_ADD    = tb/tb_posit16_addsub.sv
TB_MUL    = tb/tb_posit16_mul.sv
TB_DIV    = tb/tb_posit16_div.sv

IVFLAGS   = -g2012 -Wall

.PHONY: sim_add sim_mul sim_div sim_all clean

sim_add: $(SRC_PKG) $(SRC_ADD) $(TB_ADD)
	iverilog $(IVFLAGS) -o sim_add $(SRC_PKG) $(SRC_ADD) $(TB_ADD) && vvp sim_add

sim_mul: $(SRC_PKG) $(SRC_MUL) $(SRC_ADD) $(TB_MUL)
	# tb_mul also uses posit16_mul (and for cross-check, posit16_mul again, so just compile all)
	iverilog $(IVFLAGS) -o sim_mul $(SRC_PKG) $(SRC_MUL) $(TB_MUL) && vvp sim_mul

sim_div: $(SRC_PKG) $(SRC_MUL) $(SRC_DIV) $(TB_DIV)
	# tb_div instantiates both posit16_div and posit16_mul for cross-check
	iverilog $(IVFLAGS) -o sim_div $(SRC_PKG) $(SRC_MUL) $(SRC_DIV) $(TB_DIV) && vvp sim_div

sim_all: sim_add sim_mul sim_div

clean:
	rm -f sim_add sim_mul sim_div *.vcd *.log
