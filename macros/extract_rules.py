#!/usr/bin/env python3
"""extract_rules.py — 从真实 SKY130 PDK 文件提取精确设计规则。

来源（唯二权威，不猜）：
  /root/openroad-flow-scripts/flow/platforms/sky130hd/lef/sky130_fd_sc_hd.tlef
  /root/openroad-flow-scripts/flow/platforms/sky130hd/drc/sky130hd.lydrc

输出：v2_spec/sky130_rules_measured.md 中引用的全部数值。
本脚本只读，不修改 PDK。

用法（需 WSL，PDK 在 WSL 的 /root 下）：
  python3 macros/extract_rules.py
"""
import os
import re
import sys

TLEF = "/root/openroad-flow-scripts/flow/platforms/sky130hd/lef/sky130_fd_sc_hd.tlef"
LYDRC = "/root/openroad-flow-scripts/flow/platforms/sky130hd/drc/sky130hd.lydrc"


def lef_widths(path):
    txt = open(path, encoding="utf-8", errors="replace").read()
    out = {}
    for m in re.finditer(r"^\s*LAYER\s+(\S+)\s*$(.*?)^\s*END\s+\1\s*$",
                         txt, re.S | re.M):
        name, body = m.group(1), m.group(2)
        typ = re.search(r"^\s*TYPE\s+(\S+)\s*;", body, re.M)
        if typ and typ.group(1) != "ROUTING":
            continue
        w = re.search(r"^\s*WIDTH\s+([\d.]+)\s*;", body, re.M)
        if w:
            out[name] = float(w.group(1))
    return out


def drc_rules(path):
    """Pull every rule line that carries a numeric limit for our layers."""
    lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    keep = []
    pat = re.compile(
        r"\b(m1|m2|m3|m4|via1|via2|via3|li1|mcon)\."
        r"(width|space|separation|enclosing|isolated)\s*\(([\d.]+)")
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        for m in pat.finditer(s):
            tag = re.search(r'\.output\("([^"]+)"\s*,\s*"([^"]*)"', s)
            keep.append({
                "line": i + 1,
                "layer": m.group(1),
                "check": m.group(2),
                "value_um": float(m.group(3)),
                "rule_id": tag.group(1) if tag else "",
                "desc": tag.group(2) if tag else "",
            })
    return keep


def main():
    if not os.path.exists(TLEF):
        print("MISSING", TLEF); return 1
    if not os.path.exists(LYDRC):
        print("MISSING", LYDRC); return 1

    print("=" * 64)
    print("LEF min widths")
    print("=" * 64)
    w = lef_widths(TLEF)
    for k in ("li1", "met1", "met2", "met3", "met4", "met5"):
        if k in w:
            print("  %-6s %.3f um" % (k, w[k]))

    print()
    print("=" * 64)
    print("DRC rules (numeric limits, from sky130hd.lydrc)")
    print("=" * 64)
    rules = drc_rules(LYDRC)
    # de-duplicate by rule id, keep first
    seen = set()
    for r in rules:
        key = r["rule_id"] or (r["layer"], r["check"], r["value_um"])
        if key in seen:
            continue
        seen.add(key)
        print("  L%-5d %-6s %-10s %-6.3f  %-14s %s"
              % (r["line"], r["layer"], r["check"], r["value_um"],
                 r["rule_id"], r["desc"][:46]))
    print()
    print("total distinct rules: %d" % len(seen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
