#!/usr/bin/env python3
"""
Polynomial Regression using Gradient Descent
Golden Reference Model for RTL Implementation

This implementation mirrors the hardware architecture:
- Sequential processing (like hardware FSM)
- Explicit state tracking
- Clear separation of forward/backward/update phases
- Floating point operations that map to RTL modules

Author: [Your name]
Date: 2025
"""

import numpy as np
import matplotlib.pyplot as plt
from dataclasses import dataclass
from typing import List, Tuple
from enum import Enum


# =============================================================================
# Configuration and Data Structures
# =============================================================================

@dataclass
class HyperParameters:
    """Training hyperparameters"""
    poly_degree: int = 3           # Polynomial degree (n)
    learning_rate: float = 0.01    # α (alpha)
    max_iterations: int = 1000     # Maximum training iterations
    convergence_threshold: float = 1e-6  # Loss threshold for early stopping
    
    def __post_init__(self):
        """Validate parameters"""
        assert self.poly_degree >= 1, "Polynomial degree must be >= 1"
        assert self.learning_rate > 0, "Learning rate must be positive"
        assert self.max_iterations > 0, "Max iterations must be positive"


@dataclass
class TrainingData:
    """Training dataset"""
    X: np.ndarray  # Input samples [M]
    Y: np.ndarray  # Output samples [M]
    M: int         # Number of samples
    
    def __post_init__(self):
        """Validate data"""
        assert len(self.X) == len(self.Y), "X and Y must have same length"
        assert len(self.X) > 0, "Dataset cannot be empty"
        self.M = len(self.X)


class State(Enum):
    """FSM States (mirrors hardware state machine)"""
    IDLE = 0
    INIT = 1
    FORWARD_PASS = 2
    BACKWARD_PASS = 3
    UPDATE_PARAMS = 4
    CHECK_CONVERGENCE = 5
    DONE = 6


# =============================================================================
# Hardware Module Equivalents
# =============================================================================

class FloatingPointArithmetic:
    """
    Simulates the FP Arithmetic Unit from hardware
    
    In hardware, this would be a parameterized module with different
    implementations for IEEE754, bfloat16, etc.
    
    For now, we use Python floats (like IEEE754 float64)
    """
    
    def __init__(self, encoding="float64"):
        self.encoding = encoding
        self.operation_count = {
            'add': 0,
            'sub': 0,
            'mul': 0,
            'div': 0
        }
    
    def add(self, a: float, b: float) -> float:
        """Addition operation"""
        self.operation_count['add'] += 1
        return a + b
    
    def subtract(self, a: float, b: float) -> float:
        """Subtraction operation"""
        self.operation_count['sub'] += 1
        return a - b
    
    def multiply(self, a: float, b: float) -> float:
        """Multiplication operation"""
        self.operation_count['mul'] += 1
        return a * b
    
    def divide(self, a: float, b: float) -> float:
        """Division operation"""
        self.operation_count['div'] += 1
        return a / b if b != 0 else float('inf')
    
    def square(self, a: float) -> float:
        """Squaring (multiply by self)"""
        return self.multiply(a, a)
    
    def power(self, base: float, exp: int) -> float:
        """
        Power operation (repeated multiplication)
        This mirrors how hardware would compute x^n
        """
        if exp == 0:
            return 1.0
        
        result = base
        for _ in range(exp - 1):
            result = self.multiply(result, base)
        return result
    
    def get_stats(self):
        """Return operation statistics (useful for hardware estimation)"""
        return self.operation_count.copy()
    
    def reset_stats(self):
        """Reset operation counters"""
        for key in self.operation_count:
            self.operation_count[key] = 0


