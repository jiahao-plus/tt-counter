// research_macros.v — Verilog models for the V2 research structures.
//
// IMPORTANT — why these are NOT empty (* blackbox *) modules:
//   A module with no logic and no side effects is deleted by yosys `opt`
//   before the router sees it, so the macro never gets placed. Verified with a
//   two-module experiment (v2_validation/_t1.v): the empty blackbox was
//   removed, the pass-through module survived. `keep_hierarchy` alone does not
//   save an empty module either.
//
//   Every structure therefore carries a truthful PASS-THROUGH model. That is
//   electrically correct: each structure IS one net carrying a signal from one
//   layer to another (or a set of independent nets, for research_near), so a
//   wire is the right behaviour. The GDS/LEF macro supplies the actual
//   geometry; the RTL only has to keep the instance alive and give the router
//   real pins to reach.
//
// Naming rule (task spec 4.3): module name == LEF MACRO name == GDS cell name.

`default_nettype none

// A: M1 -> Via1 -> M2
module research_via1 (
    input  wire a,      // met1 side
    output wire b       // met2 side
);
    assign b = a;
endmodule

// B: M2 -> Via2 -> M3
module research_via2 (
    input  wire a,      // met2 side
    output wire b       // met3 side
);
    assign b = a;
endmodule

// C1: single net with three branches through vias.
// The trunk is one net; the three taps are all the same node, so the model is a
// single wire exposed on one port.
module research_branch (
    input  wire in,
    output wire tap     // same node as `in`, exposed so the cell is not empty
);
    assign tap = in;
endmodule

// C3: four *independent* pairs of parallel wires at legal gaps.
// Each pair is one net; pairs are electrically separate from each other. The
// model ties each pair input to its own output, so all eight ports are real.
module research_near (
    input  wire p0, output wire q0,
    input  wire p1, output wire q1,
    input  wire p2, output wire q2,
    input  wire p3, output wire q3
);
    assign q0 = p0;
    assign q1 = p1;
    assign q2 = p2;
    assign q3 = p3;
endmodule

`default_nettype wire
