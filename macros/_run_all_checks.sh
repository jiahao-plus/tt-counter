#!/bin/bash
# Re-run every local acceptance check, stop-free, and print a one-line verdict
# per step. Run from the repo root: bash macros/_run_all_checks.sh
set -u
cd "$(dirname "$0")/.." || exit 1
fail=0
skip=0

# The 3rd-round LibreLane final GDS/DEF live outside this repo (they are large
# run artefacts and are deliberately not committed). The intrusion check is only
# meaningful against a real final layout, so it is run through run_opt: absent
# artefacts report SKIP, never PASS.
#
# Default location: <lesson>/GDS_logs/runs/wokwi, where <lesson> holds this
# repo. Override with FINAL_GDS / FINAL_DEF, or with TT_RUN_DIR.
# <lesson> is two levels above the repo root: <lesson>/tt-v2 is this repo and
# <lesson>/GDS_logs holds the run artefacts. Note that we are already at the
# repo root here (see the cd on line 4).
TT_RUN_DIR="${TT_RUN_DIR:-$PWD/../../GDS_logs/runs/wokwi}"
FINAL_GDS="${FINAL_GDS:-$TT_RUN_DIR/final/gds/tt_um_jiahao_plus_counter.gds}"
FINAL_DEF="${FINAL_DEF:-$TT_RUN_DIR/final/def/tt_um_jiahao_plus_counter.def}"
[ -f "$FINAL_GDS" ] && [ -f "$FINAL_DEF" ] || { FINAL_GDS=""; FINAL_DEF=""; }
if [ -z "$FINAL_GDS" ]; then
  printf '%-42s SKIP (3rd-round final GDS absent, NOT a pass)\n' \
         "p5_intrusion_check.py"
  skip=$((skip+1))
fi
run() {
  local name="$1"; shift
  if "$@" >/tmp/_chk.log 2>&1; then
    printf '%-42s PASS\n' "$name"
  else
    printf '%-42s FAIL\n' "$name"
    tail -15 /tmp/_chk.log | sed 's/^/    /'
    fail=$((fail+1))
  fi
}
# For checks that depend on an artefact outside this repo. Exit code 2 means
# "could not run" and is reported as SKIP, never as PASS.
run_opt() {
  local name="$1"; shift
  "$@" >/tmp/_chk.log 2>&1
  local rc=$?
  if [ "$rc" -eq 0 ]; then
    printf '%-42s PASS\n' "$name"
  elif [ "$rc" -eq 2 ]; then
    printf '%-42s SKIP (artefact absent, NOT a pass)\n' "$name"
    skip=$((skip+1))
  else
    printf '%-42s FAIL\n' "$name"
    tail -15 /tmp/_chk.log | sed 's/^/    /'
    fail=$((fail+1))
  fi
}
run "gen_v2_macros.py"                  python3 macros/gen_v2_macros.py
run "gen_lef.py"                        python3 macros/gen_lef.py
run "p3_placement_plan.py"              python3 macros/p3_placement_plan.py
run "p3_patch_config.py"                python3 macros/p3_patch_config.py
run "p3_synth_netlist_check.py"         python3 macros/p3_synth_netlist_check.py
run "p3_assert_pin_port_contract.py"    python3 macros/p3_assert_pin_port_contract.py
run "p3_assert_consistency.py"          python3 macros/p3_assert_consistency.py
run "p3_verify_macro_views.py"          python3 macros/p3_verify_macro_views.py
run "p3_check_electrical_connectivity.py" python3 macros/p3_check_electrical_connectivity.py
run "p3_integration_matrix.py"          python3 macros/p3_integration_matrix.py
run "p3_render_placement.py"            python3 macros/p3_render_placement.py
run "p3_pdn_conflict_check.py"          python3 macros/p3_pdn_conflict_check.py
run "p3_sync_docs.py"                   python3 macros/p3_sync_docs.py
run "verify_topology.py"                python3 macros/verify_topology.py
run "run_all_drc.py"                    python3 macros/run_all_drc.py
run "_negative_control.py"              python3 macros/_negative_control.py
run "p3_verify_lef_obs.py"              python3 macros/p3_verify_lef_obs.py
run "_neg_obs.py"                       python3 macros/_neg_obs.py
run_opt "p3_v1_lef_evidence.py"         python3 macros/p3_v1_lef_evidence.py
run "p3_gds_identity.py"                python3 macros/p3_gds_identity.py
run "_neg_gds_identity.py"              python3 macros/_neg_gds_identity.py
run "check_source_files.py"             python3 tools/check_source_files.py

# ---- P5: via-enclosure fix, geometry record, and independent intrusion check
run "p5_geometry_record.py"             python3 macros/p5_geometry_record.py
run "p5_intrusion_negative.py"          python3 macros/p5_intrusion_negative.py
if [ -n "$FINAL_GDS" ]; then
  run "p5_intrusion_check.py"           python3 macros/p5_intrusion_check.py "$FINAL_GDS" "$FINAL_DEF" .v2ana/intrusion_check.json .v2ana/head
  run "p5_pad_impact.py"                python3 macros/p5_pad_impact.py "$FINAL_GDS" "$FINAL_DEF" .v2ana/head .v2ana/pad_impact.json
fi
echo
if [ "$fail" -eq 0 ] && [ "$skip" -eq 0 ]; then
  echo "ALL LOCAL CHECKS PASS"
elif [ "$fail" -eq 0 ]; then
  echo "ALL RUN CHECKS PASS — $skip SKIPPED (not passes)"
else
  echo "$fail CHECK(S) FAILED"
fi
[ "$fail" -eq 0 ]
