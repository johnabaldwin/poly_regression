"""
Floating-point format utilities for the polynomial regression testbench.

Supports the four FPnew formats used in the DUT:
  FP64    (IEEE 754 double, 64-bit)  -- fpnew fp_format_e = 1
  FP32    (IEEE 754 single, 32-bit)  -- fpnew fp_format_e = 0
  FP16    (IEEE 754 half,   16-bit)  -- fpnew fp_format_e = 2
  FP16ALT (bfloat16,        16-bit)  -- fpnew fp_format_e = 4

Each FPFormat knows how to:
  encode(float) -> int    Python float → integer bit pattern
  decode(int)   -> float  integer bit pattern → Python float
  hex_str(float) -> str   zero-padded hex string for $readmemh
"""

import struct
from dataclasses import dataclass
from typing import Callable


@dataclass
class FPFormat:
    name:     str
    enum_val: int           # fpnew_pkg::fp_format_e integer value
    width:    int           # bit width of the format
    _encode:  Callable[[float], int]
    _decode:  Callable[[int], float]

    def encode(self, value: float) -> int:
        """Return the integer bit pattern for this format."""
        return self._encode(float(value))

    def decode(self, bits: int) -> float:
        """Return a Python float from an integer bit pattern."""
        return self._decode(int(bits))

    def hex_str(self, value: float) -> str:
        """Zero-padded hex string (no prefix) suitable for $readmemh."""
        return f"{self.encode(value):0{self.width // 4}x}"

    @property
    def hex_chars(self) -> int:
        """Number of hex characters needed for one value."""
        return self.width // 4


# ── Per-format encode / decode helpers ───────────────────────────────────────

def _fp64_encode(f: float) -> int:
    return struct.unpack('>Q', struct.pack('>d', f))[0]

def _fp64_decode(bits: int) -> float:
    return struct.unpack('>d', struct.pack('>Q', bits & 0xFFFF_FFFF_FFFF_FFFF))[0]


def _fp32_encode(f: float) -> int:
    return struct.unpack('>I', struct.pack('>f', f))[0]

def _fp32_decode(bits: int) -> float:
    return struct.unpack('>f', struct.pack('>I', bits & 0xFFFF_FFFF))[0]


def _fp16_encode(f: float) -> int:
    import numpy as np
    return int(np.float16(f).view(np.uint16))

def _fp16_decode(bits: int) -> float:
    import numpy as np
    return float(np.array([bits & 0xFFFF], dtype=np.uint16).view(np.float16)[0])


def _bf16_encode(f: float) -> int:
    """
    Encode a float as bfloat16 (truncated top 16 bits of float32).
    Uses ml_dtypes for correct round-to-nearest-even if available,
    otherwise falls back to truncation (which matches most hardware).
    """
    try:
        import ml_dtypes
        import numpy as np
        return int(np.array([f], dtype=ml_dtypes.bfloat16).view(np.uint16)[0])
    except ImportError:
        # Truncate: round-to-nearest via the guard/sticky bits of float32
        fp32 = _fp32_encode(f)
        guard = (fp32 >> 15) & 1
        sticky = fp32 & 0x7FFF
        bf16 = fp32 >> 16
        if guard and sticky:       # round up
            bf16 = (bf16 + 1) & 0xFFFF
        return bf16

def _bf16_decode(bits: int) -> float:
    # bfloat16 is just float32 with the lower 16 mantissa bits zeroed
    return _fp32_decode((bits & 0xFFFF) << 16)


# ── Format instances ──────────────────────────────────────────────────────────

FP64    = FPFormat("FP64",    1, 64, _fp64_encode, _fp64_decode)
FP32    = FPFormat("FP32",    0, 32, _fp32_encode, _fp32_decode)
FP16    = FPFormat("FP16",    2, 16, _fp16_encode, _fp16_decode)
FP16ALT = FPFormat("FP16ALT", 4, 16, _bf16_encode, _bf16_decode)

# Ordered list for parametrized tests (widest → narrowest)
ALL_FORMATS = [FP64, FP32, FP16, FP16ALT]

# Lookup by name
FORMATS: dict[str, FPFormat] = {f.name: f for f in ALL_FORMATS}
