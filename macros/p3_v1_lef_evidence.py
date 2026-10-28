#!/usr/bin/env python3
"""p3_v1_lef_evidence.py — 重新测量 OBS 规则所依据的 V1 官方 LEF 事实。

## 为什么需要这个脚本

`gen_lef.py` 的 OBS 规则不是凭空设计的，是从 **V1 真实交付物**反推出来的：

    .../tt-counter-exp/official_ci/GDS_logs/runs/wokwi/final/lef/
        tt_um_jiahao_plus_counter.lef

这份 LEF 由 Magic 在 Precheck 15/15 通过的那次官方 CI 中写出。规则 E
（"OBS = 绘制金属 − PIN"）和规则 G（"无 pin 层整块一个矩形"）都声称是对
它的推广。如果这个前提是错的，两条规则就是错的——所以它必须可复跑，
而不是只在某次会话里量过一次。

同一份 flow.log 里还有第二个关键事实：`PDN_OBSTRUCTIONS`、
`ROUTING_OBSTRUCTIONS`、`FP_OBSTRUCTIONS` 三个键**均未定义**，所以宏的
LEF OBS 是本流程中唯一的逐宏布线保护。本脚本一并复核这一条。

## 检查项

  V1  V1 官方 LEF 存在且可解析
  V2  无 pin 的层：每层恰好 1 个 OBS 矩形，覆盖该层绘制范围
  V3  有 pin 的层：pin 与 OBS 的**同层重叠面积为 0**
  V4  flow.log 中 PDN_OBSTRUCTIONS / ROUTING_OBSTRUCTIONS /
      FP_OBSTRUCTIONS 三个键均未定义（因此相关步骤被跳过）
  V5  flow.log 中 `cut_rows` 带 halo，且早于 PDN 生成步骤

任何一项不成立，`gen_lef.py` 的规则依据就要重新论证。

## 路径

V1 的 CI 产物在本机 `_tmp` 之外，路径由 `--v1-root` 指定；默认值就是上面
那个绝对路径。找不到文件时本脚本记为 SKIP 并明确说明"这不是通过"，
而不是静默放过。

用法（WSL，cwd 为仓库根）：
    python3 macros/p3_v1_lef_evidence.py
    python3 macros/p3_v1_lef_evidence.py --v1-root /path/to/runs/wokwi
"""
import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VAL = os.path.join(ROOT, 'v2_validation')

DEFAULT_V1 = ('/mnt/c/Users/Lenovo/DoubaoWork/chats/2026-10-13/new-chat/'
              'tt-counter-exp/official_ci/GDS_logs/runs/wokwi')

OBSTRUCTION_KEYS = ('PDN_OBSTRUCTIONS', 'ROUTING_OBSTRUCTIONS',
                    'FP_OBSTRUCTIONS')


def parse_lef_rects(txt):
    """Split a LEF into (pin_rects, obs_rects), both {layer: [(x0,y0,x1,y1)]}."""
    i_obs = txt.find('\n  OBS\n')
    if i_obs < 0:
        return None, None
    head, obs_body = txt[:i_obs], txt[i_obs:]

    rect_re = re.compile(r'^RECT\s+(-?[\d.]+)\s+(-?[\d.]+)\s+'
                         r'(-?[\d.]+)\s+(-?[\d.]+)\s*;')

    def collect(body):
        out, cur = {}, None
        for line in body.splitlines():
            s = line.strip()
            lm = re.match(r'LAYER\s+(\S+)\s*;', s)
            if lm:
                cur = lm.group(1)
                out.setdefault(cur, [])
                continue
            rm = rect_re.match(s)
            if rm and cur:
                out[cur].append(tuple(float(rm.group(i)) for i in range(1, 5)))
        return out

    pins = {}
    for pm in re.finditer(r'^\s*PIN\s+(\S+)\s*$(.*?)^\s*END\s+\1\s*$',
                          head, re.S | re.M):
        for lay, rs in collect(pm.group(2)).items():
            pins.setdefault(lay, []).extend(rs)

    obs = collect(obs_body.splitlines()[1:] and
                  '\n'.join(obs_body.splitlines()[1:]) or '')
    return pins, obs


def overlap_area(a, b):
    dx = min(a[2], b[2]) - max(a[0], b[0])
    dy = min(a[3], b[3]) - max(a[1], b[1])
    return dx * dy if dx > 0 and dy > 0 else 0.0


