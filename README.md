# 8-bit up/down counter (tt_um_yiersansiwuliu0_counter)

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
