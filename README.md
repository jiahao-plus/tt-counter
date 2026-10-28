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

Local RTL regression: `cd test && make SIM=icarus` → **13/13 cocotb PASS**
(5 counter tests + 3 PWM + 4 LFSR + mode0 isolation). See `summary.md` for
synthesis, ORFS P&R, stats and the 1×1 tile conclusion.

---

## Research branch `exp/v2-2x2-research` (V2, local — never a submission)

This branch turns the 1×1 counter into a 2×2 **research vehicle** carrying seven
physical structures that the SEM / de-layering study measures. Functional
behaviour is unchanged from the V1 golden commit `24fc6a5`.

| ID | Cell | What it is | Ports |
| --- | --- | --- | --- |
| A | `research_via1` | M1–Via1–M2 min-size via chain | 1 (`net`) |
| B | `research_via2` | M2–Via2–M3 via chain | 1 (`net`) |
| C1 | `research_branch` | one trunk + three via branches, one node | 1 (`net`) |
| C3 | `research_near` | parallel wires at 0.14/0.20/0.28/0.50 µm gaps | none |
| C4 | `research_cross` | M1/M2 crossing with **no** via — the negative sample | none |
| D | `research_dense` | width / density ladder, 0.14 → 1.00 µm | none |
| E | `research_fiducial` | identical cross pattern on M1 and M2 | none |

### The interface: α′

A / B / C1 are each a **single continuous node** — their metal access points
are joined by a via inside the GDS. The LEF therefore declares **one PIN, one
PORT, and several cross-layer RECTs inside that PORT**:

```lef
PIN net
  DIRECTION INOUT ;
  USE SIGNAL ;
  PORT
    LAYER met1 ;
      RECT 0.000 0.000 0.140 0.140 ;
    LAYER met2 ;
      RECT 8.000 2.000 8.140 2.140 ;
  END
END net
```

In LEF/DEF, multiple **PORTs** under one PIN are only a *weak* connection —
each may be reached separately, with no guarantee they are joined. Multiple
**geometries inside one PORT** are a *strong* connection. A signal router needs
the strong form, so α′ keeps everything in one PORT. (V1's multi-PORT `VGND`
is not a counter-example: power routers handle multi-PORT differently.)

C3 / C4 / D / E have no ports at all. Their truth is purely geometric. Giving
C3 pins would make the router drop vias next to the gap ladder it exists to
measure.

### Obstructions (OBS)

All seven LEFs now carry OBS, generated from rules in `macros/gen_lef.py`
(never hand-edited into the derived LEFs). Two rules, both grounded in a
delivered artifact rather than guesswork: V1's official LEF — written by Magic
in the CI run that passed Precheck 15/15 — gives every pin-less layer one OBS
rectangle over the full drawn extent, and gives the pin-bearing layer 51 pins
plus 50 OBS rectangles with **zero same-layer pin/OBS overlap**.

- **Rule E** (A/B/C1, electrical): `OBS = drawn metal − PIN shapes`. Hiding the
  interior without covering a PIN is what keeps pin access legal; each PIN
  keeps at least three free approach sides (measured).
- **Rule G** (C3/C4/D/E, geometry-only): one OBS rectangle over the whole
  `prBoundary`, applied only to layers the macro actually draws on. C3's
  between-pair gaps are 2.000 µm — 14× the 0.14 µm wire width — wide enough for
  a router to thread a wire through or drop a via beside the 0.28/0.50 µm steps.

met4/met5 are deliberately **not** obstructed: these macros draw nothing there,
M4 is the PDN stripe layer (`PDN_VERTICAL_LAYER = met4`, 1.6 µm stripes) and
`ERROR_ON_PDN_VIOLATIONS` is `True`. In this flow `PDN_OBSTRUCTIONS`,
`ROUTING_OBSTRUCTIONS` and `FP_OBSTRUCTIONS` are all undefined, so the macro's
own LEF OBS is the only per-macro routing protection there is.

Whether the router actually honours the OBS can only be read from a routed DEF.

### Where to read more

