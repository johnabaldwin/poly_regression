"""
Diagnostic test: capture error_mem after forward pass, then trace reverse pass.
"""
import os
import struct
import sys
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles

sys.path.insert(0, str(Path(__file__).parent))
from utils.fp_formats import FORMATS

def fp_decode(raw, width):
    raw = int(raw) & ((1 << width) - 1)
    if width == 64:
        return struct.unpack('d', struct.pack('Q', raw))[0]
    elif width == 32:
        return struct.unpack('f', struct.pack('I', raw))[0]
    else:
        return float('nan')

@cocotb.test()
async def rev_diag(dut):
    fp_format_name = os.environ.get("TB_FP_FORMAT", "FP64")
    fmt = FORMATS[fp_format_name]
    width = fmt.width

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    dut.rst.value = 1
    dut.start.value = 0
    await ClockCycles(dut.clk, 8)
    dut.rst.value = 0
    await ClockCycles(dut.clk, 2)

    dut.start.value = 1
    await RisingEdge(dut.clk)
    dut.start.value = 0

    # Wait until done
    for i in range(10000):
        await RisingEdge(dut.clk)
        if dut.done.value == 1:
            dut._log.info(f"Done at cycle {i+1}")
            break
    else:
        dut._log.error("Timeout!")
        return

    # Read error_mem
    dut._log.info("=== Error Memory Contents ===")
    for i in range(min(10, 50)):
        raw = int(dut.error_mem.gen_l_ram.ram[i].value)
        val = fmt.decode(raw)
        dut._log.info(f"  error[{i:2d}] = {val:.6f}")

    # Read coef_mem
    dut._log.info("=== Final Coefficient Memory ===")
    for i in range(4):
        raw = int(dut.coef_mem.gen_l_ram.ram[i].value)
        val = fmt.decode(raw)
        dut._log.info(f"  coef[{i}] = {val:.6f}")
