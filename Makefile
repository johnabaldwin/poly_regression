# =============================================================================
# Polynomial Regression RTL Project - Hybrid Make + FuseSoC Build System
# =============================================================================
SHELL := /bin/bash

# Project configuration
PROJECT_NAME = poly_regression
FUSESOC_CORE = john:comp_arch:poly_regression:1.0.0

# Directories
RTL_DIR = rtl
TB_DIR = tb
SIM_DIR = sim
SYNTH_DIR = synth
DATA_DIR = data
SCRIPTS_DIR = scripts

# Virtual environment
VENV = .venv

# Tools
FUSESOC = $(VENV)/bin/fusesoc
VERILATOR = verilator
VERIBLE_LINT = verible-verilog-lint
VERIBLE_FMT = verible-verilog-format
GTKWAVE = gtkwave
VIVADO = vivado
PYTHON = python3

# Source files (for direct Make operations)
RTL_SOURCES = $(shell find $(RTL_DIR) -name "*.sv" -o -name "*.v")
RTL_INCLUDES = -I$(RTL_DIR)/common
TB_SOURCES = $(shell find $(TB_DIR) -name "*.sv" -o -name "*.cpp")

# Default parameters (can be overridden)
FP_FORMAT ?= FP32
POLY_DEGREE ?= 3
NUM_SAMPLES ?= 100
MAX_ITERATIONS ?= 1000

# Build flags
FUSESOC_SIM_FLAGS = --FP_FORMAT=$(FP_FORMAT) --POLY_DEGREE=$(POLY_DEGREE) \
                    --NUM_SAMPLES=$(NUM_SAMPLES) --MAX_ITERATIONS=$(MAX_ITERATIONS)

