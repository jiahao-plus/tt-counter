<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This is a 2×2 research vehicle. It carries a small functional test core plus
seven passive metal structures that are the actual object of study, placed as
hard macros beside the standard-cell logic.

### Functional core: three modes

The function of the design is selected by `ui_in[7:2]` (the `mode` bus).
`ui_in[1:0]` keep their per-mode meaning and are described below.

**Mode 0 — `ui_in[7:2] == 6'd0`: 8-bit up/down counter (original V1 design).**

- `ui_in[0]` = **en**: when 1, the counter advances on each rising clock edge;
  when 0, the current value is held.
- `ui_in[1]` = **dir**: when 1 the counter counts up; when 0 it counts down.
- `uo_out[7:0]` = the count value, suitable for the demo board LEDs.
- `uio_out` = 0 and `uio_oe` = 0, so all eight `uio` pins stay inputs.

The counter resets to 0 while `rst_n` is low and only advances while both the
Tiny Tapeout global enable (`ena`) and `en` are high. This mode is
bit-for-bit the V1 behaviour; it is the golden reference the test suite pins
down.

**Mode 1 — `ui_in[7:2] == 6'd1`: PWM generator.**

- `uio_in[7:0]` = **duty** (0–255).
- `uio_out[0]` = `pwm_out`; `uio_oe[0]` = 1. The remaining `uio` pins stay
  inputs (`uio_oe[7:1]` = 0).

The PWM is a free-running 8-bit counter compared against `duty`, so
`pwm_out` is high for `duty` out of every 256 clock cycles. It runs
continuously; only its visibility on the pin is gated by the mode.

**Mode 2 — `ui_in[7:2] == 6'd2`: LFSR generator with serial output.**

- `uio_in[7:0]` = **seed_value**, sampled while `rst_n` is low.
- `ui_in[0]` = **enable**, `ui_in[1]` = **output_enable**.
- `uo_out[7:0]` = the LFSR state.
- `uio_out[0]` = serial `Out`, `uio_out[1]` = `valid`;
  `uio_oe[1:0]` = `2'b11`, the rest stay inputs.

With reset released and `enable` high, the register performs 10 shifts
(feedback taps 7/5/4/3), then freezes the result into `uo_out`. Asserting
`output_enable` then shifts that frozen byte out LSB-first on `uio_out[0]`
while `valid` is high. The serial stream therefore contains exactly
`popcount(frozen)` ones.

**Any other value of `ui_in[7:2]`** drives `uo_out` to 0 and leaves all `uio`
pins as inputs.

Both `pwm` and `LFSR_Design` are vendored MIT-licensed third-party IP
(`bhasan60/verilog-pwm-controller` and `Brafamous` respectively); the
counter, the mode mux and the research macros are this project's own.

### Research structures

Seven hard macros are instantiated alongside the logic. Three of them are
electrical: `research_via1` (M1–Via1–M2), `research_via2` (M2–Via2–M3) and
`research_branch` (one net branching onto three M2 stubs). Each exposes a
single `net` port, and all three are tied to the internal `pwm_out` signal —
a real combinational node that also drives `uio_out[0]` in mode 1, so it
cannot be optimised away and the router must actually reach the macro pin.

The other four are geometry-only and have no ports at all:
`research_near` (eight independent M1 conductors on a 0.14 / 0.20 / 0.28 /
0.50 µm gap ladder), `research_cross` (M1 and M2 crossing in projection with
no via), `research_dense` (width/pitch ladders on M1, M2 and M3) and
`research_fiducial` (a multi-layer registration mark). Their value is purely
geometric, so their LEF declares no pins and blocks routing over the drawn
metal — an invading wire or via would destroy the very feature being
measured.

The purpose of the vehicle is cross-layer SEM connectivity: after delayering,
the via links, the deliberate non-links and the gap ladders provide known
ground truth to check an image-derived connectivity reconstruction against.

## How to test

Run the cocotb testbench:

```bash
cd test
make
```

The suite has 13 tests in three groups.

- **Mode 0 counter (5):** reset clears to 0; count-up over 10 cycles;
  count-down with wrap; enable-off holds the value; 255→0 wraparound after a
  full 256 cycles. One further test confirms mode 0 keeps `uio_oe` and
  `uio_out` at 0 and does not disturb the counter.
- **Mode 1 PWM (3):** duty = 64 gives 58–70 high cycles out of 256 and
  asserts `uio_oe == 1`; duty = 0 never goes high; duty = 255 stays high for
  at least 250 of the 256 cycles.
- **Mode 2 LFSR (4):** seed 0x5A generates the golden frozen state 0xA9 and
  the shifted-out stream matches the expected popcount; reset loads the seed;
  `enable` low holds the state; reset re-loads the seed while running.

## External hardware

None required. For a visual demo, drive the design with a slow clock
(e.g. 1 kHz) from the Tiny Tapeout demo board. In mode 0 the eight LEDs
count in binary; in mode 1 LED 0 dims according to the duty cycle set on
`uio_in`; in mode 2 the LEDs show the LFSR state and `uio[0]`/`uio[1]` carry
the serial stream and its valid flag.