class Memory:
    """
    Simulates hardware memory modules
    
    In RTL, these would be:
    - Data memory: Dual-port RAM for X and Y
    - Coefficient memory: Single-port RAM with R/W
    - Gradient memory: Accumulator registers
    """
    
    def __init__(self, size: int, name: str = "Memory"):
        self.size = size
        self.name = name
        self.data = np.zeros(size, dtype=float)
        self.read_count = 0
        self.write_count = 0
    
    def read(self, addr: int) -> float:
        """Read from memory"""
        assert 0 <= addr < self.size, f"Address {addr} out of bounds"
        self.read_count += 1
        return self.data[addr]
    
    def write(self, addr: int, value: float):
        """Write to memory"""
        assert 0 <= addr < self.size, f"Address {addr} out of bounds"
        self.write_count += 1
        self.data[addr] = value
    
    def read_all(self) -> np.ndarray:
        """Read entire memory (for debugging/visualization)"""
        return self.data.copy()
    
    def write_all(self, data: np.ndarray):
        """Initialize memory with data"""
        assert len(data) == self.size, "Data size mismatch"
        self.data = data.copy()
        self.write_count += len(data)
    
    def reset_stats(self):
        """Reset access counters"""
        self.read_count = 0
        self.write_count = 0


# =============================================================================
# Main Polynomial Regression Engine
# =============================================================================

