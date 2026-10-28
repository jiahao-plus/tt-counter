#!/usr/bin/env python3
"""p3_gds_identity.py — 逐图形证明七个宏的 GDS 与 HEAD 完全一致。

## 为什么不能只比图形数

上一轮"几何零改动"的结论只比较了每层图形**数量**。数量相同不等于几何相同：
一条线可以从 y=1 平移到 y=2、一个矩形可以翻转、一个多边形可以改形状，
数量都不变。本轮改为逐图形比较。

## 比什么

对每个宏的每种层，把该层所有图形规范化为一个可排序的元组：

    (layer, datatype, shape_kind, 坐标序列)

  * shape_kind ∈ {box, polygon, path}，形状类别本身参与比较 —— box 与 polygon
    即使视觉相同也算不同，因为它们是不同的 GDS 记录。
  * box / polygon 的坐标是**绝对**坐标：`begin_shapes_rec` 已经乘上了层次变换，
    所以"层次变换"这一项不是另外检查，而是被包含在绝对坐标里。
  * 多边形坐标按逆时针规范化后从最小顶点开始旋转，使同一个多边形无论顶点
    起点如何都得到同一序列；box 用 (left, bottom, right, top)。

再对**全部**规范化元组排序并做 SHA-256，得到该宏的几何摘要。

## 为什么这是强证据

摘要相同意味着：层的集合相同、每层的图形多重集合相同、每个图形的形状类别与
绝对坐标相同。文件时间戳、库名、GDS 的 BGNLIB 日期、记录顺序都不参与摘要，
所以它们不同不影响结论 —— 这正是任务要求的"排除文件时间戳差异"。

## 输出去哪

  v2_validation/P4_GDS_IDENTITY.json   逐宏、逐层的 digest 与 PASS/FAIL
  stdout                               一张表
"""
import hashlib
import json
import os
import re
import subprocess
import sys

import pya

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'out')
VAL = os.path.join(ROOT, 'v2_validation')

# Two distinct directories on purpose:
#   HEAD_SRC — where the Windows shell pre-extracts `git cat-file` output.
#              Written once by the caller, never opened for writing here.
#   TMP      — scratch copies this script reads. Keeping them apart matters:
#              an earlier version used one directory for both and truncated
#              the source with open(..., 'wb') before reading it, producing a
#              0-byte file and a confusing "unknown format" error.
HEAD_SRC = os.path.join(HERE, '_tmp_gds_identity')
TMP = os.path.join(HERE, '_tmp_gds_identity_work')

TAGS = ['A', 'B', 'C1', 'C3', 'C4', 'D', 'E']

# GDSII records that legitimately carry a modification date. They are the only
# records allowed to differ between HEAD and the working tree when the geometry
# is unchanged.
TIMESTAMP_RECORDS = {0x0102: 'BGNLIB', 0x0502: 'BGNSTR'}


def gds_records(data):
    """(offset, length, record_type) for every record in a GDSII byte string."""
    i = 0
    while i + 4 <= len(data):
        n = (data[i] << 8) | data[i + 1]
        rt = (data[i + 2] << 8) | data[i + 3]
        if n < 4 or i + n > len(data):
            break
        yield i, n, rt
        i += n


def raw_byte_diff(head_bytes, work_bytes):
    """Every byte that differs, checked against the record it falls in.

    The canonical digest comparison above deliberately ignores timestamps by
    never reading them. This is the complementary, cruder check: compare the
    files byte for byte, then prove that *each* differing byte lies inside a
    BGNLIB or BGNSTR record. Together they say "the files differ, and the only
    thing they differ in is the dates" without either check having to trust the
    other.
    """
    if len(head_bytes) != len(work_bytes):
        return {'ok': False, 'reason': 'file length differs (%d vs %d)'
                % (len(head_bytes), len(work_bytes)),
                'n_diff': None, 'outside': []}
    spans = list(gds_records(head_bytes))
    diffs = [i for i in range(len(head_bytes))
             if head_bytes[i] != work_bytes[i]]
    outside = []
    kinds = set()
    for off in diffs:
        hit = [(s, n, rt) for s, n, rt in spans if s <= off < s + n]
        if len(hit) != 1 or hit[0][2] not in TIMESTAMP_RECORDS:
            outside.append(off)
        else:
            kinds.add(TIMESTAMP_RECORDS[hit[0][2]])
    return {'ok': not outside, 'n_diff': len(diffs),
            'n_bytes': len(head_bytes),
            'n_records': len(spans),
            'timestamp_records_hit': sorted(kinds),
            'outside': outside[:20]}



