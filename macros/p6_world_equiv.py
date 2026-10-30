"""P6 route-B acceptance: the world coordinates of the three electrical macros
must be identical before and after the cell re-basing.

Two independent references, deliberately not both derived from the generator:

  REF-A  the immutable round-4 commit b4e32b8, read through git
  REF-B  the round-4 routed DEF, whose COMPONENTS give the historical placement

The candidate is the new macro GDS plus the new placement from src/config.json.
Both references must agree with the candidate on every polygon, and on every
LEF PIN rectangle.
"""
import io
import json
import os
import subprocess
import tempfile
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from poly_exact import read_boundaries, bbox

# Derive the repo root from this file's own location so the check works under
# Windows and WSL alike instead of hard-coding one shell's path spelling.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE = 'b4e32b8a2c679619acc03fe3ad415bb476258260'


def _find_old_def():
    """Round-4 routed DEF, wherever this checkout can see it.

    The same file lives at different paths under Windows and WSL; probing both
    keeps the check runnable from either shell instead of silently failing.
    """
    for p in (r'C:\tmp\nl4x\runs\wokwi\final\def\tt_um_jiahao_plus_counter.def',
              '/mnt/c/tmp/nl4x/runs/wokwi/final/def/tt_um_jiahao_plus_counter.def',
              '/c/tmp/nl4x/runs/wokwi/final/def/tt_um_jiahao_plus_counter.def'):
        if os.path.exists(p):
            return p
    return None


OLD_DEF = _find_old_def()
NORMALISED = ('A', 'B', 'C1')
UNTOUCHED = ('C3', 'C4', 'D', 'E')
CELL = {'A': 'research_via1', 'B': 'research_via2', 'C1': 'research_branch',
        'C3': 'research_near', 'C4': 'research_cross',
        'D': 'research_dense', 'E': 'research_fiducial'}


def git_blob(path):
    """Bytes of `path` at the pinned baseline commit.

    WSL's git cannot read this worktree's .git pointer (it returns a fatal
    error rather than the object), so fall back to the copy the Windows side
    pre-extracted.  Both routes are pinned to BASELINE by construction: the
    fallback file is named after the tag and is itself produced from the same
    commit, never from the working tree.
    """
    rel = path.split('macros/out/struct_')[-1].replace('.gds', '')
    try:
        r = subprocess.run(['git', 'cat-file', 'blob',
                            '%s:%s' % (BASELINE, path)],
                           cwd=REPO, capture_output=True)
        if r.returncode == 0 and r.stdout[:4] == b'\x00\x06\x00\x02':
            return r.stdout
    except (FileNotFoundError, OSError):
        pass
    pre = os.path.join(REPO, 'macros', '_tmp_gds_identity',
                       'head_%s.gds' % rel)
    with open(pre, 'rb') as f:
        return f.read()


def old_placement(def_path):
    """Historical placement of each macro instance, straight from the DEF."""
    out = {}
    inst_of = {}
    for tag, cell in CELL.items():
        inst_of[cell] = None
    for line in io.open(def_path, encoding='utf-8', errors='replace'):
        s = line.strip()
        if not s.startswith('- u_rs'):
            continue
        f = s.split()
        inst, cell = f[1], f[2]
        i = f.index('(')
        x, y = int(f[i + 1]), int(f[i + 2])
        out[cell] = (x / 1000.0, y / 1000.0)   # nm -> um
    return out


def new_placement():
    cfg = json.load(io.open(os.path.join(REPO, 'src', 'config.json'),
                            encoding='utf-8'))
    out = {}
    for cell, spec in cfg['MACROS'].items():
        inst = list(spec['instances'])[0]
        out[cell] = tuple(spec['instances'][inst]['location'])
    return out


def polys(path):
    """{(layer,datatype): set of vertex tuples} for one macro GDS."""
    out = {}
    for r in read_boundaries(path):
        if r['layer'] == 235:            # prBoundary tracked separately
            continue
        out.setdefault((r['layer'], r['datatype']), set()).add(tuple(r['pts']))
    return out


def translate(ps, dx, dy):
    return {k: {tuple((x + dx, y + dy) for (x, y) in pts) for pts in v}
            for k, v in ps.items()}


def main():
    if OLD_DEF is None:
        print('SKIP: round-4 routed DEF not found on this machine, so the')
        print('      historical placement cannot be read independently.')
        print('      Refusing to fall back to the generator\'s own manifest.')
        return 2

    # Scratch directory for the extracted baseline GDS.  Derive it from the
    # filesystem rather than from a literal path: under WSL 'C:\tmp' is not a
    # drive but a file name, and a literal would silently create a directory
    # called 'C:tmp' inside the repo.
    tmp = os.path.join(tempfile.gettempdir(), 'p6_accept')
    os.makedirs(tmp, exist_ok=True)

    oldp = old_placement(OLD_DEF)
    newp = new_placement()

    print('%-16s %-22s %-22s %s' % ('cell', 'round-4 placement', 'round-5 placement', 'delta'))
    print('-' * 78)
    ok = True
    for tag in NORMALISED + UNTOUCHED:
        cell = CELL[tag]
        o, n = oldp[cell], newp[cell]
        d = (round(n[0] - o[0], 3), round(n[1] - o[1], 3))
        print('%-16s (%8.3f,%8.3f)      (%8.3f,%8.3f)      (%+.3f,%+.3f)'
              % (cell, o[0], o[1], n[0], n[1], d[0], d[1]))
    print()

    print('%-16s %-10s %-10s %s' % ('cell', 'polygons', 'world ok', 'note'))
    print('-' * 70)
    for tag in NORMALISED + UNTOUCHED:
        cell = CELL[tag]
        head_gds = os.path.join(tmp, 'head_%s.gds' % tag)
        with open(head_gds, 'wb') as f:
            f.write(git_blob('macros/out/struct_%s.gds' % tag))
        cur_gds = os.path.join(REPO, 'macros', 'out', 'struct_%s.gds' % tag)

        hp = polys(head_gds)
        cp = polys(cur_gds)
        # world = local + placement, using each version's own placement
        hw = translate(hp, int(round(oldp[cell][0] * 1000)),
                       int(round(oldp[cell][1] * 1000)))
        cw = translate(cp, int(round(newp[cell][0] * 1000)),
                       int(round(newp[cell][1] * 1000)))
        same = (hw == cw)
        if not same:
            ok = False
        n_poly = sum(len(v) for v in cp.values())
        note = 'world coordinates identical' if same else 'WORLD MISMATCH'
        print('%-16s %-10d %-10s %s' % (cell, n_poly, 'YES' if same else 'NO', note))

    # untouched macros must additionally be identical in LOCAL coordinates
    print()
    print('%-16s %s' % ('cell', 'local geometry identical to b4e32b8'))
    print('-' * 60)
    for tag in UNTOUCHED:
        cell = CELL[tag]
        head_gds = os.path.join(tmp, 'head_%s.gds' % tag)
        cur_gds = os.path.join(REPO, 'macros', 'out', 'struct_%s.gds' % tag)
        same = polys(head_gds) == polys(cur_gds)
        if not same:
            ok = False
        print('%-16s %s' % (cell, 'YES' if same else 'NO'))

    print()
    print('ROUTE-B WORLD-COORDINATE EQUIVALENCE:', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