class PolynomialRegressionHardware:
    """
    Main class implementing polynomial regression
    
    This mirrors the top-level RTL module structure:
    - Memory modules (data, coefficients, gradients)
    - FP arithmetic unit
    - Control FSM
    - Datapath operations
    """
    
    def __init__(self, hyperparams: HyperParameters, data: TrainingData,
                 initial_coeffs=None):
        self.hyperparams = hyperparams
        self.data = data
        self._initial_coeffs = (
            np.array(initial_coeffs, dtype=float) if initial_coeffs is not None else None
        )

        # Verbose mode for debugging
        self.verbose = False
        
        # Degree shorthand
        self.n = hyperparams.poly_degree
        
        # Hardware modules
        self.fp_unit = FloatingPointArithmetic()
        self.data_memory_X = Memory(data.M, "X_data")
        self.data_memory_Y = Memory(data.M, "Y_data")
        self.coeff_memory = Memory(self.n + 1, "Coefficients")
        self.gradient_memory = Memory(self.n + 1, "Gradients")
        
        # Power register file (stores x^0, x^1, ..., x^n for current sample)
        self.powers = np.zeros(self.n + 1, dtype=float)
        
        # Error storage (one per sample, for backward pass)
        self.errors = np.zeros(data.M, dtype=float)
        
        # State machine
        self.state = State.IDLE
        self.iteration = 0
        self.loss_history = []
        self.coeff_history = []
        
        # Counters (like hardware counters)
        self.sample_idx = 0
        self.coeff_idx = 0
        
        # Accumulators
        self.total_loss = 0.0
        
        # Initialize memories
        self._initialize_memories()
        
    
    def _initialize_memories(self):
        """
        Initialize memory modules
        Equivalent to hardware INIT state
        """
        # Load training data into memories
        self.data_memory_X.write_all(self.data.X)
        self.data_memory_Y.write_all(self.data.Y)
        
        # Initialize coefficients: use externally-supplied values when provided,
        # otherwise fall back to the default seed-42 random initialization so
        # that the existing test suite remains deterministic.
        if self._initial_coeffs is not None:
            assert len(self._initial_coeffs) == self.n + 1, (
                f"initial_coeffs length {len(self._initial_coeffs)} != n+1 {self.n+1}"
            )
            self.coeff_memory.write_all(self._initial_coeffs)
        else:
            np.random.seed(42)  # For reproducibility
            initial_coeffs = np.random.randn(self.n + 1) * 0.01
            self.coeff_memory.write_all(initial_coeffs)
        
        # Zero out gradient memory
        self.gradient_memory.write_all(np.zeros(self.n + 1))
        
        if self.verbose:
            print(f"Initialized coefficients: {self.coeff_memory.read_all()}")
    
    # =========================================================================
    # Forward Pass (Polynomial Evaluation)
    # =========================================================================
    
    def _compute_powers(self, x: float):
        """
        Compute and store x^0, x^1, x^2, ..., x^n
        
        Hardware equivalent: COMPUTE_POWERS state
        Uses FP multiplier in sequential mode
        """
        self.powers[0] = 1.0  # x^0 = 1
        
        for k in range(1, self.n + 1):
            # Sequential power computation: x^k = x^(k-1) * x
            self.powers[k] = self.fp_unit.multiply(self.powers[k-1], x)
            
        if self.verbose:
            print(f"  Powers of {x}: {self.powers}")
    
    def _evaluate_polynomial(self) -> float:
        """
        Evaluate polynomial: y = a₀x^n + a₁x^(n-1) + ... + aₙ
        
        Hardware equivalent: MAC_LOOP state
        Uses FP multiply-accumulate chain
        """
        accumulator = 0.0
        
        # MAC loop: accumulate coefficient[k] * power[k]
        for k in range(self.n + 1):
            coeff = self.coeff_memory.read(k)
            power = self.powers[k]
            
            # MAC: accum += coeff * power
            product = self.fp_unit.multiply(coeff, power)
            accumulator = self.fp_unit.add(accumulator, product)
        
        return accumulator
    
    def _forward_pass_single_sample(self, sample_idx: int) -> Tuple[float, float]:
        """
        Forward pass for a single sample
        
        Returns: (predicted_y, error)
        
        Hardware states:
        - COMPUTE_POWERS
        - MAC_LOOP
        - COMPUTE_ERROR
        """
        # Read sample from memory
        x = self.data_memory_X.read(sample_idx)
        y_true = self.data_memory_Y.read(sample_idx)
        
        # Compute powers
        self._compute_powers(x)
        
        # Evaluate polynomial
        y_pred = self._evaluate_polynomial()
        
        # Compute error
        error = self.fp_unit.subtract(y_pred, y_true)
        
        # Store error for backward pass
        self.errors[sample_idx] = error
        
        if self.verbose:
            print(f"  Sample {sample_idx}: x={x:.4f}, y_true={y_true:.4f}, "
                  f"y_pred={y_pred:.4f}, error={error:.4f}")
        
        return y_pred, error
    
    def _forward_pass(self):
        """
        Complete forward pass over all samples
        
        Hardware state: FORWARD_PASS
        Loops over all M samples
        """
        if self.verbose:
            print(f"\n=== Forward Pass (Iteration {self.iteration}) ===")
        
        self.total_loss = 0.0
        
        # Loop over all samples
        for i in range(self.data.M):
            y_pred, error = self._forward_pass_single_sample(i)
            
            # Accumulate loss: loss += error²
            squared_error = self.fp_unit.square(error)
            self.total_loss = self.fp_unit.add(self.total_loss, squared_error)
        
        # Mean squared error
        self.total_loss = self.fp_unit.divide(self.total_loss, float(self.data.M))
        
        if self.verbose:
            print(f"Total Loss: {self.total_loss:.6f}")
    
    # =========================================================================
    # Backward Pass (Gradient Computation)
    # =========================================================================
    
    def _compute_gradient_single_coeff(self, k: int):
        """
        Compute gradient for coefficient k
        
        ∂Loss/∂aₖ = (2/M) * Σᵢ errorᵢ * xᵢᵏ
        
        Hardware states:
        - Nested loop: For each sample i, accumulate gradient
        - Uses FP multiply and accumulate
        """
        gradient_accum = 0.0
        
        # Loop over all samples
        for i in range(self.data.M):
            x = self.data_memory_X.read(i)
            error = self.errors[i]
            
            # Compute x^k (reuse power computation logic)
            x_power_k = self.fp_unit.power(x, k)
            
            # Accumulate: grad += error * x^k
            product = self.fp_unit.multiply(error, x_power_k)
            gradient_accum = self.fp_unit.add(gradient_accum, product)
        
        # Scale by (2/M)
        scale_factor = self.fp_unit.divide(2.0, float(self.data.M))
        gradient = self.fp_unit.multiply(gradient_accum, scale_factor)
        
        return gradient
    
    def _backward_pass(self):
        """
        Complete backward pass - compute all gradients
        
        Hardware state: BACKWARD_PASS
        Nested loops: samples × coefficients
        """
        if self.verbose:
            print(f"\n=== Backward Pass ===")
        
        # Zero out gradients
        for k in range(self.n + 1):
            self.gradient_memory.write(k, 0.0)
        
        # Compute gradient for each coefficient
        for k in range(self.n + 1):
            gradient = self._compute_gradient_single_coeff(k)
            self.gradient_memory.write(k, gradient)
            
            if self.verbose:
                print(f"  Gradient[{k}]: {gradient:.6f}")
    
    # =========================================================================
    # Parameter Update
    # =========================================================================
    
    def _update_parameters(self):
        """
        Update coefficients: aₖ = aₖ - α * ∂Loss/∂aₖ
        
        Hardware state: UPDATE_PARAMS
        Loop over all coefficients
        """
        if self.verbose:
            print(f"\n=== Update Parameters ===")
            print(f"Learning rate: {self.hyperparams.learning_rate}")
        
        for k in range(self.n + 1):
            # Read current coefficient and gradient
            coeff = self.coeff_memory.read(k)
            grad = self.gradient_memory.read(k)
            
            # Compute update: α * grad
            update = self.fp_unit.multiply(self.hyperparams.learning_rate, grad)
            
            # Update coefficient: coeff -= α * grad
            new_coeff = self.fp_unit.subtract(coeff, update)
            
            # Write back to memory
            self.coeff_memory.write(k, new_coeff)
            
            if self.verbose:
                print(f"  Coeff[{k}]: {coeff:.6f} -> {new_coeff:.6f} "
                      f"(grad={grad:.6f}, update={update:.6f})")
    
    # =========================================================================
    # Control FSM
    # =========================================================================
    
    def _check_convergence(self) -> bool:
        """
        Check if training should stop
        
        Hardware state: CHECK_CONVERGENCE
        """
        # Store history
        self.loss_history.append(self.total_loss)
        self.coeff_history.append(self.coeff_memory.read_all())
        
        # Check convergence criteria
        converged = self.total_loss < self.hyperparams.convergence_threshold
        max_iter_reached = self.iteration >= self.hyperparams.max_iterations
        
        if converged:
            print(f"✓ Converged at iteration {self.iteration} "
                  f"(loss={self.total_loss:.6e})")
            return True
        
        if max_iter_reached:
            print(f"⚠ Max iterations reached ({self.hyperparams.max_iterations})")
            return True
        
        return False
    
    def train(self, verbose=False):
        """
        Main training loop
        
        Implements the complete FSM:
        IDLE -> INIT -> (FORWARD -> BACKWARD -> UPDATE -> CHECK)* -> DONE
        """
        self.verbose = verbose
        
        print("="*60)
        print("POLYNOMIAL REGRESSION TRAINING")
        print("="*60)
        print(f"Polynomial degree: {self.n}")
        print(f"Number of samples: {self.data.M}")
        print(f"Learning rate: {self.hyperparams.learning_rate}")
        print(f"Max iterations: {self.hyperparams.max_iterations}")
        print("="*60)
        
        # State: IDLE -> INIT
        self.state = State.INIT
        self._initialize_memories()
        
        # Main training loop
        self.state = State.FORWARD_PASS
        
        for iteration in range(self.hyperparams.max_iterations):
            self.iteration = iteration
            
            # Print progress every 100 iterations
            if iteration % 100 == 0 and not verbose:
                print(f"Iteration {iteration:4d}: Loss = {self.total_loss:.6e}")
            
            # Forward pass
            self.state = State.FORWARD_PASS
            self._forward_pass()
            
            # Backward pass
            self.state = State.BACKWARD_PASS
            self._backward_pass()
            
            # Update parameters
            self.state = State.UPDATE_PARAMS
            self._update_parameters()
            
            # Check convergence
            self.state = State.CHECK_CONVERGENCE
            if self._check_convergence():
                break
        
        # Done
        self.state = State.DONE
        
        print("="*60)
        print("TRAINING COMPLETE")
        print("="*60)
        self._print_results()
    
    # =========================================================================
    # Results and Analysis
    # =========================================================================
    
    def _print_results(self):
        """Print final results"""
        print(f"\nFinal coefficients:")
        coeffs = self.coeff_memory.read_all()
        for k in range(self.n + 1):
            print(f"  a[{k}] = {coeffs[k]:+.6f}")
        
        print(f"\nFinal loss: {self.total_loss:.6e}")
        print(f"Iterations: {self.iteration + 1}")
        
        # Hardware statistics
        print(f"\n--- Hardware Operation Statistics ---")
        fp_stats = self.fp_unit.get_stats()
        total_ops = sum(fp_stats.values())
        print(f"Total FP operations: {total_ops}")
        for op, count in fp_stats.items():
            print(f"  {op:4s}: {count:8d} ({100*count/total_ops:.1f}%)")
        
        print(f"\n--- Memory Access Statistics ---")
        print(f"X data: {self.data_memory_X.read_count} reads")
        print(f"Y data: {self.data_memory_Y.read_count} reads")
        print(f"Coefficients: {self.coeff_memory.read_count} reads, "
              f"{self.coeff_memory.write_count} writes")
        print(f"Gradients: {self.gradient_memory.read_count} reads, "
              f"{self.gradient_memory.write_count} writes")
    
    def get_coefficients(self) -> np.ndarray:
        """Return final learned coefficients"""
        return self.coeff_memory.read_all()
    
    def predict(self, x: float) -> float:
        """
        Predict y for a given x using learned coefficients
        
        This is just the forward pass evaluation
        """
        self._compute_powers(x)
        return self._evaluate_polynomial()
    
    def plot_results(self):
        """Plot training progress and final fit"""
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        # Plot 1: Loss over iterations
        ax = axes[0, 0]
        ax.plot(self.loss_history, linewidth=2)
        ax.set_xlabel('Iteration')
        ax.set_ylabel('Loss (MSE)')
        ax.set_title('Training Loss')
        ax.set_yscale('log')
        ax.grid(True, alpha=0.3)
        
        # Plot 2: Coefficient evolution
        ax = axes[0, 1]
        coeff_history = np.array(self.coeff_history)
        for k in range(self.n + 1):
            ax.plot(coeff_history[:, k], label=f'a[{k}]', linewidth=2)
        ax.set_xlabel('Iteration')
        ax.set_ylabel('Coefficient Value')
        ax.set_title('Coefficient Evolution')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Plot 3: Final polynomial fit
        ax = axes[1, 0]
        x_plot = np.linspace(self.data.X.min(), self.data.X.max(), 200)
        y_plot = [self.predict(x) for x in x_plot]
        
        ax.scatter(self.data.X, self.data.Y, alpha=0.6, s=50, 
                   label='Training Data', color='blue')
        ax.plot(x_plot, y_plot, 'r-', linewidth=2, 
                label=f'Learned Polynomial (degree {self.n})')
        ax.set_xlabel('x')
        ax.set_ylabel('y')
        ax.set_title('Polynomial Fit')
        ax.legend()
        ax.grid(True, alpha=0.3)
        
        # Plot 4: Residuals
        ax = axes[1, 1]
        residuals = [self.data.Y[i] - self.predict(self.data.X[i]) 
                     for i in range(self.data.M)]
        ax.scatter(self.data.X, residuals, alpha=0.6, s=50, color='green')
        ax.axhline(y=0, color='r', linestyle='--', linewidth=2)
        ax.set_xlabel('x')
        ax.set_ylabel('Residual')
        ax.set_title('Residuals (y_true - y_pred)')
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig('polynomial_regression_results.png', dpi=150)
        print("\nPlot saved to: polynomial_regression_results.png")
        plt.show()


