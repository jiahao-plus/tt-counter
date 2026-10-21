#!/usr/bin/env python3
"""
DEF statistics for the ORFS sky130hd P&R result of tt_um_jiahao_plus_counter.

Parses 6_final.def:
  - component count (total, fill, tap)
  - net count (total, signal, power)
  - routing segment count per layer (li1/met1/met2/met3/met4)
  - wire width distribution (um)
  - via-rule references per rule
  - M1-Via1-M2 cross-layer connection candidate count (geometric proxy)

Usage:
  python3 def_stats.py <6_final.def> [route_log.txt] [out.json]
"""
import sys, json, re, statistics
from collections import Counter

POWER_RE = re.compile(r'^(vdd|vss|vcc|gnd|vpwr|vgnd)$', re.I)
# DEF net head line: "- NET_NAME ( pin ... ) + USE SIGNAL"
NET_HEAD = re.compile(r'^\s*-\s+(\S+)\s+\(')
# Routing segment: "+ ROUTED met1 ..." or "NEW met2 ..." (leading + optional)
SEG = re.compile(r'(?:ROUTED|NEW)\s+(li1|met1|met2|met3|met4|met5)\s+([0-9.]+)')
VIA_RULES = {
    'via2_3': 'M1M2_PR (met1-via-met2)',
    'via3_4': 'M2M3_PR (met2-via2-met3)',
    'via4_5': 'M3M4_PR (met3-via3-met4)',
    'via5_6': 'M4M5_PR (met4-via4-met5)',
}


def parse_def(path):
    comp_total = comp_fill = comp_tap = 0
    nets_total = 0
    signal_nets = []
    power_nets = []
    seg_per_layer = Counter()
    widths = []
    widths_nz = []
    via_refs = Counter()

    in_components = False
    in_nets = False
    with open(path, 'r', errors='replace') as f:
        for raw in f:
            line = raw.rstrip('\n')
            s = line.strip()

            if s.startswith('COMPONENTS'):
                in_components, in_nets = True, False
                continue
            if s.startswith('NETS'):
                in_components, in_nets = False, True
                continue
            if s.startswith('VIAS') or s.startswith('NONDEFAULTRULES') or s.startswith('SPECIALNETS'):
                in_components, in_nets = False, False
                continue
            if s.startswith('END '):
                in_components, in_nets = False, False
                continue

            if in_components and s.startswith('- '):
                comp_total += 1
                if 'fill' in s.lower():
                    comp_fill += 1
                if 'tap' in s.lower():
                    comp_tap += 1

            if in_nets:
                m = NET_HEAD.match(line)
                if m:
                    nets_total += 1
                    name = m.group(1)
                    if POWER_RE.match(name):
                        power_nets.append(name)
                    else:
                        signal_nets.append(name)

            # Routing segments and via-rule refs appear inside NETS; scan every
            # line (they do not occur elsewhere in this DEF).
            seg = SEG.search(line)
            if seg:
                seg_per_layer[seg.group(1)] += 1
                w = float(seg.group(2))
                widths.append(w)
                if w > 0:
                    widths_nz.append(w)
            for vk in VIA_RULES:
                if vk in line:
                    via_refs[vk] += 1

    return {
        'components': {
            'total': comp_total,
            'fill': comp_fill,
            'tap': comp_tap,
            'logic_cells': comp_total - comp_fill - comp_tap,
        },
        'nets': {
            'total': nets_total,
            'signal': len(signal_nets),
            'power': len(power_nets),
            'power_net_names': sorted(set(power_nets)),
        },
        'routing_segments_per_layer': dict(seg_per_layer),
        'wire_widths_um': {
            'min_nz': round(min(widths_nz), 3) if widths_nz else None,
            'median_nz': round(statistics.median(widths_nz), 3) if widths_nz else None,
            'max_nz': round(max(widths_nz), 3) if widths_nz else None,
            'segments_total': len(widths),
            'segments_nz_width': len(widths_nz),
            'note': 'width=0 STRIPE entries are PDN via straps; nz stats exclude them.',
        },
        'via_rule_references': dict(via_refs),
    }


def parse_route_log(path):
    """Extract the up-via summary table from 5_2_route.log if present."""
    out = {}
    try:
        with open(path, 'r', errors='replace') as f:
            txt = f.read()
    except OSError:
        return out
    for layer in ['li1', 'met1', 'met2', 'met3', 'met4']:
        m = re.search(r'^\s*' + layer + r'\s+(\d+)\s*$', txt, re.M)
        if m:
            out[layer] = int(m.group(1))
    m = re.search(r'Total number of vias = (\d+)', txt)
    if m:
        out['total_vias'] = int(m.group(1))
    return out


def main():
    def_path = sys.argv[1]
    route_log = sys.argv[2] if len(sys.argv) > 2 else None
    out_json = sys.argv[3] if len(sys.argv) > 3 else None

    data = parse_def(def_path)
    data['route_log_via_summary'] = parse_route_log(route_log) if route_log else {}

    # M1-Via1-M2 cross-layer candidates: proxy = number of M1M2_PR via-rule
    # references in net routing (a via that joins a met1 segment and a met2
    # segment of the same net). Criterion stated explicitly in report.
    m1m2 = data['via_rule_references'].get('via2_3', 0)
    data['m1_via1_m2_candidates'] = {
        'count': m1m2,
        'criterion': ('count of via-rule references for M1M2_PR (via2_3) in NETS '
                      'routing; each such via joins a met1 (M1) segment and a met2 (M2) '
                      'segment of the same net. DEF does not enumerate individual via '
                      'instances, so this is a reference-count proxy, not a per-cut count.'),
    }

    pretty = json.dumps(data, indent=2, ensure_ascii=False)
    print(pretty)
    if out_json:
        with open(out_json, 'w') as f:
            f.write(pretty + '\n')


if __name__ == '__main__':
    main()