def canonical_polygon(poly):
    """A rotation-invariant, orientation-normalised vertex list.

    Two polygons that differ only by where the vertex list starts, or by
    winding direction, are the same polygon and must hash the same.
    """
    pts = [(p.x, p.y) for p in poly.each_point_hull()]
    if not pts:
        return ()
    # drop a duplicated closing point if present
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if not pts:
        return ()
    # normalise winding: shoelace sign
    area2 = 0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        area2 += x0 * y1 - x1 * y0
    if area2 < 0:
        pts = pts[::-1]
    # rotate so the lexicographically smallest vertex comes first
    k = min(range(len(pts)), key=lambda i: pts[i])
    pts = pts[k:] + pts[:k]
    return tuple(pts)


def shape_signature(shape, trans):
    """(kind, canonical coordinates) for one shape in ABSOLUTE dbu."""
    if shape.is_box():
        b = shape.box.transformed(trans)
        return ('box', (b.left, b.bottom, b.right, b.top))
    if shape.is_polygon():
        p = shape.polygon.transformed(trans)
        return ('polygon', canonical_polygon(p))
    if shape.is_path():
        p = shape.path.transformed(trans).simple_polygon()
        return ('path', canonical_polygon(p))
    if shape.is_text():
        t = shape.text.transformed(trans)
        return ('text', (t.string, int(t.x), int(t.y)))
    return ('other', ())


def layer_digest(layout, cell, li):
    """Sorted canonical signatures for one layer of one cell, hashed."""
    info = layout.get_info(li)
    sigs = []
    it = cell.begin_shapes_rec(li)
    while not it.at_end():
        s = it.shape()
        sigs.append(shape_signature(s, it.trans()))
        it.next()
    sigs.sort(key=repr)
    h = hashlib.sha256()
    for s in sigs:
        h.update(repr(s).encode())
        h.update(b'\n')
    return info, sigs, h.hexdigest()


def macro_digest(path):
    """{layer_key: {...}} plus a whole-layout digest, for one GDS file.

    Handles multi-top layouts: v2_structures.gds holds all seven cells as
    independent top cells, so `top_cell()` (which asserts a single top) cannot
    be used there. Each top cell is digested separately and the cell name is
    folded into the whole-layout digest, so renaming or reordering cells is
    still detected.
    """
    ly = pya.Layout()
    ly.read(path)
    tops = sorted(ly.top_cells(), key=lambda c: c.name)
    if not tops:
        raise RuntimeError('no top cell in %s' % path)

    per_layer = {}
    whole = hashlib.sha256()
    for top in tops:
        whole.update(('CELL:%s\n' % top.name).encode())
        for li in sorted(ly.layer_indexes()):
            info, sigs, dig = layer_digest(ly, top, li)
            if not sigs:
                continue
            key = '%d/%d' % (info.layer, info.datatype)
            per_layer.setdefault(key, {'name': info.name or '',
                                       'n_shapes': 0, 'kinds': set()})
            e = per_layer[key]
            e['n_shapes'] += len(sigs)
            e['kinds'] |= {k for k, _ in sigs}
            # digest is per (cell, layer); fold both into the layout digest
            whole.update(('%s|%s|%s\n' % (top.name, key, dig)).encode())

    for key, e in per_layer.items():
        e['kinds'] = sorted(e['kinds'])
        # a stable per-layer digest over every contributing cell
        h = hashlib.sha256()
        for top in tops:
            h.update(('%s|' % top.name).encode())
            li = ly.find_layer(*[int(x) for x in key.split('/')])
            if li is None:
                continue
            _, sigs, dig = layer_digest(ly, top, li)
            h.update(dig.encode())
        e['digest'] = h.hexdigest()

    bbox = None
    for top in tops:
        b = top.bbox()
        if bbox is None:
            bbox = pya.Box(b)
        else:
            bbox = bbox + b
    return {
        'cells': [c.name for c in tops],
        'cell': tops[0].name if len(tops) == 1 else '%d cells' % len(tops),
        'dbu': ly.dbu,
        'bbox_dbu': [bbox.left, bbox.bottom, bbox.right, bbox.top],
        'n_layers_nonempty': len(per_layer),
        'layers': per_layer,
        'digest': whole.hexdigest(),
    }


