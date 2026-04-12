# Build System and RTL Issues

## Build System Fixes (Applied)

### 1. `fusesoc` not on system PATH
**File:** `Makefile`  
FuseSoC is installed in the project's virtual environment (`.venv/`) but the Makefile invoked it as a bare `fusesoc` command. Added a `VENV` variable and updated the `FUSESOC` tool variable to use `.venv/bin/fusesoc`.

### 2. Parameter name mismatch: `FP_ENCODING` vs `FP_FORMAT`
**File:** `Makefile`  
The Makefile defined `FP_ENCODING` and passed `--FP_ENCODING=...` to FuseSoC, but the `.core` file declares the parameter as `FP_FORMAT`. Renamed the Makefile variable and flag to `FP_FORMAT`.

### 3. Wrong `common_cells` paths in `.core` file
**File:** `poly_regression.core`  
The `common_cells` fileset referenced `external/fpnew/vendor/common_cells/src/...`, which does not exist. The FPNew submodule vendors common_cells at `external/fpnew/src/common_cells/src/`. Corrected all paths and removed the non-existent `cf_math_pkg.sv` entry.

### 4. RTL filesets referenced non-existent files
**File:** `poly_regression.core`  
The `.core` file was out of sync with the actual RTL files on disk (the project had been refactored). Updated all filesets to match actual files:

| Old (non-existent) | New (actual) |
|---|---|
| `rtl/common/parameters.svh` | `rtl/common/register.sv` |
| `rtl/common/fp_arithmetic_wrapper.sv` | *(removed)* |
| `rtl/algorithm/polynomial_evaluator.sv` | `rtl/algorithm/forward_pass.sv` |
| `rtl/algorithm/gradient_computer.sv` | `rtl/algorithm/reverse_pass.sv` |
| `rtl/algorithm/coefficient_updater.sv` | `rtl/algorithm/control.sv` |
| `rtl/algorithm/gradient_descent_controller.sv` | *(removed)* |
| `rtl/memory/data_memory.sv` | `rtl/memory/ram_sdp.sv` |
| `rtl/memory/coefficient_memory.sv` | `rtl/memory/register_file.sv` |
| `rtl/memory/gradient_memory.sv` | *(removed)* |
| `rtl/top/poly_regression_core.sv` | `rtl/top/poly_regression.sv` |
| `rtl/top/poly_regression_fpga.sv` | *(removed — not yet written)* |
| `tb/integration/tb_gradient_descent_core.sv` | *(removed — not yet written)* |
| `tb/cpp/tb_main.cpp` etc. | *(removed — not yet written)* |
| `synth/vivado/constraints/*.xdc` | *(removed — not yet written)* |

### 5. `common_cells` fileset missing from all targets
**File:** `poly_regression.core`  
The `common_cells` fileset was defined but not included in any target's `filesets` list. Added it to `default`, `sim`, `lint`, and `synth` targets.

### 6. Wrong toplevel module name
**File:** `poly_regression.core`  
The `sim` and `lint` targets specified `toplevel: poly_regression_core`, which does not exist. Corrected to `poly_regression`.

### 7. Invalid `.verible.conf` format
**File:** `.verible.conf`  
The file used a YAML-like format that `verible-verilog-lint` does not support. Rewrote it in Verible's native rules-file format (one rule per line, `-` prefix to disable, `=key:value` for configuration).

### 8. Verible not installed
Verible was not present on the system. Downloaded the static Linux x86_64 binary (v0.0-4053-g89d4d98a) from the chipsalliance/verible GitHub releases and installed `verible-verilog-lint` and `verible-verilog-format` to `/usr/local/bin/`.

---

## RTL Bugs (Outstanding)

These issues will prevent simulation from building or produce incorrect hardware. Listed roughly in dependency order.

### 1. Missing modules: `fp_power` and `fp_madd`
**Files:** `rtl/algorithm/forward_pass.sv`, `rtl/algorithm/reverse_pass.sv`  
Both modules instantiate `fp_power` and `fp_madd`, which do not exist anywhere in the project. These are FPNew wrapper modules that were likely deleted along with `rtl/common/exponentiation.sv` (visible in `git status` as a deleted file). They need to be re-created as wrappers around the relevant FPNew operations (`fpnew_top` or individual operation blocks).

### 2. `fp_zero()` called as a function
**File:** `rtl/algorithm/forward_pass.sv:100`  
```systemverilog
.a(fp_zero()),
```
`fp_zero` is not a defined function. This should be replaced with a zero constant of the appropriate width, e.g. `'0` or `{DATA_WIDTH{1'b0}}`.

### 3. Undeclared signals in top-level module
**File:** `rtl/top/poly_regression.sv`  
The following signals are used but never declared:
- `new_coef_rdy` (line 116, 150) — output from `reverse_pass`, used as write enable for `coef_mem`
- `error_rd_addr` (line 178) — read address for `err_mem`, never driven
- `error_wr_addr` (line 181) — write address for `err_mem`, never driven

### 4. FSM state `FORWARD_PASS_READ` has no case body
**File:** `rtl/algorithm/control.sv:29, 88`  
The state `FORWARD_PASS_READ` is declared in the `state_t` enum and is transitioned to from `FORWARD_PASS_WAIT` (when `fwd_pow_done` is asserted), but it has no entry in the `case` statement. It therefore falls through to `default: next_state = ERR`, locking up the state machine. A case body needs to be added — most likely it should assert `data_rd_en` and transition to `FORWARD_PASS_START` to process the next sample.

### 5. Latch inferred for `data_rd_en` in controller
**File:** `rtl/algorithm/control.sv`  
`data_rd_en` is assigned in some states of the `always_comb` block but has no default assignment at the top of the block. This causes a latch to be inferred for simulation and will produce a synthesis warning/error. Add `data_rd_en = 1'b0;` as a default before the `case` statement.

### 6. Blocking assignments inside `always_ff`
**Files:** `rtl/algorithm/forward_pass.sv:115–122`, `rtl/algorithm/reverse_pass.sv:68–76`  
The `accumulate` register in both modules is updated with blocking assignment (`=`) inside `always_ff`. This should use non-blocking assignment (`<=`) to avoid simulation race conditions and match synthesized behavior.

### 7. Non-blocking assignment in `always_comb`
**File:** `rtl/memory/register_file.sv:17`  
```systemverilog
always_comb begin
    r_data <= reg_file[r_addr];  // wrong: <= in combinational block
end
```
Non-blocking assignment (`<=`) in an `always_comb` block is illegal in synthesis and produces unpredictable simulation behavior. Change to `=`.

### 8. `coefficient_update` FMA `vld` port unconnected
**File:** `rtl/algorithm/reverse_pass.sv:86`  
The `vld` input to the `coefficient_update` FMA instance is left unconnected (marked with a TODO). Without a valid signal, the FMA will never produce a result and `new_coef_rdy` will never assert, meaning coefficients are never updated. The valid signal should be driven once all per-sample error accumulation is complete.

### 9. `coef_addr` output never driven
**File:** `rtl/algorithm/reverse_pass.sv`  
The `coef_addr` output port is declared but never assigned inside the module. The coefficient memory write address will be `X` in simulation.
