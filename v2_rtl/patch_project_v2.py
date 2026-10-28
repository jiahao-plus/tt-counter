#!/usr/bin/env python3
"""patch_project_v2.py — add V2 research instantiations to src/project.v.

V1 functional behaviour is preserved verbatim. Only two edits:
  1. the header banner gains a V2 note
  2. research macro instances are appended before the final endmodule
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
P = os.path.join(ROOT, 'src', 'project.v')

BANNER_OLD = " * Integrated multi-mode design (experiment branch exp/ip-integration)"
BANNER_NEW = (
    " * V2 2x2 research vehicle (branch exp/v2-2x2-research)\n"
    " *\n"
    " * Functional behaviour is UNCHANGED from the V1 golden commit 24fc6a5.\n"
    " * Added: RTL instances of the V2 electrical research structures\n"
    " * (M1-Via1-M2, M2-Via2-M3, single-net branch, near-neighbour pairs).\n"
    " * The NON_ELECTRICAL cells (research_cross / research_dense /\n"
    " * research_fiducial) carry no nets and are placed by the floorplan, so\n"
    " * they are deliberately NOT instantiated here."
)

INST = """
  // ---------------------------------------------------------------
  // V2 research structures.
  //
  // Only the ELECTRICAL structures are instantiated: they have real pins and
  // must be reached by the router. The NON_ELECTRICAL cells carry no nets and
  // are placed by the floorplan instead.
  //
  // Each macro input is tied to pwm_out (a flop-driven signal in mode 1) so the
  // nets survive synthesis and the router must connect the macro pins.
  // ---------------------------------------------------------------
  wire rs_a_in = pwm_out;
  wire rs_a_out;
  wire rs_b_in = pwm_out;
  wire rs_b_out;

  research_via1 u_rs_via1 (
      .a (rs_a_in),
      .b (rs_a_out)
  );

  research_via2 u_rs_via2 (
      .a (rs_b_in),
      .b (rs_b_out)
  );

  research_branch u_rs_branch (
      .in (pwm_out)
  );

  research_near u_rs_near (
      .p0 (ui_in[0]), .q0 (ui_in[1]),
      .p1 (ui_in[2]), .q1 (ui_in[3]),
      .p2 (ui_in[4]), .q2 (ui_in[5]),
      .p3 (ui_in[6]), .q3 (ui_in[7])
  );

  // Keep the two macro outputs observable so they are not optimised away.
  wire _rs_obs = rs_a_out ^ rs_b_out;

"""

TAIL_OLD = "  // Silence unused-input warning\n  wire _unused = &{1'b0};"
TAIL_NEW = INST + "  // Silence unused-input warning\n  wire _unused = &{1'b0, _rs_obs};"


def main():
    s = open(P, encoding='utf-8').read()
    if 'V2 2x2 research vehicle' in s:
        print('already patched; nothing to do')
        return 0
    if BANNER_OLD not in s:
        print('FAIL: banner anchor not found'); return 1
    if TAIL_OLD not in s:
        print('FAIL: tail anchor not found'); return 1
    s = s.replace(BANNER_OLD, BANNER_NEW)
    s = s.replace(TAIL_OLD, TAIL_NEW)
    open(P, 'w', encoding='utf-8', newline='\n').write(s)
    print('patched', P)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