# =============================================================================
# Helper Functions for Generating Test Data
# =============================================================================

def generate_polynomial_data(true_coeffs: List[float],
                             x_range: Tuple[float, float],
                             num_samples: int,
                             noise_std: float = 0.0,
                             quiet: bool = False) -> TrainingData:
    """
    Generate synthetic polynomial data for testing
    
    Args:
        true_coeffs: True polynomial coefficients [a₀, a₁, ..., aₙ]
        x_range: (min, max) range for x values
        num_samples: Number of samples to generate
        noise_std: Standard deviation of Gaussian noise
    
    Returns:
        TrainingData object
    """
    degree = len(true_coeffs) - 1
    
    # Generate x values
    X = np.linspace(x_range[0], x_range[1], num_samples)
    
    # Evaluate true polynomial
    Y = np.zeros(num_samples)
    for i, x in enumerate(X):
        y = 0.0
        for k, coeff in enumerate(true_coeffs):
            y += coeff * (x ** k)
        Y[i] = y
    
    # Add noise
    if noise_std > 0:
        Y += np.random.normal(0, noise_std, num_samples)

    if not quiet:
        print(f"Generated polynomial data:")
        print(f"  True coefficients: {true_coeffs}")
        print(f"  Degree: {degree}")
        print(f"  X range: [{x_range[0]}, {x_range[1]}]")
        print(f"  Samples: {num_samples}")
        print(f"  Noise std: {noise_std}")

    return TrainingData(X=X, Y=Y, M=num_samples)


