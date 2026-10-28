// research_macros.v — Verilog views for the seven V2 research structures.
//
// TWO DIFFERENT TREATMENTS, for two different kinds of structure:
//
// 1. ELECTRICAL structures (A, B, C1, C3) carry real signal nets. Their model
//    is a truthful pass-through: the structure IS one net (or a set of
//    independent nets, for research_near) running from one layer to another
//    through a via, so a wire is the correct behaviour. This also keeps the
//    instance alive through `opt` and gives the router real pins to reach.
//
// 2. NON_ELECTRICAL structures (C4, D, E) carry no nets by design. They use
//    the official Tiny Tapeout pattern for geometry-only macros:
//        (* blackbox *) (* keep *) module NAME (); endmodule
//    with the instance name and module name listed in
//    IGNORE_DISCONNECTED_MODULES in src/config.json.
//
//    Verified locally: `(* blackbox *)` ALONE is deleted by yosys `opt`;
//    adding `(* keep *)` keeps it. That is why both attributes are required.
//    (An earlier V2 revision used pass-through models for these three; that
//    implies signal semantics the structures do not have, so it was wrong.)
//
// Naming rule: module name == LEF MACRO name == GDS cell name.

`default_nettype none

// ---------------------------------------------------------------- electrical

// A: M1 -> Via1 -> M2
module research_via1 (
    input  wire a,
    output wire b
);
    assign b = a;
endmodule

// B: M2 -> Via2 -> M3
module research_via2 (
    input  wire a,
    output wire b
);
    assign b = a;
endmodule

// C1: single net, three branches through vias
module research_branch (
    input  wire in,
    output wire tap
);
    assign tap = in;
endmodule

// C3: four independent pairs of parallel wires at legal gaps
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

// ------------------------------------------------------------ non-electrical

// C4: M1 and M2 cross in projection, no via, deliberately NOT connected.
// No ports: this is a negative sample, it must not join any net.
(* blackbox *) (* keep *) module research_cross ();
endmodule

// D: width / density ladder, pure geometry.
(* blackbox *) (* keep *) module research_dense ();
endmodule

// E: multi-layer fiducial, identical pattern on M1 and M2.
(* blackbox *) (* keep *) module research_fiducial ();
endmodule

`default_nettype wire