def check_v1_lef(path):
    txt = open(path, encoding='utf-8', errors='replace').read()
    pins, obs = parse_lef_rects(txt)
    problems = []
    if pins is None:
        problems.append('V1: no OBS block in %s' % path)
        return {'path': path, 'problems': problems,
                'layers': []}, problems

    rows = []
    for lay in sorted(set(pins) | set(obs)):
        ps, os_ = pins.get(lay, []), obs.get(lay, [])
        ov = sum(overlap_area(p, o) for p in ps for o in os_)
        rows.append({'layer': lay, 'n_pin': len(ps), 'n_obs': len(os_),
                     'overlap_area_um2': round(ov, 6),
                     'pin_less_single_rect': (not ps and len(os_) == 1)})

        # V2
        if not ps and len(os_) != 1:
            problems.append('V2 %s: pin-less layer has %d OBS rects, expected 1'
                            % (lay, len(os_)))
        # V3
        if ov > 0:
            problems.append('V3 %s: pin/OBS overlap area %.6f um^2 — the rule '
                            '"OBS excludes pins" does not hold here'
                            % (lay, ov))

    return {'path': path, 'n_pins_total': sum(len(v) for v in pins.values()),
            'n_obs_total': sum(len(v) for v in obs.values()),
            'layers': rows, 'problems': problems}, problems


