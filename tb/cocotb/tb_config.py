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


# Hard ceiling on the per-degree iteration scaling.  Raise for better
# high-degree convergence at the cost of longer simulation runs.
# At the default of 10 000, a degree-9 sim takes ~66 min per format.
MAX_ITER_CAP = 10_000


def degree_lr(degree: int) -> float:
    """Return a degree-appropriate learning rate for gradient descent stability.

    λ_max of the MSE Hessian scales as (x_max²)^n, so the stable learning rate
    shrinks by x_max² = 4 for each degree above the fixed-test baseline of 3.
    Degrees ≤ 3 keep LEARNING_RATE unchanged.

      deg 1-3 → 0.01000   deg 4 → 0.00250   deg 5 → 0.000625
      deg 6   → 0.000156  deg 9 → 0.0000024
    """
    x_max = max(abs(X_RANGE[0]), abs(X_RANGE[1]))
    return LEARNING_RATE / float(x_max ** 2) ** max(0, degree - 3)


def degree_max_iter(degree: int) -> int:
    """Return a degree-appropriate iteration budget.

    Scales MAX_ITERATIONS proportionally with 1/degree_lr so each degree gets
    the same effective gradient-descent step budget, capped at MAX_ITER_CAP.

      deg 3 → 900   deg 4 → 3 600   deg 5+ → 10 000 (capped)
    """
    x_max = max(abs(X_RANGE[0]), abs(X_RANGE[1]))
    scale = float(x_max ** 2) ** max(0, degree - 3)
    return min(int(MAX_ITERATIONS * scale), MAX_ITER_CAP)


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