def ensure_head_src():
    """Make sure _tmp_gds_identity/ is populated before comparing.

    That directory is filled by `_prefetch_head_gds.py`, which must run where
    git can actually read the worktree. Under WSL, git cannot (rc=128), but a
    Windows python is usually reachable as `python.exe` through the /mnt/c
    interop layer. Trying it here means the one-click check stays one command;
    if it fails we simply fall through and let checkout_head() report which
    objects are unreadable.
    """
    need = ['head_%s.gds' % t for t in TAGS] + ['head_master.gds']
    if all(os.path.exists(os.path.join(HEAD_SRC, n))
           and os.path.getsize(os.path.join(HEAD_SRC, n)) > 100 for n in need):
        return True
    # A REPO-RELATIVE path with cwd=ROOT, never an absolute one. Under WSL the
    # absolute path is /mnt/c/...; the Windows interpreter running behind
    # `python.exe` would read that as C:\mnt\c\... and fail. The repo path also
    # contains a non-ASCII component (课题/), which the interop layer mangles
    # into '????' whenever it has to round-trip the argument through the ANSI
    # code page — passing a relative path keeps it out of that path entirely.
    script = os.path.relpath(os.path.join(HERE, '_prefetch_head_gds.py'), ROOT)
    err = []
    for exe in ('python.exe', 'py.exe'):
        try:
            r = subprocess.run([exe, script], cwd=ROOT, capture_output=True)
        except FileNotFoundError:
            err.append('%s: not found' % exe)
            continue
        if r.returncode == 0:
            return True
        err.append('%s: rc=%d %s' % (exe, r.returncode,
                                     r.stderr.decode('utf-8', 'replace')[-200:]))
    if err:
        sys.stderr.write('prefetch failed:\n  ' + '\n  '.join(err) + '\n')
    return False


def checkout_head(rel_path, dest):
    """Write HEAD:<rel_path> to dest as RAW BYTES. Returns True on success.

    `git cat-file blob` is used rather than `git show`: `git show` runs the
    blob through attributes/pager machinery, which can text-mangle a binary.
    cat-file returns the object verbatim.

    Called under WSL, where `git` may not see this worktree (the repo was
    created on the Windows side and the .git file points at a Windows path).
    Falls back to a copy the Windows shell pre-extracted into
    _tmp_gds_identity/.
    """
    obj = 'HEAD:%s' % rel_path
    pre = os.path.join(HEAD_SRC, 'head_%s.gds'
                       % os.path.basename(rel_path).replace('struct_', '')
                       .replace('.gds', '').replace('v2_structures', 'master'))
    # A pre-extracted copy (written by the Windows side) is used first, and is
    # COPIED not consumed: WSL's git cannot read this worktree's .git pointer
    # reliably and has been observed returning rc=0 with an unusable blob.
    if os.path.exists(pre) and os.path.getsize(pre) > 100:
        with open(pre, 'rb') as src:
            data = src.read()
        with open(dest, 'wb') as f:
            f.write(data)
        return True
    for args in (['git', 'cat-file', 'blob', obj],
                 ['git', '-C', ROOT, 'cat-file', 'blob', obj]):
        try:
            r = subprocess.run(args, cwd=ROOT, capture_output=True)
        except FileNotFoundError:
            break
        # GDS magic: 0x0006 0x0002 as the first four bytes
        if r.returncode == 0 and r.stdout[:4] == b'\x00\x06\x00\x02':
            with open(dest, 'wb') as f:
                f.write(r.stdout)
            return True
    return False