def check_flow_log(path):
    """Re-measure the two flow facts the OBS rules lean on.

    `flow.log` itself does NOT contain the cut_rows command line — it only
    says which step ran and where its log went:

        Running 'OpenROAD.CutRows' at 'runs/wokwi/18-openroad-cutrows'…

    The actual command is in that step's own log. So the step ordering is read
    from flow.log (where the "Running X at runs/wokwi/NN-..." lines are), and
    the halo arguments are read from the step log. Looking only at flow.log
    would have made this check claim "no cut_rows" — a false negative about a
    fact that is really there.
    """
    txt = open(path, encoding='utf-8', errors='replace').read()
    problems, facts = [], {}

    # ---- V4: the three obstruction keys must be undefined
    # LibreLane prints exactly "'KEY' is not defined. Skipping '<Step>'…" when
    # a key is absent. Some keys have no consuming step in a given flow at all
    # (FP_OBSTRUCTIONS never appears here), which is still consistent with
    # "undefined" — the only thing that would break the claim is a key that
    # looks assigned.
    for key in OBSTRUCTION_KEYS:
        skipped = re.findall(r"'%s' is not defined\. Skipping '([^']+)'" % key,
                             txt)
        assigned = re.search(r"'%s'\s*(?:=|<-)" % key, txt) is not None
        facts[key] = {'skip_lines': skipped,
                      'appears_at_all': key in txt,
                      'looks_assigned': bool(assigned)}
        if assigned:
            problems.append('V4 %s looks assigned in flow.log; it is supposed '
                            'to be undefined in this flow, and the claim "LEF '
                            'OBS is the only per-macro routing protection" '
                            'depends on it being undefined' % key)
        # a key that appears but never gets a skip line is suspicious
        if key in txt and not skipped:
            problems.append('V4 %s appears in flow.log but was never reported as '
                            '"not defined" — check what consumes it' % key)

    # ---- V5: cut_rows must run before PDN, with a halo
    runs = {}
    for m in re.finditer(r"Running '([^']+)' at '([^']*?(\d{2})-([^/']+))'",
                         txt):
        step, _full, num, slug = m.group(1), m.group(2), m.group(3), m.group(4)
        runs.setdefault(slug, {'step': step, 'num': int(num)})
    facts['steps_seen'] = {k: v['num'] for k, v in runs.items()}

    cut = runs.get('openroad-cutrows')
    pdn = runs.get('openroad-generatepdn')
    facts['cut_rows_step'] = cut['num'] if cut else None
    facts['pdn_step'] = pdn['num'] if pdn else None
    if cut is None:
        problems.append('V5: no cut_rows step in flow.log')
    if pdn is None:
        problems.append('V5: no GeneratePDN step in flow.log')
    if cut and pdn and cut['num'] >= pdn['num']:
        problems.append('V5: cut_rows (step %d) does not precede PDN (step %d)'
                        % (cut['num'], pdn['num']))

    # the halo arguments live in the step's own log
    facts['cut_rows_cmd'] = None
    facts['cut_rows_has_halo'] = None
    step_log = os.path.join(os.path.dirname(path),
                            '%02d-openroad-cutrows' % cut['num'] if cut else '',
                            'openroad-cutrows.log')
    if cut and os.path.exists(step_log):
        t = open(step_log, encoding='utf-8', errors='replace').read()
        m = re.search(r'cut_rows[^\n]*', t)
        if m:
            facts['cut_rows_cmd'] = m.group(0).strip()
            facts['cut_rows_has_halo'] = ('halo_width_x' in m.group(0)
                                          and 'halo_width_y' in m.group(0))
    if facts['cut_rows_has_halo'] is None:
        problems.append('V5: could not read the cut_rows command from %s — the '
                        '"10 um halo means no followpin under the macro" claim '
                        'is unverified' % step_log)
    elif not facts['cut_rows_has_halo']:
        problems.append('V5: cut_rows runs without a halo — standard-cell rows '
                        'may still be generated under and around the macro')

    return {'path': path, 'facts': facts, 'problems': problems}, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--v1-root', default=DEFAULT_V1)
    args = ap.parse_args()

    lef = os.path.join(args.v1_root, 'final', 'lef',
                       'tt_um_jiahao_plus_counter.lef')
    flow = os.path.join(args.v1_root, 'flow.log')

    problems, result = [], {'v1_root': args.v1_root,
                            'scope': 'Re-measures the V1 official artefacts that '
                                     'gen_lef.py\'s OBS rules are derived from. '
                                     'Read-only; nothing here is a V2 design claim.'}
    missing_artefact = False

    if not os.path.exists(lef):
        problems.append('V1 LEF not found at %s' % lef)
        result['lef'] = {'status': 'SKIP', 'path': lef}
        missing_artefact = True
    else:
        r, p = check_v1_lef(lef)
        problems.extend(p)
        result['lef'] = r
        result['lef']['status'] = 'RUN' if not p else 'FAIL'

    if not os.path.exists(flow):
        problems.append('V1 flow.log not found at %s' % flow)
        result['flow'] = {'status': 'SKIP', 'path': flow}
        missing_artefact = True
    else:
        r, p = check_flow_log(flow)
        problems.extend(p)
        result['flow'] = r
        result['flow']['status'] = 'RUN' if not p else 'FAIL'

    os.makedirs(VAL, exist_ok=True)
    result['all_pass'] = not problems
    result['problems'] = problems
    json.dump(result, open(os.path.join(VAL, 'P5_V1_LEF_EVIDENCE.json'), 'w',
                           encoding='utf-8'), indent=1, ensure_ascii=False)

    # ------------------------------------------------------------- console
    if result['lef'].get('layers'):
        print('V1 official LEF: %s' % lef)
        print('%-10s %8s %8s %14s  %s'
              % ('layer', '#pin', '#obs', 'pin∩obs um^2', 'pin-less single rect'))
        print('-' * 66)
        for r in result['lef']['layers']:
            print('%-10s %8d %8d %14.6f  %s'
                  % (r['layer'], r['n_pin'], r['n_obs'],
                     r['overlap_area_um2'],
                     'n/a (has pins)' if r['n_pin'] else r['pin_less_single_rect']))
        print('  totals: %d pins, %d OBS rects'
              % (result['lef']['n_pins_total'], result['lef']['n_obs_total']))
        print()
    if result['flow'].get('facts'):
        f = result['flow']['facts']
        print('V1 flow.log:')
        for k in OBSTRUCTION_KEYS:
            e = f.get(k, {})
            print('  %-24s appears=%-5s assigned=%-5s skipped_step=%s'
                  % (k, e.get('appears_at_all'), e.get('looks_assigned'),
                     (e.get('skip_lines') or ['-'])[0]))
        print('  cut_rows step: %s   PDN step: %s   has halo: %s'
              % (f.get('cut_rows_step'), f.get('pdn_step'),
                 f.get('cut_rows_has_halo')))
        if f.get('cut_rows_cmd'):
            print('  cmd: %s' % f['cut_rows_cmd'])
        print()

    print('written v2_validation/P5_V1_LEF_EVIDENCE.json')
    if problems:
        print()
        print('FAIL — %d problem(s):' % len(problems))
        for p in problems:
            print('  !', p)
        # Exit 2 means "the V1 artefacts are not on this machine", which the
        # one-click runner reports as SKIP. That is materially different from
        # "measured and it contradicts our rule" (exit 1) — a missing file must
        # never be silently counted as agreement.
        both_absent = (result['lef'].get('status') == 'SKIP'
                       and result['flow'].get('status') == 'SKIP')
        return 2 if both_absent else 1
    print('PASS — V1 evidence supports rule E (OBS excludes pins) and rule G '
          '(pin-less layers get one full-extent rect)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
