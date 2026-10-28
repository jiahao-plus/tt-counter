#!/usr/bin/env python3
"""_prefetch_head_gds.py — 把 HEAD 版本的 GDS 落到 macros/_tmp_gds_identity/。

**为什么需要这一步**：`p3_gds_identity.py` 在 WSL 里跑，而这个 worktree 的
`.git` 是 Windows 侧创建的指针文件，WSL 的 git 读不可靠 —— 实测会返回 rc=0
但给出不可用的 blob。所以用一个在 Windows 侧运行的脚本把 HEAD 内容取出来，
WSL 侧只读这些副本。

用 `git cat-file blob` 而不是 `git show`：`git show` 会经过 attributes 和
pager，可能对二进制做文本处理。cat-file 原样返回对象。

用 `open(..., 'wb')` 写，不做任何换行转换。

用法（Windows 侧，仓库根）：
    python macros/_prefetch_head_gds.py
然后（WSL）：
    python3 macros/p3_gds_identity.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEST = os.path.join(HERE, '_tmp_gds_identity')

ITEMS = [('macros/out/struct_%s.gds' % t, 'head_%s.gds' % t)
         for t in ('A', 'B', 'C1', 'C3', 'C4', 'D', 'E')]
ITEMS.append(('macros/out/v2_structures.gds', 'head_master.gds'))

GDS_MAGIC = b'\x00\x06\x00\x02'


def main():
    os.makedirs(DEST, exist_ok=True)
    bad = 0
    for rel, name in ITEMS:
        r = subprocess.run(['git', 'cat-file', 'blob', 'HEAD:%s' % rel],
                           cwd=ROOT, capture_output=True)
        if r.returncode != 0:
            print('FAIL %-40s git rc=%d %s'
                  % (rel, r.returncode, r.stderr.decode('utf-8', 'replace')[:80]))
            bad += 1
            continue
        if r.stdout[:4] != GDS_MAGIC:
            print('FAIL %-40s not a GDS stream (first bytes %r)'
                  % (rel, r.stdout[:8]))
            bad += 1
            continue
        with open(os.path.join(DEST, name), 'wb') as f:
            f.write(r.stdout)
        print('ok   %-40s %6d bytes -> _tmp_gds_identity/%s'
              % (rel, len(r.stdout), name))
    print()
    if bad:
        print('FAIL — %d object(s) could not be extracted' % bad)
        return 1
    print('PASS — %d HEAD GDS objects extracted with GDS magic verified' % len(ITEMS))
    return 0


if __name__ == '__main__':
    sys.exit(main())