def main():
    os.makedirs(TMP, exist_ok=True)
    rows, problems = [], []

    if not ensure_head_src():
        problems.append(
            'cannot populate %s — run `python macros/_prefetch_head_gds.py` '
            'from a shell where git can read this worktree' % HEAD_SRC)

    for tag in TAGS:
        rel = 'macros/out/struct_%s.gds' % tag
        cur = os.path.join(OUT, 'struct_%s.gds' % tag)
        old = os.path.join(TMP, 'head_%s.gds' % tag)

        if not checkout_head(rel, old):
            problems.append('%s: cannot read %s from HEAD' % (tag, rel))
            continue

        a = macro_digest(old)
        b = macro_digest(cur)

        layer_keys = sorted(set(a['layers']) | set(b['layers']))
        layer_rows = []
        same = True
        for k in layer_keys:
            la, lb = a['layers'].get(k), b['layers'].get(k)
            if la is None or lb is None:
                same = False
                layer_rows.append({'layer': k, 'head': la, 'work': lb,
                                   'verdict': 'LAYER MISSING'})
                problems.append('%s %s: layer present in only one version'
                                % (tag, k))
                continue
            ok = (la['digest'] == lb['digest']
                  and la['n_shapes'] == lb['n_shapes'])
            if not ok:
                same = False
                problems.append('%s %s: geometry differs (%d vs %d shapes)'
                                % (tag, k, la['n_shapes'], lb['n_shapes']))
            layer_rows.append({
                'layer': k,
                'head': {'n_shapes': la['n_shapes'], 'digest': la['digest'][:16],
                         'kinds': la['kinds']},
                'work': {'n_shapes': lb['n_shapes'], 'digest': lb['digest'][:16],
                         'kinds': lb['kinds']},
                'verdict': 'PASS' if ok else 'FAIL',
            })

        whole_ok = (a['digest'] == b['digest'] and same
                    and a['dbu'] == b['dbu'] and a['bbox_dbu'] == b['bbox_dbu'])
        if not whole_ok:
            problems.append('%s: whole-macro digest differs' % tag)

        # complementary raw-byte check: the files DO differ, and everything
        # they differ in must be a date record
        rb = raw_byte_diff(open(old, 'rb').read(), open(cur, 'rb').read())
        if not rb['ok']:
            problems.append('%s: raw bytes differ outside timestamp records (%s)'
                            % (tag, rb.get('reason')
                               or 'offsets %s' % rb['outside']))

        rows.append({
            'tag': tag,
            'gds': rel,
            'head': {'digest': a['digest'], 'cell': a['cell'],
                     'n_layers': a['n_layers_nonempty'],
                     'n_shapes': sum(v['n_shapes'] for v in a['layers'].values())},
            'work': {'digest': b['digest'], 'cell': b['cell'],
                     'n_layers': b['n_layers_nonempty'],
                     'n_shapes': sum(v['n_shapes'] for v in b['layers'].values())},
            'dbu_ok': a['dbu'] == b['dbu'],
            'bbox_ok': a['bbox_dbu'] == b['bbox_dbu'],
            'raw_bytes': rb,
            'layers': layer_rows,
            'verdict': 'PASS' if (whole_ok and rb['ok']) else 'FAIL',
        })

    # ---- master GDS
    rel = 'macros/out/v2_structures.gds'
    old_m = os.path.join(TMP, 'head_master.gds')
    master_row = None
    if checkout_head(rel, old_m):
        a = macro_digest(old_m)
        b = macro_digest(os.path.join(OUT, 'v2_structures.gds'))
        ok = a['digest'] == b['digest']
        rb = raw_byte_diff(open(old_m, 'rb').read(),
                           open(os.path.join(OUT, 'v2_structures.gds'),
                                'rb').read())
        if not ok:
            problems.append('v2_structures.gds: digest differs')
        if not rb['ok']:
            problems.append('v2_structures.gds: raw bytes differ outside '
                            'timestamp records (%s)' % rb.get('reason'))
        master_row = {'gds': rel,
                      'head_digest': a['digest'], 'work_digest': b['digest'],
                      'raw_bytes': rb,
                      'verdict': 'PASS' if (ok and rb['ok']) else 'FAIL'}

    summary = {
        'method': 'Per-layer, per-shape canonical signature '
                  '(layer/datatype + shape kind + absolute dbu coordinates, '
                  'polygons normalised for winding and vertex start), sorted '
                  'then SHA-256. Hierarchy transforms are applied via '
                  'begin_shapes_rec, so "absolute coordinates" already '
                  'incorporates every hierarchical transformation. File '
                  'timestamps, library names and BGNLIB dates are not part of '
                  'the digest. A second, complementary check compares the raw '
                  'bytes and requires every differing byte to fall inside a '
                  'BGNLIB (0x0102) or BGNSTR (0x0502) date record — the digest '
                  'ignores dates by construction, the byte check proves they '
                  'are the ONLY difference.',
        'all_pass': not problems,
        'problems': problems,
        'macros': rows,
        'master_gds': master_row,
        'scope': 'Compares the working tree against HEAD of the same branch. '
                 'It proves the working tree did not change any macro geometry '
                 'relative to HEAD. It says nothing about V1 — V1 (24fc6a5) has '
                 'no research macros at all, so there is nothing to compare '
                 'these seven against.',
    }
    json.dump(summary, open(os.path.join(VAL, 'P4_GDS_IDENTITY.json'), 'w',
                            encoding='utf-8'), indent=1, ensure_ascii=False)

    # ------------------------------------------------------------- console
    print('%-4s %-6s %-8s %-8s %-9s %-9s %s'
          % ('tag', 'layers', 'shapes', 'shapes', 'HEAD dig', 'WORK dig', 'verdict'))
    print('-' * 78)
    for r in rows:
        print('%-4s %-6d %-8d %-8d %-9s %-9s %s'
              % (r['tag'], r['work']['n_layers'],
                 r['head']['n_shapes'], r['work']['n_shapes'],
                 r['head']['digest'][:8], r['work']['digest'][:8], r['verdict']))
    if master_row:
        print('%-4s %-6s %-8s %-8s %-9s %-9s %s'
              % ('ALL', '-', '-', '-', master_row['head_digest'][:8],
                 master_row['work_digest'][:8], master_row['verdict']))
    print()
    print('raw bytes — every differing byte must fall inside a BGNLIB/BGNSTR date:')
    print('%-4s %-8s %-10s %-22s %s'
          % ('tag', 'len', 'diff bytes', 'date records hit', 'outside dates'))
    print('-' * 78)
    for r in rows:
        rb = r['raw_bytes']
        print('%-4s %-8s %-10s %-22s %s'
              % (r['tag'], rb.get('n_bytes', '-'), rb.get('n_diff', '-'),
                 ','.join(rb.get('timestamp_records_hit') or []) or '-',
                 rb.get('reason') or (rb['outside'] or 'NONE')))
    if master_row:
        rb = master_row['raw_bytes']
        print('%-4s %-8s %-10s %-22s %s'
              % ('ALL', rb.get('n_bytes', '-'), rb.get('n_diff', '-'),
                 ','.join(rb.get('timestamp_records_hit') or []) or '-',
                 rb.get('reason') or (rb['outside'] or 'NONE')))
    print()

    # per-layer table for one macro, to show the granularity
    for r in rows:
        if r['verdict'] == 'FAIL':
            print('per-layer detail for %s:' % r['tag'])
            for l in r['layers']:
                print('   %-8s %-4s head=%s work=%s'
                      % (l['layer'], l['verdict'],
                         (l['head'] or {}).get('digest', '-'),
                         (l['work'] or {}).get('digest', '-')))

    # ------------------------------------------------------------- markdown
    md = ['# GDS 几何一致性（逐图形）', '',
          '自动生成：`macros/p3_gds_identity.py`  ',
          '比较对象：工作区 `macros/out/struct_*.gds` ↔ `git show HEAD:...`', '',
          '## 方法', '',
          '每个宏、每种层，把该层全部图形规范化为 `(layer, datatype, 形状类别, 绝对坐标)`，',
          '排序后做 SHA-256。多边形按缠绕方向与起始顶点规范化。',
          '层次变换由 `begin_shapes_rec` 应用到坐标上，因此"绝对坐标一致"已包含',
          '层次变换一致。文件时间戳、库名、BGNLIB 日期不参与摘要。', '',
          '> 上一轮只比较了每层图形**数量**。数量相同不等于几何相同——一条线平移、',
          '> 一个矩形翻转、一个多边形改形状，数量都不变。本轮改为逐图形比较。', '',
          '## 结果', '',
          '| 宏 | 非空层 | HEAD 图形数 | 工作区图形数 | HEAD 摘要 | 工作区摘要 | 判定 |',
          '|---|---|---|---|---|---|---|']
    for r in rows:
        md.append('| %s | %d | %d | %d | `%s` | `%s` | **%s** |'
                  % (r['tag'], r['work']['n_layers'], r['head']['n_shapes'],
                     r['work']['n_shapes'], r['head']['digest'][:16],
                     r['work']['digest'][:16], r['verdict']))
    if master_row:
        md.append('| ALL | — | — | — | `%s` | `%s` | **%s** |'
                  % (master_row['head_digest'][:16],
                     master_row['work_digest'][:16], master_row['verdict']))
    md += ['', '## 逐层明细', '']
    for r in rows:
        md.append('### %s — %s' % (r['tag'], r['gds']))
        md.append('')
        md.append('| 层 | HEAD 图形 | 工作区图形 | HEAD 摘要 | 工作区摘要 | 判定 |')
        md.append('|---|---|---|---|---|---|')
        for l in r['layers']:
            h = l['head'] or {}
            w = l['work'] or {}
            md.append('| %s | %s | %s | `%s` | `%s` | %s |'
                      % (l['layer'], h.get('n_shapes', '—'),
                         w.get('n_shapes', '—'),
                         h.get('digest', '—'), w.get('digest', '—'),
                         l['verdict']))
        md.append('')
    md += ['', '## 逐字节对照（时间戳）', '',
           '摘要比较**不读**时间戳，所以它证明不了"两个文件只差时间戳"。本节做',
           '相反的检查：逐字节比较，并要求**每一个**不同的字节都落在 `BGNLIB`',
           '(0x0102) 或 `BGNSTR` (0x0502) 日期记录内部。', '',
           '| 文件 | 字节数 | 不同字节 | 命中的日期记录 | 日期记录之外 |',
           '|---|---|---|---|---|']
    for r in rows + ([master_row] if master_row else []):
        rb = r['raw_bytes']
        md.append('| %s | %s | %s | %s | %s |'
                  % (r.get('tag', 'ALL'), rb.get('n_bytes', '—'),
                     rb.get('n_diff', '—'),
                     ', '.join(rb.get('timestamp_records_hit') or []) or '—',
                     rb.get('reason') or ('**%d**' % len(rb['outside'])
                                          if rb['outside'] else 'NONE')))
    md += ['', '## 结论', '']
    if problems:
        md.append('**FAIL** — %d 个问题：' % len(problems))
        for p in problems:
            md.append('- %s' % p)
    else:
        md.append('**PASS** — 七个宏加合并版，逐图形摘要与 HEAD 完全一致。')
        md.append('')
        md.append('> 这证明工作区没有改动任何宏的几何。V1（`24fc6a5`）里根本没有')
        md.append('> 这些研究宏，因此不存在"与 V1 比较"这件事。')
    open(os.path.join(VAL, 'P4_GDS_IDENTITY.md'), 'w',
         encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')

    print('written v2_validation/P4_GDS_IDENTITY.{json,md}')
    if problems:
        print()
        print('FAIL — %d problem(s):' % len(problems))
        for p in problems:
            print('  !', p)
        return 1
    print('PASS — all seven macros byte-identical in geometry to HEAD')
    return 0


if __name__ == '__main__':
    sys.exit(main())
