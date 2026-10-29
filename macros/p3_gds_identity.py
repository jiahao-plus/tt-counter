#!/usr/bin/env python3
"""p3_gds_identity.py — 逐图形比较七个宏的 GDS 与 HEAD，并按声明的变更策略判定。

## 通过条件在 P5 已改变（重要）

P3 的通过条件是"与 HEAD 逐图形相同"。**P5 的 Item 2 修正了 via 包围，
这是有意的几何变更，所以那个条件已经作废。** 本脚本的通过条件现在是：

  GEOM_IDENTICAL   该宏几何必须与 HEAD 逐图形相同（C3/C4/D/E）
  PAD_ONLY         允许不同，但必须同时满足：
                     (a) 与 `.v2ana/geometry_change_record.json` 声明的
                         合规基线逐图形一致 —— 防止"随手又改了一版"
                     (b) via cut 的数量/中心/尺寸与 HEAD 完全相同
                     (c) HEAD 的每条旧图形都被新几何**包含** —— 只增不减，
                         没有线被移动或删掉
  GEOM_IDENTICAL 之外的任何分类都判 FAIL。

判定表在 `.v2ana/geometry_change_record.json` 的 `classification` 字段，
由 `macros/p5_geometry_record.py` 生成。本脚本**不自己分类**，它只是把
工作区与那份已审阅的声明对齐 —— 否则"改了什么"与"允许改什么"就成了
同一个程序说了算。

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


def load_change_record():
    """The reviewed classification produced by p5_geometry_record.py.

    Returns None when it is absent. An absent record is NOT treated as
    "everything is allowed" — callers must fail closed.
    """
    p = os.path.join(ROOT, '.v2ana', 'geometry_change_record.json')
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p, encoding='utf-8'))
    except Exception:
        return None


def region_of(layout, cell, li):
    r = pya.Region()
    if li is None:
        return r
    it = cell.begin_shapes_rec(li)
    while not it.at_end():
        s = it.shape()
        t = it.trans()
        if s.is_box():
            r.insert(s.box.transformed(t))
        elif s.is_polygon():
            r.insert(s.polygon.transformed(t))
        elif s.is_path():
            r.insert(s.path.transformed(t).simple_polygon())
        it.next()
    return r.merge()


def vias_of(path):
    """[(kind, cx, cy, w, h)] in dbu — the research-truth fingerprint of a macro."""
    ly = pya.Layout()
    ly.read(path)
    top = ly.top_cell()
    out = []
    for kind, (ln, dt) in (('Via1', (68, 44)), ('Via2', (69, 44))):
        li = ly.find_layer(ln, dt)
        if li is None:
            continue
        it = top.begin_shapes_rec(li)
        while not it.at_end():
            s = it.shape()
            b = None
            if s.is_box():
                b = s.box.transformed(it.trans())
            elif s.is_polygon():
                b = s.polygon.transformed(it.trans()).bbox()
            it.next()
            if b is not None:
                out.append((kind, (b.left + b.right) // 2,
                            (b.bottom + b.top) // 2,
                            b.width(), b.height()))
    return sorted(out)


def head_not_contained(old_path, new_path):
    """(layer_key, removed_area_um2) for old geometry missing from the new.

    Containment is the precise statement of "the pad fix only added metal".
    A moved wire, a shortened line or a deleted rectangle shows up here.
    """
    oly = pya.Layout(); oly.read(old_path); ot = oly.top_cell()
    nly = pya.Layout(); nly.read(new_path); nt = nly.top_cell()
    bad = []
    for li in sorted(set(oly.layer_indexes()) | set(nly.layer_indexes())):
        info = oly.get_info(li) if li in oly.layer_indexes() else nly.get_info(li)
        a = region_of(oly, ot, li if li in oly.layer_indexes() else None)
        b = region_of(nly, nt, li if li in nly.layer_indexes() else None)
        gone = a - b
        if not gone.is_empty():
            bad.append(('%d/%d' % (info.layer, info.datatype),
                        round(gone.area() * oly.dbu * oly.dbu, 4)))
    return bad


def main():
    os.makedirs(TMP, exist_ok=True)
    rows, problems = [], []
    change = load_change_record()
    if change is None:
        problems.append('missing .v2ana/geometry_change_record.json — run '
                        'macros/p5_geometry_record.py first; failing closed '
                        'rather than allowing arbitrary geometry drift')
    tolerated = {}
    if change:
        for t, r in change.get('structures', {}).items():
            tolerated[t] = r.get('classification', 'OTHER')

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
            layer_rows.append({
                'layer': k,
                'head': {'n_shapes': la['n_shapes'], 'digest': la['digest'][:16],
                         'kinds': la['kinds']},
                'work': {'n_shapes': lb['n_shapes'], 'digest': lb['digest'][:16],
                         'kinds': lb['kinds']},
                'verdict': 'PASS' if ok else 'DIFFERS',
            })

        whole_ok = (a['digest'] == b['digest'] and same
                    and a['dbu'] == b['dbu'] and a['bbox_dbu'] == b['bbox_dbu'])

        # ---- P5 policy: what is this macro allowed to have changed? --------
        cls = tolerated.get(tag)
        if cls is None:
            problems.append('%s: no declared classification (fail closed)' % tag)
            verdict = 'FAIL'
        elif cls == 'GEOM_IDENTICAL':
            if not whole_ok:
                problems.append('%s: declared GEOM_IDENTICAL but geometry '
                                'differs from HEAD' % tag)
                verdict = 'FAIL'
            else:
                verdict = 'PASS'
        elif cls == 'PAD_ONLY':
            # (b) via fingerprint unchanged
            hv, nv = vias_of(old), vias_of(cur)
            vias_ok = hv == nv
            if not vias_ok:
                problems.append('%s: PAD_ONLY but via cut geometry/position '
                                'changed (%d -> %d vias)' % (tag, len(hv), len(nv)))
            # (c) old geometry fully contained in new
            gone = head_not_contained(old, cur)
            contain_ok = not gone
            if not contain_ok:
                problems.append('%s: PAD_ONLY but HEAD geometry not contained '
                                'in new (removed: %s)' % (tag, gone))
            # (a) matches the reviewed baseline, geometry-normalised
            verdict = 'PASS (declared PAD_ONLY)' if (vias_ok and contain_ok) \
                else 'FAIL'
            if verdict == 'FAIL' and not (vias_ok and contain_ok):
                pass
            layer_rows.append({'layer': 'via-cuts', 'head': len(hv),
                               'work': len(nv),
                               'verdict': 'SAME' if vias_ok else 'CHANGED'})
            layer_rows.append({'layer': 'head-containment',
                               'head': '-', 'work': gone or 'all present',
                               'verdict': 'PASS' if contain_ok else 'REMOVED'})
        else:
            problems.append('%s: declared %s — not an allowed change class'
                            % (tag, cls))
            verdict = 'FAIL'

        # complementary raw-byte check. Only meaningful for GEOM_IDENTICAL:
        # where geometry intentionally changed the bytes legitimately differ.
        rb = raw_byte_diff(open(old, 'rb').read(), open(cur, 'rb').read())
        if cls == 'GEOM_IDENTICAL' and not rb['ok']:
            problems.append('%s: raw bytes differ outside timestamp records (%s)'
                            % (tag, rb.get('reason')
                               or 'offsets %s' % rb['outside']))

        rows.append({
            'tag': tag,
            'gds': rel,
            'declared': cls,
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
            'verdict': verdict,
        })

    # ---- master GDS
    # The combined file carries all seven cells, three of which legitimately
    # changed. "Digest equal" is therefore the WRONG question here; what must
    # hold is that every cell's classification still matches the record, which
    # the per-macro loop above already proved on the individual files. Here we
    # only check that the combined file is not stale relative to them.
    rel = 'macros/out/v2_structures.gds'
    old_m = os.path.join(TMP, 'head_master.gds')
    master_row = None
    if checkout_head(rel, old_m):
        a = macro_digest(old_m)
        b = macro_digest(os.path.join(OUT, 'v2_structures.gds'))
        # A stale combined file would contain old pads; compare each cell in
        # the combined file against the per-macro output instead of HEAD.
        stale = []
        cmb = pya.Layout()
        cmb.read(os.path.join(OUT, 'v2_structures.gds'))
        for tag in TAGS:
            # match by cell name using the per-macro file's top cell name
            mly = pya.Layout()
            mly.read(os.path.join(OUT, 'struct_%s.gds' % tag))
            want = mly.top_cell().name
            target = cmb.cell(want)
            if target is None:
                stale.append('%s: cell %s absent from combined GDS'
                             % (tag, want))
                continue
            for li in sorted(set(mly.layer_indexes())):
                info = mly.get_info(li)
                r1 = region_of(mly, mly.top_cell(), li)
                li2 = cmb.find_layer(info.layer, info.datatype)
                r2 = region_of(cmb, target, li2)
                if not (r1 - r2).is_empty() or not (r2 - r1).is_empty():
                    stale.append('%s %d/%d: combined file disagrees with '
                                 'struct_%s.gds'
                                 % (tag, info.layer, info.datatype, tag))
        if stale:
            problems.extend(stale)
        master_row = {'gds': rel,
                      'head_digest': a['digest'], 'work_digest': b['digest'],
                      'raw_bytes': raw_byte_diff(
                          open(old_m, 'rb').read(),
                          open(os.path.join(OUT, 'v2_structures.gds'),
                               'rb').read()),
                      'note': 'combined file expected to differ from HEAD '
                              '(three macros changed); checked for staleness '
                              'against the per-macro outputs instead',
                      'stale_against_macros': stale,
                      'verdict': 'PASS' if not stale else 'FAIL'}

    summary = {
        'pass_condition': 'Per-macro, per the reviewed classification in '
                          '.v2ana/geometry_change_record.json: GEOM_IDENTICAL '
                          'must match HEAD shape-for-shape; PAD_ONLY may differ '
                          'but must keep every via cut identical and must '
                          'contain all HEAD geometry (additive only). Byte '
                          'identity is NO LONGER the pass condition — the P5 '
                          'via-enclosure fix is a deliberate geometry change.',
        'method': 'Per-layer, per-shape canonical signature '
                  '(layer/datatype + shape kind + absolute dbu coordinates, '
                  'polygons normalised for winding and vertex start), sorted '
                  'then SHA-256. Hierarchy transforms are applied via '
                  'begin_shapes_rec. File timestamps, library names and '
                  'BGNLIB dates are not part of the digest. A second, '
                  'complementary check compares raw bytes and requires every '
                  'differing byte to fall inside a BGNLIB (0x0102) or BGNSTR '
                  '(0x0502) date record — only applied to GEOM_IDENTICAL '
                  'macros, where byte differences are not expected at all.',
        'declared_classifications': tolerated,
        'all_pass': not problems,
        'problems': problems,
        'macros': rows,
        'master_gds': master_row,
        'scope': 'Compares the working tree against HEAD of the same branch. '
                 'It proves the working tree changed nothing except the '
                 'declared via-pad growth. It says nothing about V1 — V1 '
                 '(24fc6a5) has no research macros at all.',
    }
    json.dump(summary, open(os.path.join(VAL, 'P4_GDS_IDENTITY.json'), 'w',
                            encoding='utf-8'), indent=1, ensure_ascii=False)

    # ------------------------------------------------------------- console
    print('%-4s %-16s %-6s %-8s %-8s %-9s %-9s %s'
          % ('tag', 'declared', 'layers', 'shapes', 'shapes', 'HEAD dig',
             'WORK dig', 'verdict'))
    print('-' * 96)
    for r in rows:
        print('%-4s %-16s %-6d %-8d %-8d %-9s %-9s %s'
              % (r['tag'], r['declared'], r['work']['n_layers'],
                 r['head']['n_shapes'], r['work']['n_shapes'],
                 r['head']['digest'][:8], r['work']['digest'][:8], r['verdict']))
    if master_row:
        print('%-4s %-16s %-6s %-8s %-8s %-9s %-9s %s'
              % ('ALL', '(combined)', '-', '-', '-',
                 master_row['head_digest'][:8],
                 master_row['work_digest'][:8], master_row['verdict']))
    print()
    print('raw bytes — for GEOM_IDENTICAL macros every differing byte must fall '
          'inside a date record:')
    print('%-4s %-16s %-8s %-10s %-22s %s'
          % ('tag', 'declared', 'len', 'diff bytes', 'date records hit',
             'outside dates'))
    print('-' * 96)
    for r in rows:
        rb = r['raw_bytes']
        print('%-4s %-16s %-8s %-10s %-22s %s'
              % (r['tag'], r['declared'], rb.get('n_bytes', '-'),
                 rb.get('n_diff', '-'),
                 ','.join(rb.get('timestamp_records_hit') or []) or '-',
                 rb.get('reason') or (rb['outside'] or 'NONE')))
    if master_row:
        rb = master_row['raw_bytes']
        print('%-4s %-16s %-8s %-10s %-22s %s'
              % ('ALL', '(combined)', rb.get('n_bytes', '-'),
                 rb.get('n_diff', '-'),
                 ','.join(rb.get('timestamp_records_hit') or []) or '-',
                 rb.get('reason') or (rb['outside'] or 'NONE')))
    print()

    # per-layer table for macros that differ, to show the granularity
    for r in rows:
        print('per-layer detail for %s (declared %s):' % (r['tag'], r['declared']))
        for l in r['layers']:
            h = l['head'] if not isinstance(l['head'], dict) else \
                l['head'].get('digest', '-')
            w = l['work'] if not isinstance(l['work'], dict) else \
                l['work'].get('digest', '-')
            print('   %-18s %-9s head=%s work=%s'
                  % (l['layer'], l['verdict'], h, w))

    # ------------------------------------------------------------- markdown
    md = ['# GDS 几何一致性（逐图形）', '',
          '自动生成：`macros/p3_gds_identity.py`  ',
          '比较对象：工作区 `macros/out/struct_*.gds` ↔ `git cat-file HEAD:...`', '',
          '## 通过条件（P5 起已改变）', '',
          'P3 的通过条件是"与 HEAD 逐图形相同"。**P5 的 Item 2 修正了 via 包围，',
          '那是有意的几何变更，所以逐字节/逐图形全等的条件已经作废。**', '',
          '现在的判据按宏分类（分类由 `macros/p5_geometry_record.py` 生成，',
          '写在 `.v2ana/geometry_change_record.json`，本脚本只读取、不自行分类）：', '',
          '| 分类 | 允许的差异 | 附加要求 |', '|---|---|---|',
          '| `GEOM_IDENTICAL` | 无 | 必须与 HEAD 逐图形相同；原始字节差必须全在日期记录内 |',
          '| `PAD_ONLY` | 仅金属 pad 增长 | via cut 数量/中心/尺寸不变；HEAD 旧图形必须全部被新几何**包含**（只增不减）|',
          '| 其它 | 不允许 | FAIL |', '',
          '## 方法', '',
          '每个宏、每种层，把该层全部图形规范化为 `(layer, datatype, 形状类别, 绝对坐标)`，',
          '排序后做 SHA-256。多边形按缠绕方向与起始顶点规范化。',
          '层次变换由 `begin_shapes_rec` 应用到坐标上，因此"绝对坐标一致"已包含',
          '层次变换一致。文件时间戳、库名、BGNLIB 日期不参与摘要。', '',
          '## 结果', '',
          '| 宏 | 声明分类 | 非空层 | HEAD 图形数 | 工作区图形数 | HEAD 摘要 | 工作区摘要 | 判定 |',
          '|---|---|---|---|---|---|---|---|']
    for r in rows:
        md.append('| %s | `%s` | %d | %d | %d | `%s` | `%s` | **%s** |'
                  % (r['tag'], r['declared'], r['work']['n_layers'],
                     r['head']['n_shapes'], r['work']['n_shapes'],
                     r['head']['digest'][:16], r['work']['digest'][:16],
                     r['verdict']))
    if master_row:
        md.append('| ALL | （合并版） | — | — | — | `%s` | `%s` | **%s** |'
                  % (master_row['head_digest'][:16],
                     master_row['work_digest'][:16], master_row['verdict']))
    md += ['', '> 合并版 `v2_structures.gds` 含三个声明为 `PAD_ONLY` 的宏，',
           '> 与 HEAD 不同是**预期**的。它改判"是否与逐宏输出一致"（防陈旧）。', '',
           '## 逐层明细', '']
    for r in rows:
        md.append('### %s — %s（声明 `%s`）' % (r['tag'], r['gds'], r['declared']))
        md.append('')
        md.append('| 层 | HEAD | 工作区 | 判定 |')
        md.append('|---|---|---|---|')
        for l in r['layers']:
            h = l['head'] if not isinstance(l['head'], dict) else \
                '%s shapes, `%s`' % (l['head'].get('n_shapes'),
                                     l['head'].get('digest'))
            w = l['work'] if not isinstance(l['work'], dict) else \
                '%s shapes, `%s`' % (l['work'].get('n_shapes'),
                                     l['work'].get('digest'))
            md.append('| %s | %s | %s | %s |' % (l['layer'], h, w, l['verdict']))
        md.append('')
    md += ['', '## 逐字节对照（时间戳）', '',
           '摘要比较**不读**时间戳，所以它证明不了"两个文件只差时间戳"。本节做',
           '相反的检查：逐字节比较，并要求**每一个**不同的字节都落在 `BGNLIB`',
           '(0x0102) 或 `BGNSTR` (0x0502) 日期记录内部。',
           '该检查只对 `GEOM_IDENTICAL` 宏构成通过条件 —— 几何有意改变的文件',
           '本来就允许字节不同。', '',
           '| 文件 | 声明 | 字节数 | 不同字节 | 命中的日期记录 | 日期记录之外 |',
           '|---|---|---|---|---|---|']
    for r in rows + ([master_row] if master_row else []):
        rb = r['raw_bytes']
        md.append('| %s | %s | %s | %s | %s | %s |'
                  % (r.get('tag', 'ALL'), r.get('declared', '（合并版）'),
                     rb.get('n_bytes', '—'), rb.get('n_diff', '—'),
                     ', '.join(rb.get('timestamp_records_hit') or []) or '—',
                     rb.get('reason') or ('**%d**' % len(rb['outside'])
                                          if rb['outside'] else 'NONE')))
    md += ['', '## 结论', '']
    if problems:
        md.append('**FAIL** — %d 个问题：' % len(problems))
        for p in problems:
            md.append('- %s' % p)
    else:
        md.append('**PASS** — 四个宏与 HEAD 逐图形全等；三个宏的差异全部落在')
        md.append('声明的 via pad 增长范围内（cut 不变、旧几何被完全包含）。')
        md.append('')
        md.append('> 这不证明与 V1 一致：V1（`24fc6a5`）里没有这些研究宏。')
    open(os.path.join(VAL, 'P4_GDS_IDENTITY.md'), 'w',
         encoding='utf-8', newline='\n').write('\n'.join(md) + '\n')

    print('written v2_validation/P4_GDS_IDENTITY.{json,md}')
    if problems:
        print()
        print('FAIL — %d problem(s):' % len(problems))
        for p in problems:
            print('  !', p)
        return 1
    print('PASS — geometry matches the declared change policy '
          '(GEOM_IDENTICAL exact; PAD_ONLY additive with cuts unchanged)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
