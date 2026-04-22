# =============================================================================
# Polynomial Regression Cocotb Testbench
# =============================================================================

TB_DIR   := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
REPO_ROOT := $(abspath $(TB_DIR)/../..)

VENV   := $(REPO_ROOT)/.venv
PYTHON := $(VENV)/bin/python
PYTEST := $(PYTHON) -m pytest

PYTEST_OPTS ?= -v --tb=short

# =============================================================================
# Setup
# =============================================================================

.PHONY: install
install:
	$(VENV)/bin/pip install -r $(TB_DIR)/requirements.txt

# =============================================================================
# Test targets
# =============================================================================

# Run all four format tests sequentially
.PHONY: test
test:
	cd $(TB_DIR) && \
	PYTHONPATH=$(TB_DIR) \
	$(PYTEST) tests/test_formats.py $(PYTEST_OPTS)

# Individual format targets
.PHONY: test-fp64
test-fp64:
	cd $(TB_DIR) && \
	PYTHONPATH=$(TB_DIR) \
	$(PYTEST) tests/test_formats.py -k FP64 $(PYTEST_OPTS)

.PHONY: test-fp32
test-fp32:
	cd $(TB_DIR) && \
	PYTHONPATH=$(TB_DIR) \
	$(PYTEST) tests/test_formats.py -k FP32 $(PYTEST_OPTS)

.PHONY: test-fp16
test-fp16:
	cd $(TB_DIR) && \
	PYTHONPATH=$(TB_DIR) \
	$(PYTEST) tests/test_formats.py -k "FP16 and not FP16ALT" $(PYTEST_OPTS)

.PHONY: test-bfloat16
test-bfloat16:
	cd $(TB_DIR) && \
	PYTHONPATH=$(TB_DIR) \
	$(PYTEST) tests/test_formats.py -k FP16ALT $(PYTEST_OPTS)

# fp_power unit test (FMT defaults to FP64; override with FMT=FP32 etc.)
FMT ?= FP64
.PHONY: test-fp-power
test-fp-power:
	cd $(TB_DIR) && \
	PYTHONPATH=$(TB_DIR) \
	$(PYTEST) tests/test_fp_power.py -k $(FMT) $(PYTEST_OPTS)

# =============================================================================
# Randomised multi-test target
# =============================================================================
# Required:
#   N          - number of random test cases to run
# Optional:
#   SEED       - base random seed (default: 0)
#   MAX_DEGREE - maximum polynomial degree to sample (default: 9)
#
# Example: make test-random N=20 SEED=42 MAX_DEGREE=6
# =============================================================================

N          ?=
SEED       ?= 0
MAX_DEGREE ?= 9

.PHONY: test-random
test-random:
	@[ -n "$(N)" ] || { \
		echo ""; \
		echo "  Error: N is required."; \
		echo "  Usage: make test-random N=<count> [SEED=<seed>] [MAX_DEGREE=<deg>]"; \
		echo ""; \
		exit 1; \
	}
	@cd $(TB_DIR) && { \
		PYTHONPATH=$(TB_DIR) \
		TB_NUM_TESTS=$(N) \
		TB_RANDOM_SEED=$(SEED) \
		TB_MAX_DEGREE=$(MAX_DEGREE) \
		$(PYTEST) tests/test_random.py $(PYTEST_OPTS); \
		rc=$$?; \
		echo ""; \
		echo "Generating plots from results..."; \
		PYTHONPATH=$(TB_DIR) \
		$(PYTHON) $(TB_DIR)/utils/plot_random_results.py $(TB_DIR)/results || true; \
		exit $$rc; \
	}

# =============================================================================
# Waveform viewing (opens GTKWave on the most recent VCD)
# =============================================================================

.PHONY: waves
waves:
	@VCD=$$(find $(TB_DIR) -name "dump.vcd" 2>/dev/null | xargs ls -t 2>/dev/null | head -1); \
	if [ -n "$$VCD" ]; then \
		echo "Opening $$VCD"; \
		gtkwave "$$VCD" & \
	else \
		echo "No VCD files found. Run: TB_TRACE=1 TB_MAX_CYCLES=500 make test-fp64"; \
		exit 1; \
	fi

# =============================================================================
# Clean
# =============================================================================

.PHONY: clean
clean:
	find $(TB_DIR) -type d -name "sim_build*"    -exec rm -rf {} + 2>/dev/null || true
	find $(TB_DIR) -type d -name "__pycache__"   -exec rm -rf {} + 2>/dev/null || true
	find $(TB_DIR) -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find $(TB_DIR) -name "*.pyc" -delete 2>/dev/null || true
	find $(TB_DIR) -name "results_*.json" -delete 2>/dev/null || true
	rm -f $(TB_DIR)/results/format_comparison.csv
	rm -f $(TB_DIR)/results/random_summary.csv
	rm -rf $(TB_DIR)/results/test_*
	rm -rf $(TB_DIR)/results/plots
	rm -rf $(REPO_ROOT)/data/random

.PHONY: help
help:
	@echo "Polynomial Regression Cocotb Testbench"
	@echo "======================================="
	@echo ""
	@echo "  make install                  Install Python dependencies into project venv"
	@echo "  make test                     Run all four FP format tests (fixed coefficients)"
	@echo "  make test-fp64                Run FP64 only"
	@echo "  make test-fp32                Run FP32 only"
	@echo "  make test-fp16                Run FP16 only"
	@echo "  make test-bfloat16            Run FP16ALT (bfloat16) only"
	@echo ""
	@echo "  make test-random N=<count>    Random multi-test sweep across all formats"
	@echo "    N          Number of random test cases (required)"
	@echo "    SEED       Base random seed          (default: 0)"
	@echo "    MAX_DEGREE Maximum polynomial degree (default: 9)"
	@echo ""
	@echo "  Example: make test-random N=20 SEED=42 MAX_DEGREE=6"
	@echo ""
	@echo "  make waves                    Open most recent VCD in GTKWave"
	@echo "  make clean                    Remove all build and result artifacts"
	@echo ""
	@echo "Fixed-test results:  tb/cocotb/results/format_comparison.csv"
	@echo "Random-test results: tb/cocotb/results/random_summary.csv"
	@echo "                     tb/cocotb/results/test_<N>/<FMT>/hw_results.json"
	@echo "Plots:               tb/cocotb/results/plots/"