# Color output
ESC := $(shell printf '\033')
COLOR_RESET = $(ESC)[0m
COLOR_BOLD = $(ESC)[1m
COLOR_GREEN = $(ESC)[32m
COLOR_YELLOW = $(ESC)[33m
COLOR_BLUE = $(ESC)[34m
COLOR_RED = $(ESC)[31m

# =============================================================================
# Default Target
# =============================================================================

.PHONY: all
all: help

.PHONY: help
help:
	@echo "$(COLOR_BOLD)Polynomial Regression RTL Build System$(COLOR_RESET)"
	@echo "=========================================="
	@echo ""
	@echo "$(COLOR_BOLD)Linting:$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make lint$(COLOR_RESET)              - Run all linting (functional + style)"
	@echo "  $(COLOR_GREEN)make lint-functional$(COLOR_RESET)   - Run Verilator functional lint"
	@echo "  $(COLOR_GREEN)make lint-style$(COLOR_RESET)        - Run Verible style check"
	@echo "  $(COLOR_GREEN)make format$(COLOR_RESET)            - Auto-format code with Verible"
	@echo ""
	@echo "$(COLOR_BOLD)Simulation (FuseSoC):$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make sim$(COLOR_RESET)               - Run Verilator simulation"
	@echo "  $(COLOR_GREEN)make sim-gui$(COLOR_RESET)           - Run simulation and open waveforms"
	@echo "  $(COLOR_GREEN)make waves$(COLOR_RESET)             - View waveforms from last simulation"
	@echo "  $(COLOR_GREEN)make test-unit$(COLOR_RESET)         - Run unit tests"
	@echo ""
	@echo "$(COLOR_BOLD)Simulation Parameters:$(COLOR_RESET)"
	@echo "  $(COLOR_YELLOW)FP_FORMAT$(COLOR_RESET)=<format>      - Floating point format (default: $(FP_FORMAT))"
	@echo "  $(COLOR_YELLOW)POLY_DEGREE$(COLOR_RESET)=<n>        - Polynomial degree (default: $(POLY_DEGREE))"
	@echo "  $(COLOR_YELLOW)NUM_SAMPLES$(COLOR_RESET)=<n>        - Number of samples (default: $(NUM_SAMPLES))"
	@echo "  $(COLOR_YELLOW)MAX_ITERATIONS$(COLOR_RESET)=<n>     - Max iterations (default: $(MAX_ITERATIONS))"
	@echo ""
	@echo "$(COLOR_BOLD)Examples:$(COLOR_RESET)"
	@echo "  make sim FP_FORMAT=FP16ALT POLY_DEGREE=5"
	@echo "  make sim FP_FORMAT=FP16 NUM_SAMPLES=200"
	@echo ""
	@echo "$(COLOR_BOLD)Synthesis (Vivado):$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make synth$(COLOR_RESET)             - Run Vivado synthesis (via Make)"
	@echo "  $(COLOR_GREEN)make synth-fusesoc$(COLOR_RESET)     - Run Vivado synthesis (via FuseSoC)"
	@echo "  $(COLOR_GREEN)make impl$(COLOR_RESET)              - Run Vivado implementation"
	@echo ""
	@echo "$(COLOR_BOLD)Data Management:$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make generate-data$(COLOR_RESET)     - Generate test datasets"
	@echo ""
	@echo "$(COLOR_BOLD)Analysis:$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make compare-formats$(COLOR_RESET)   - Compare floating point format results"
	@echo ""
	@echo "$(COLOR_BOLD)Utility:$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make clean$(COLOR_RESET)             - Clean all build outputs"
	@echo "  $(COLOR_GREEN)make clean-sim$(COLOR_RESET)         - Clean simulation outputs only"
	@echo "  $(COLOR_GREEN)make clean-synth$(COLOR_RESET)       - Clean synthesis outputs only"
	@echo "  $(COLOR_GREEN)make info$(COLOR_RESET)              - Show FuseSoC core information"
	@echo ""
	@echo "$(COLOR_BOLD)Submodule Management:$(COLOR_RESET)"
	@echo "  $(COLOR_GREEN)make init-submodules$(COLOR_RESET)    - Initialize git submodules (FPnew)"
	@echo "  $(COLOR_GREEN)make update-submodules$(COLOR_RESET)  - Update submodules to latest"
	@echo "  $(COLOR_GREEN)make status-submodules$(COLOR_RESET)  - Show submodule status"

# =============================================================================
# Linting Targets
# =============================================================================

.PHONY: lint
lint: lint-functional lint-style
	@echo "$(COLOR_BOLD)$(COLOR_GREEN)✓ All linting passed!$(COLOR_RESET)"

.PHONY: lint-functional
lint-functional:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== Functional Lint ===$(COLOR_RESET)"
	@set -o pipefail; slang --lint-only \
		-I external/fpnew/src/common_cells/src \
		external/fpnew/src/fpnew_pkg.sv \
		$(RTL_SOURCES) 2>&1 | tee lint_functional.log; \
	if [ $$? -eq 0 ]; then \
		echo "$(COLOR_GREEN)✓ Functional lint passed$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_RED)✗ Functional lint failed$(COLOR_RESET)"; \
		exit 1; \
	fi

.PHONY: lint-style
lint-style:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== Verible Style Check ===$(COLOR_RESET)"
	@$(VERIBLE_LINT) --rules_config .verible.conf $(RTL_SOURCES) 2>&1 | tee lint_style.log
	@if [ $$? -eq 0 ]; then \
		echo "$(COLOR_GREEN)✓ Style check passed$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_YELLOW)⚠ Style issues found (see lint_style.log)$(COLOR_RESET)"; \
	fi

.PHONY: format
format:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== Auto-formatting with Verible ===$(COLOR_RESET)"
	@$(VERIBLE_FMT) --inplace $(RTL_SOURCES)
	@echo "$(COLOR_GREEN)✓ Formatting complete$(COLOR_RESET)"

# =============================================================================
# Simulation Targets (FuseSoC)
# =============================================================================

.PHONY: sim
sim:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== Running Verilator Simulation ===$(COLOR_RESET)"
	@echo "Parameters: FP_ENCODING=$(FP_ENCODING), POLY_DEGREE=$(POLY_DEGREE), NUM_SAMPLES=$(NUM_SAMPLES)"
	$(FUSESOC) run --target=sim $(FUSESOC_SIM_FLAGS) $(FUSESOC_CORE)
	@echo "$(COLOR_GREEN)✓ Simulation complete$(COLOR_RESET)"
	@echo "Waveform: build/$(FUSESOC_CORE)/sim-verilator/trace.vcd"

.PHONY: sim-gui
sim-gui: sim waves

.PHONY: waves
waves:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== Launching GTKWave ===$(COLOR_RESET)"
	@WAVE_FILE=$$(find build -name "trace.vcd" | head -1); \
	if [ -n "$$WAVE_FILE" ]; then \
		$(GTKWAVE) $$WAVE_FILE & \
		echo "$(COLOR_GREEN)✓ GTKWave launched$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_RED)✗ No waveform file found. Run 'make sim' first.$(COLOR_RESET)"; \
		exit 1; \
	fi

.PHONY: test-unit
test-unit:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== Running Unit Tests ===$(COLOR_RESET)"
	$(FUSESOC) run --target=test_unit $(FUSESOC_CORE)
	@echo "$(COLOR_GREEN)✓ Unit tests complete$(COLOR_RESET)"

# =============================================================================
# Synthesis Targets
# =============================================================================

# Synthesis via FuseSoC (basic)
.PHONY: synth-fusesoc
synth-fusesoc:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== Running Vivado Synthesis (FuseSoC) ===$(COLOR_RESET)"
	$(FUSESOC) run --target=synth $(FUSESOC_SIM_FLAGS) $(FUSESOC_CORE)
	@echo "$(COLOR_GREEN)✓ Synthesis complete$(COLOR_RESET)"

# Synthesis via Make (more control)
.PHONY: synth
synth:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== Running Vivado Synthesis (Make) ===$(COLOR_RESET)"
	@mkdir -p $(SYNTH_DIR)/vivado/reports
	cd $(SYNTH_DIR)/vivado && $(VIVADO) -mode batch -source scripts/synthesize.tcl
	@echo "$(COLOR_GREEN)✓ Synthesis complete$(COLOR_RESET)"

.PHONY: impl
impl:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== Running Vivado Implementation ===$(COLOR_RESET)"
	cd $(SYNTH_DIR)/vivado && $(VIVADO) -mode batch -source scripts/implement.tcl
	@echo "$(COLOR_GREEN)✓ Implementation complete$(COLOR_RESET)"

# =============================================================================
# Data Generation
# =============================================================================

.PHONY: generate-data
generate-data:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== Generating Test Datasets ===$(COLOR_RESET)"
	cd $(DATA_DIR) && $(PYTHON) generate_test_data.py
	@echo "$(COLOR_GREEN)✓ Test data generated$(COLOR_RESET)"

# =============================================================================
# Analysis
# =============================================================================

.PHONY: compare-formats
compare-formats:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== Comparing Floating Point Formats ===$(COLOR_RESET)"
	$(PYTHON) $(SCRIPTS_DIR)/compare_formats.py
	@echo "$(COLOR_GREEN)✓ Comparison complete$(COLOR_RESET)"

# =============================================================================
# Information
# =============================================================================

.PHONY: info
info:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== FuseSoC Core Information ===$(COLOR_RESET)"
	$(FUSESOC) core show $(FUSESOC_CORE)

# =============================================================================
# Clean Targets
# =============================================================================

.PHONY: clean-sim
clean-sim:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== Cleaning Simulation Outputs ===$(COLOR_RESET)"
	rm -rf build/
	rm -f *.vcd *.fst
	rm -f lint_*.log
	@echo "$(COLOR_GREEN)✓ Simulation outputs cleaned$(COLOR_RESET)"

.PHONY: clean-synth
clean-synth:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== Cleaning Synthesis Outputs ===$(COLOR_RESET)"
	rm -rf $(SYNTH_DIR)/vivado/vivado_project/
	rm -rf $(SYNTH_DIR)/vivado/.Xil/
	rm -f $(SYNTH_DIR)/vivado/*.log
	rm -f $(SYNTH_DIR)/vivado/*.jou
	@echo "$(COLOR_GREEN)✓ Synthesis outputs cleaned$(COLOR_RESET)"

.PHONY: clean
clean: clean-sim clean-synth
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== Cleaning All Build Outputs ===$(COLOR_RESET)"
	find . -name "*.log" -delete
	find . -name "*.jou" -delete
	@echo "$(COLOR_GREEN)✓ All outputs cleaned$(COLOR_RESET)"

# =============================================================================
# Submodule Management
# =============================================================================

.PHONY: init-submodules
init-submodules:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== Initializing Git Submodules ===$(COLOR_RESET)"
	git submodule update --init --recursive
	@echo "$(COLOR_GREEN)✓ Submodules initialized$(COLOR_RESET)"

.PHONY: update-submodules
update-submodules:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== Updating Git Submodules ===$(COLOR_RESET)"
	git submodule update --remote --merge
	@echo "$(COLOR_GREEN)✓ Submodules updated$(COLOR_RESET)"

.PHONY: status-submodules
status-submodules:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)=== Submodule Status ===$(COLOR_RESET)"
	git submodule status

# =============================================================================
# Phony Targets
# =============================================================================

.PHONY: all help lint lint-functional lint-style format \
        sim sim-gui waves test-unit \
        synth synth-fusesoc impl \
        generate-data compare-formats info \
        clean clean-sim clean-synth