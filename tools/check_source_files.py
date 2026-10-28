#!/usr/bin/env python3
"""check_source_files.py — 断言 info.yaml 的 source_files 与真实文件一致。

背景：V2 首次官方 CI 在配置读取阶段就失败了：
    research_macros.v doesn't exist in the repo

原因是 info.yaml 的 project.source_files 列出的是 **src/ 下的相对文件名**，
而 research_macros.v 当时放在 v2_rtl/。官方构建只认 src/。

本脚本把这条规则变成可执行断言，今后任何路径错误都会在本地暴露，
而不是等到 CI 报错。

检查项：
  1. info.yaml 可解析，project.source_files 非空
  2. 每个 source_files 条目在 src/ 下真实存在
  3. src/ 下的每个 *.v 都被 source_files 覆盖（防止漏列导致综合缺模块）
  4. test/Makefile 的 PROJECT_SOURCES 与 source_files 一致
  5. 仓库内不存在同名的第二份 .v（防止版本漂移）

用法：python3 tools/check_source_files.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
INFO = os.path.join(ROOT, 'info.yaml')
SRC = os.path.join(ROOT, 'src')
MK = os.path.join(ROOT, 'test', 'Makefile')


def parse_source_files(info_path):
    """Parse the source_files list without requiring PyYAML."""
    text = open(info_path, encoding='utf-8').read()
    m = re.search(r'^\s*source_files:\s*$((?:\s*-\s*.+\s*$\n?)+)', text, re.M)
    if not m:
        return None
    return re.findall(r'-\s*"?([^"\n]+?)"?\s*$', m.group(1), re.M)


def parse_makefile_sources(mk_path):
    text = open(mk_path, encoding='utf-8').read()
    m = re.search(r'^PROJECT_SOURCES\s*=\s*(.+)$', text, re.M)
    if not m:
        return None
    return m.group(1).split()


def find_duplicate_v_files(root, names):
    """Return {name: [paths]} for every .v name that appears more than once
    outside .git and third_party (third_party libs are legitimately vendored)."""
    hits = {}
    skip = {'.git', 'third_party', 'v2_validation', 'test', 'tools',
            '_archive', '__pycache__'}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip
                       and not d.startswith('.')]
        for fn in filenames:
            if fn in names:
                hits.setdefault(fn, []).append(
                    os.path.relpath(os.path.join(dirpath, fn), root))
    return {k: v for k, v in hits.items() if len(v) > 1}


def main():
    problems = []

    if not os.path.exists(INFO):
        print('FAIL: info.yaml not found at', INFO); return 1
    files = parse_source_files(INFO)
    if files is None:
        print('FAIL: could not parse project.source_files in info.yaml'); return 1
    if not files:
        print('FAIL: source_files is empty'); return 1

    print('info.yaml source_files (%d):' % len(files))
    src_listing = sorted(f for f in os.listdir(SRC) if f.endswith('.v'))
    print('src/ verilog files  (%d): %s' % (len(src_listing), src_listing))
    print()

    # ---- 1. every listed file exists in src/
    for f in files:
        p = os.path.join(SRC, f)
        ok = os.path.isfile(p)
        print('  %-24s %s' % (f, 'OK' if ok else 'MISSING in src/'))
        if not ok:
            problems.append('source_files lists "%s" but src/%s does not exist'
                            % (f, f))

    # ---- 2. every src/*.v is listed
    for f in src_listing:
        if f not in files:
            problems.append('src/%s exists but is not listed in source_files '
                            '(it will not be compiled)' % f)

    # ---- 3. test Makefile agrees
    mk = parse_makefile_sources(MK) if os.path.exists(MK) else None
    if mk is None:
        problems.append('test/Makefile has no PROJECT_SOURCES')
    else:
        if sorted(mk) != sorted(files):
            problems.append('test/Makefile PROJECT_SOURCES %s != '
                            'info.yaml source_files %s' % (sorted(mk), sorted(files)))
        else:
            print('\n  test/Makefile PROJECT_SOURCES matches source_files: OK')

    # ---- 4. no duplicate copies elsewhere
    dup = find_duplicate_v_files(ROOT, set(files))
    for name, paths in sorted(dup.items()):
        problems.append('%s exists in %d places, version drift risk: %s'
                        % (name, len(paths), paths))
    if not dup:
        print('  no duplicate copies of any source file: OK')

    # ---- report
    print()
    if problems:
        print('SOURCE FILE CHECK: FAIL (%d)' % len(problems))
        for p in problems:
            print('  !', p)
        return 1
    print('SOURCE FILE CHECK: PASS — info.yaml / src/ / test-Makefile consistent')
    return 0


if __name__ == '__main__':
    sys.exit(main())
