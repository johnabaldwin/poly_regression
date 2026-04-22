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


def sim_cycle_budget(degree: int, num_samples: int, max_iterations: int,
                     fma_latency: int = 2) -> int:
    """Estimate the simulation cycle budget for a poly_regression run.

    fp_power latency scales as 3+(d-1)*(fma_latency+3) per sample, and the
    reverse pass loops over every coefficient k=0..degree, so total cycles grow
    roughly as degree² × num_samples × max_iterations.  Returns 2× the
    estimated cycle count as a safety margin.
    """
    def pow_lat(d: int) -> int:
        return 2 if d == 0 else 3 + (d - 1) * (fma_latency + 3)

    fwd = (num_samples + 1) * (1 + pow_lat(degree)) + 1
    rev = sum(2 + (num_samples - 1) * (1 + pow_lat(k)) for k in range(degree + 1))
    per_iter = fwd + rev + 2
    return 2 * (max_iterations + 2) * per_iter
