# 8-bit up/down counter (tt_um_jiahao_plus_counter)

A minimal, fully combinational-control 8-bit up/down counter for Tiny Tapeout —
a first silicon test design: it is small enough to leave huge margin for
routing, and simple enough to be verified by eye on the demo board LEDs and
later under a microscope after de-capping.

- Project datasheet: [docs/info.md](docs/info.md)
- Based on the official [tt10-verilog-template](https://github.com/TinyTapeout/tt10-verilog-template)

## How it works

| Signal | Pin | Meaning |
| ------ | --- | ------- |
| `ui_in[0]` | ui[0] | `en` — 1 = counting enabled, 0 = hold value |
| `ui_in[1]` | ui[1] | `dir` — 1 = count up, 0 = count down |
| `uo_out[7:0]` | uo[0..7] | current 8-bit count value (drive the LEDs) |

- Active-low async reset (`rst_n`) clears the count to 0.
- The count only advances on the rising edge of `clk` while both `ena` and `en` are high.
- All `uio` pins are configured as inputs (unused).

## How to test

Local RTL simulation (requires iverilog + cocotb in a shell):

```bash
cd test
make
```

Expected: all cocotb tests pass (reset clears, count up, count down,
enable-off holds, 255→0 wrap).

## External hardware

None required. For a visible demo, feed a slow clock (e.g. 1 kHz) from the
Tiny Tapeout demo board's RP2040 and watch the 8 LEDs count in binary.

---

## Experiment branch `exp/ip-integration` (local build verification only)

This section exists only on the local experiment branch and is **not** part of
the upstream tapeout submission. The top module name and all 24 pins are kept
identical; `ui_in[7:2]` is repurposed as a mode select bus.

| mode (`ui_in[7:2]`) | function |
| --- | --- |
| 0 (default) | original 8-bit up/down reversible counter, behavior unchanged |
| 1 | PWM generator (vendored MIT IP); duty = `uio_in[7:0]`, `pwm_out` → `uio_out[0]`, `uio_oe[0]=1` |
| 2 | LFSR generator + serial shifter (vendored MIT IP); `enable=ui_in[0]`, `output_enable=ui_in[1]`, `seed=uio_in`, `lfsr_state` → `uo_out`, serial `Out` → `uio_out[0]`, `valid` → `uio_out[1]` |

Vendored IP under `third_party/` (LICENSE retained):

- `pwm` — bhasan60/verilog-pwm-controller, MIT, commit `789f55292b94b392b586752821033ad2b1568759`, module `pwm(clk, rst, duty[7:0], pwm_out)`.
- `lfsr` — Brafamous/Linear-Feedback-Shift-Register-Design, MIT, commit `fc59536f0017ddba4447f9497b2485072bc6ee99`, module `LFSR_Design #(width_in,width_out,countwidth)(clk,rst,enable,output_enable,seed_value[7:0],valid,Out,lfsr_out[7:0])`.

Local RTL regression: `cd test && make SIM=icarus` → 8/8 cocotb PASS
(original 5 counter tests unchanged + PWM duty=64 + LFSR golden/phase +
mode0 isolation). See `summary.md` for synthesis, ORFS P&R, stats and the
1×1 tile conclusion. This branch was never pushed and is not a submission.
