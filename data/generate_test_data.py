#!/usr/bin/env python3
"""Generate test datasets for polynomial regression"""

import numpy as np
import struct

def float_to_hex(f):
    """Convert float to hex string for memory initialization"""
    return struct.pack('>f', f).hex()

def generate_polynomial_dataset(coeffs, x_range, num_samples, noise_level=0.0):
    """
    Generate dataset from polynomial with optional noise
    
    Args:
        coeffs: List of coefficients [a0, a1, ..., an] for a0*x^n + ... + an
        x_range: Tuple of (min, max) for x values
        num_samples: Number of data points
        noise_level: Standard deviation of Gaussian noise
    """
    degree = len(coeffs) - 1
    x = np.linspace(x_range[0], x_range[1], num_samples)
    
    # Evaluate polynomial
    y = np.zeros_like(x)
    for i, coeff in enumerate(coeffs):
        power = degree - i
        y += coeff * (x ** power)
    
    # Add noise
    if noise_level > 0:
        y += np.random.normal(0, noise_level, num_samples)
    
    return x, y

def save_dataset_hex(x, y, base_filename):
    """Save dataset in hex format for RTL memory initialization"""
    
    # Save X data
    with open(f"{base_filename}_x.hex", 'w') as f:
        for val in x:
            f.write(float_to_hex(val) + '\n')
    
    # Save Y data
    with open(f"{base_filename}_y.hex", 'w') as f:
        for val in y:
            f.write(float_to_hex(val) + '\n')
    
    # Save ground truth
    with open(f"{base_filename}_truth.txt", 'w') as f:
        f.write(f"X range: [{x.min():.4f}, {x.max():.4f}]\n")
        f.write(f"Y range: [{y.min():.4f}, {y.max():.4f}]\n")
        f.write(f"Number of samples: {len(x)}\n")

if __name__ == "__main__":
    # Generate linear regression dataset
    print("Generating linear regression dataset...")
    coeffs = [2.0, 1.0]  # y = 2x + 1
    x, y = generate_polynomial_dataset(coeffs, (-5, 5), 100, noise_level=0.1)
    save_dataset_hex(x, y, "linear_regression/dataset_01")
    
    # Generate quadratic regression dataset
    print("Generating quadratic regression dataset...")
    coeffs = [1.0, -2.0, 1.0]  # y = x^2 - 2x + 1
    x, y = generate_polynomial_dataset(coeffs, (-3, 3), 100, noise_level=0.2)
    save_dataset_hex(x, y, "quadratic_regression/dataset_01")
    
    # Generate cubic regression dataset
    print("Generating cubic regression dataset...")
    coeffs = [2.0, -3.0, 4.0, 1.0]  # y = 2x^3 - 3x^2 + 4x + 1
    x, y = generate_polynomial_dataset(coeffs, (-2, 2), 100, noise_level=0.5)
    save_dataset_hex(x, y, "cubic_regression/dataset_01")
    
    print("Dataset generation complete!")