| Document | Contents |
| --- | --- |
| [v2_docs/V2_FINAL_ACCEPTANCE.md](v2_docs/V2_FINAL_ACCEPTANCE.md) | **验收报告** — 10 local checks, results, and what remains unverified |
| [v2_docs/V2_FINAL_INTERFACE_DECISION.md](v2_docs/V2_FINAL_INTERFACE_DECISION.md) | the α′ interface spec, fallback β, and the 10 acceptance criteria |
| [v2_docs/V2_INTEGRATION_CONTRACT.md](v2_docs/V2_INTEGRATION_CONTRACT.md) | the five-view chain: GDS component → LEF PIN → Verilog port → netlist net → final GDS |
| [v2_docs/V2_ARCHITECTURE_DECISION.md](v2_docs/V2_ARCHITECTURE_DECISION.md) | why A/B/C1 are electrical macros and C3/C4/D/E are geometry-only |
| [v2_docs/V2_OFFICIAL_RULES_EVIDENCE.md](v2_docs/V2_OFFICIAL_RULES_EVIDENCE.md) | official Tiny Tapeout / LibreLane / SKY130 rules, each with a source |
| [v2_docs/V2_HISTORY.md](v2_docs/V2_HISTORY.md) | timeline, the two CI failures and their root causes, and the corrected criteria |

### Reproducing the local checks

All scripts run from the repo root under WSL:

```bash
bash macros/_run_all_checks.sh                  # 22 scripts, all must PASS
cd test && make                                 # 13/13 cocotb
```

`_run_all_checks.sh` runs, in order: `gen_v2_macros.py`, `gen_lef.py`,
`p3_placement_plan.py`, `p3_patch_config.py`, `p3_synth_netlist_check.py`,
`p3_assert_pin_port_contract.py`, `p3_assert_consistency.py`,
`p3_verify_macro_views.py`, `p3_check_electrical_connectivity.py`,
`p3_integration_matrix.py`, `p3_render_placement.py`,
`p3_pdn_conflict_check.py`, `p3_sync_docs.py`, `verify_topology.py`,
`run_all_drc.py`, `_negative_control.py`, `p3_verify_lef_obs.py`,
`_neg_obs.py`, `p3_v1_lef_evidence.py`, `p3_gds_identity.py`,
`_neg_gds_identity.py`, `tools/check_source_files.py`.

`p3_v1_lef_evidence.py` is registered through a `run_opt` wrapper: it
re-measures artefacts that live **outside** this repo (the V1 official LEF and
flow log) and exits 2 when they are absent. The runner prints that as
`SKIP (artefact absent, NOT a pass)` and counts it separately — a missing file
is never reported as agreement.

`p3_gds_identity.py` compares every shape of every layer against HEAD by
canonical signature (layer/datatype + shape kind + absolute dbu coordinates,
SHA-256) — a shape *count* comparison cannot see a 1 dbu translation, a widened
rectangle or a mirrored cell. It then does the complementary raw-byte pass:
every differing byte must fall inside a `BGNLIB` or `BGNSTR` date record. It
needs the HEAD GDS objects pre-extracted, but `_run_all_checks.sh` (and
`p3_gds_identity.py` itself) does this automatically when a copy is missing.
To do it by hand:

```bash
python macros/_prefetch_head_gds.py     # Windows side, uses git cat-file
python3 macros/p3_gds_identity.py       # WSL side, reads the copies
```

The prefetch step exists because WSL's git cannot read this worktree's Windows
`.git` pointer (`rc=128` on every lookup), and `git show` can text-mangle a
binary whereas `git cat-file blob` returns the object verbatim. The automatic
call passes a **repo-relative** path with `cwd=ROOT`: an absolute `/mnt/c/...`
path reaches the Windows interpreter as `C:\mnt\c\...`, and the `课题/` path
component does not survive the ANSI code-page round trip (`????`). If both
`python.exe` and `py.exe` fail, the check FAILs and prints the captured stderr
rather than passing quietly.

### Status

All 22 local scripts and all 13 cocotb tests pass. **Nothing here proves pin
access, routing, or LVS** — those need the official CI, which this machine
cannot reach (school network policy blocks the GitHub domains; do not bypass
it). The branch is at `6eb6eb5`; these changes are **not yet committed**.

