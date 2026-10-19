<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This project is a simple 8-bit up/down counter. Its behaviour is fully
controlled by two input bits:

- `ui_in[0]` (pin `ui[0]`) = **en**: when 1, the counter advances on each
  rising clock edge; when 0, the current value is held.
- `ui_in[1]` (pin `ui[1]`) = **dir**: when 1, the counter counts up; when 0,
  it counts down.

The 8-bit count value is presented on `uo_out[7:0]` (pins `uo[0]`–`uo[7]`),
which can be connected directly to the demo board LEDs. The counter is reset
to 0 when `rst_n` is pulled low, and only advances while both the Tiny Tapeout
global enable (`ena`) and `en` are high. All bidirectional pins (`uio`) are
left as inputs.

The design is intentionally minimal (a few dozen standard cells): it serves as
a first-silicon validation vehicle and a convenient reference structure for
later die-level inspection.

## How to test

Run the cocotb testbench:

```bash
cd test
make
```

The test suite checks: reset clears to 0, count-up by 10 cycles, count-down by
5 cycles, enable-off holds the value, and 255→0 wraparound after a full 256
cycles.

## External hardware

None required. For a visual demo, drive the design with a slow clock
(e.g. 1 kHz) from the Tiny Tapeout demo board and observe the 8 LEDs counting
in binary.
