// research_macros.v — Verilog views for the seven V2 research structures.
//
// THE SHAPE OF THIS FILE
// ----------------------
// Every module is (* blackbox *) (* keep *) with explicit ports and NO body.
// Two independent reasons, both reproduced locally:
//
//   1. `synth` -> `flatten` -> `opt` deletes an instance whose outputs reach
//      only a constant-folded sink such as `wire _unused = &{1'b0, ...}`.
//      `(* keep *)` stops that.
//   2. `write_verilog` inlines a module that has a body, so even a kept
//      instance never reaches the written netlist. A blackbox has no body to
//      inline and is emitted as a real instance.
//
// WHY ONE PORT CALLED `net` FOR A/B/C1
// ------------------------------------
// The physical fact (measured, see v2_validation/P4_PIN_COMPONENT_AUDIT.json)
// is that each of A, B and C1 has its two metal access points joined by a via
// INSIDE the macro: one continuous node. Declaring two ports made the netlist
// carry two nets across one conductor, which is the contradiction that stalled
// the earlier integration rounds.
//
// The LEF therefore declares one PIN (`net`) whose single PORT lists both the
// M1 and the M2 access rectangles. One PORT means strong connectivity in
// LEF/DEF; multiple PORTs would only be weak connectivity, which is not what
// routing a signal needs.
//
// The direction is `inout`: these are passive metal taps, with no source or
// sink semantics. `input`/`output` would imply an active device.
//
// WHAT `keep` DOES NOT BUY
// ------------------------
// It preserves the instance, its name, its cell type and its port
// connections. It does NOT prove the physical macro is wired correctly, and
// it says nothing about whether LVS accepts an internally-shorted passive.
// Those are open questions for the official flow.
//
// C3 / C4 / D / E carry no nets. They are geometry-only samples; their truth
// is purely geometric. C3 could legally have eight pins (eight isolated
// conductors, eight nets) but is kept pin-free on purpose: routing to it would
// add vias and wires next to the 0.14/0.20/0.28/0.50 um gap ladder and spoil
// exactly the spacing measurement it exists to provide.
//
// Naming rule: module name == LEF MACRO name == GDS cell name,
// and pin name == port name, character for character.

`default_nettype none

// ---------------------------------------------------------------- electrical
//
// A / B / C1 are passive metal taps. The single `net` port is the whole
// connectivity contract; the connection itself is made by metal and via inside
// the GDS, not by RTL.

// A: M1 access point and M2 access point, joined by Via1 inside the macro.
(* blackbox *) (* keep *) module research_via1 (inout wire net);
endmodule

// B: M2 access point and M3 access point, joined by Via2 inside the macro.
(* blackbox *) (* keep *) module research_via2 (inout wire net);
endmodule

// C1: one trunk plus three branch stubs, all one node, four access points.
(* blackbox *) (* keep *) module research_branch (inout wire net);
endmodule

// ------------------------------------------------------------ non-electrical
//
// No ports at all: these must not join any net.

// C3: eight isolated parallel wires at the 0.14 / 0.20 / 0.28 / 0.50 um gap
// ladder. Geometry-only truth: what exists, how wide, how far apart.
(* blackbox *) (* keep *) module research_near ();
endmodule

// C4: M1 and M2 cross in projection with no via — the negative sample.
(* blackbox *) (* keep *) module research_cross ();
endmodule

// D: width / density ladder, 0.14 to 1.00 um.
(* blackbox *) (* keep *) module research_dense ();
endmodule

// E: multi-layer fiducial, identical pattern on M1 and M2.
(* blackbox *) (* keep *) module research_fiducial ();
endmodule

`default_nettype wire