# =============================================================================
# Main - Example Usage
# =============================================================================

def main():
    """Example usage of the polynomial regression model"""
    
    # Test Case 1: Linear regression (degree 1)
    print("\n" + "="*60)
    print("TEST CASE 1: Linear Regression")
    print("="*60)
    
    # True polynomial: y = 2x + 1
    data = generate_polynomial_data(
        true_coeffs=[1.0, 2.0],  # [a₀, a₁] for a₀ + a₁·x
        x_range=(-5, 5),
        num_samples=100,
        noise_std=0.5
    )
    
    hyperparams = HyperParameters(
        poly_degree=1,
        learning_rate=0.01,
        max_iterations=1000,
        convergence_threshold=1e-4
    )
    
    model = PolynomialRegressionHardware(hyperparams, data)
    model.train(verbose=False)
    model.plot_results()
    
    # Test Case 2: Cubic regression (degree 3)
    print("\n" + "="*60)
    print("TEST CASE 2: Cubic Regression")
    print("="*60)
    
    # True polynomial: y = 1 + 2x - 3x² + x³
    data = generate_polynomial_data(
        true_coeffs=[1.0, 2.0, -3.0, 1.0],  # [a₀, a₁, a₂, a₃]
        x_range=(-2, 2),
        num_samples=150,
        noise_std=0.8
    )
    
    hyperparams = HyperParameters(
        poly_degree=3,
        learning_rate=0.01,
        max_iterations=2000,
        convergence_threshold=1e-4
    )
    
    model = PolynomialRegressionHardware(hyperparams, data)
    model.train(verbose=False)
    model.plot_results()
    
    # Demonstrate verbose mode with smaller example
    print("\n" + "="*60)
    print("TEST CASE 3: Quadratic (Verbose Mode)")
    print("="*60)
    
    # Small dataset for verbose demonstration
    data = generate_polynomial_data(
        true_coeffs=[0.5, -1.0, 2.0],  # y = 0.5 - x + 2x²
        x_range=(-1, 1),
        num_samples=10,
        noise_std=0.1
    )
    
    hyperparams = HyperParameters(
        poly_degree=2,
        learning_rate=0.01,
        max_iterations=50,
        convergence_threshold=1e-6
    )
    
    model = PolynomialRegressionHardware(hyperparams, data)
    model.train(verbose=True)  # Show detailed per-iteration output


if __name__ == "__main__":
    main()