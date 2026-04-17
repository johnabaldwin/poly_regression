"""Shared test configuration constants for the cocotb testbench."""

POLY_DEGREE    = 3
NUM_SAMPLES    = 50
MAX_ITERATIONS = 900
LEARNING_RATE  = 0.01
NOISE_STD      = 0.3

# Ground-truth coefficients: y = 1 + 2x - 1.5x² + 0.5x³
# Convention matches poly_test.py: true_coeffs[k] is the coefficient of x^k.
TRUE_COEFFS = [1.0, 2.0, -1.5, 0.5]
X_RANGE     = (-2.0, 2.0)
