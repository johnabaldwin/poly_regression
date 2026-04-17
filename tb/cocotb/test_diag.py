
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ClockCycles
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from utils.fp_formats import FORMATS

@cocotb.test()
async def diag_test(dut):
    fmt = FORMATS["FP64"]
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst.value = 1
    dut.start.value = 0
    await ClockCycles(dut.clk, 8)
    dut.rst.value = 0
    await ClockCycles(dut.clk, 2)
    dut.start.value = 1
    await RisingEdge(dut.clk)
    dut.start.value = 0

    def decode(v): 
        b = int(v)
        import struct
        return struct.unpack("d", struct.pack("Q", b & 0xFFFFFFFFFFFFFFFF))[0]

    print("\nCycle  coef_idx  exp_out_v  exp_valid_r  coef_idx_r  coef_value      accumulate      coef_madd")
    for cycle in range(35):
        await RisingEdge(dut.clk)
        fp = dut.forward_pass
        coef_idx = int(fp.coef_idx.value)
        exp_ov   = int(fp.exp_out_valid.value)
        exp_vr   = int(fp.exp_valid_r.value)
        cidx_r   = int(fp.coef_idx_r.value)
        cval     = decode(dut.coef_rd_data.value)
        acc      = decode(fp.accumulate.value)
        cm       = decode(fp.coef_madd.value)
        print(f"  {cycle+1:3d}    {coef_idx}       {exp_ov}          {exp_vr}         {cidx_r}     {cval:12.6f}  {acc:12.6f}  {cm:12.6f}")
    
    # Also check y_actual and error after 20+ more cycles
    print("\nCycle  fwd_pow_done  error_en  y_actual      coef_madd     error")
    for cycle in range(35, 65):
        await RisingEdge(dut.clk)
        fp = dut.forward_pass
        pd   = int(dut.fwd_pow_done.value)
        en   = int(fp.error_en.value)
        ya   = decode(fp.y_actual.value)
        cm   = decode(fp.coef_madd.value)
        err  = decode(fp.error.value)
        erdy = int(fp.error_rdy.value)
        print(f"  {cycle+1:3d}    pd={pd}  en={en}  y={ya:10.4f}  cm={cm:12.6f}  err={err:12.6f}  rdy={erdy}")
