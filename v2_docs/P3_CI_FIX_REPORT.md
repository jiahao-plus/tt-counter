# P3 首次 CI 失败修复报告

日期：2026-10-28
分支：`exp/v2-2x2-research`
上次 CI Commit：`45e629e`
**本轮未 Commit、未 Push**

---

## 1. 错误根因

### 错误 1（阻塞 GDS 与 Docs）

```
research_macros.v doesn't exist in the repo
```

**根因**：`info.yaml` 的 `project.source_files` 列出的是**相对于 `src/` 的文件名**：

```yaml
source_files:
  - "project.v"
  - "pwm.v"
  - "LFSR_Design.v"
  - "research_macros.v"     # <-- 声明在 src/ 下
```

但实际文件在 **`v2_rtl/research_macros.v`**。

Tiny Tapeout 的构建在 "Fetch verilog and build config" 阶段只从 `src/` 收集源文件，
找不到就立即失败。**GDS 从未进入 P&R 阶段。**

### 错误 2（test 工作流）

```
test/results.xml 不存在
```

**根因**：`test/Makefile` 的 `PROJECT_SOURCES` 只有 3 个文件：

```makefile
PROJECT_SOURCES = project.v pwm.v LFSR_Design.v
```

而 `src/project.v` 里有 7 个研究宏实例化（`research_via1`、`research_via2` 等）。
cocotb 用 icarus 编译时找不到模块定义 → 编译失败 → **测试根本没跑起来** →
`results.xml` 从未生成。

**这两个错误是同一个根因的两个表现**：`research_macros.v` 放错位置，
导致 `info.yaml`、`test/Makefile`、本地脚本三处引用不一致。

---

## 2. 修改内容

### 2.1 文件移动（唯一权威位置）

```
R  v2_rtl/research_macros.v -> src/research_macros.v
```

**用 `git mv` 移动，不是复制**——不存在两份副本，无版本漂移风险。

### 2.2 `test/Makefile`

```diff
-PROJECT_SOURCES = project.v pwm.v LFSR_Design.v
+# Must mirror project.source_files in info.yaml. ...
+PROJECT_SOURCES = project.v pwm.v LFSR_Design.v research_macros.v
```

### 2.3 `v2_validation/synth_check.ys`

```diff
-read_verilog -sv src/project.v src/pwm.v src/LFSR_Design.v v2_rtl/research_macros.v
+read_verilog -sv src/project.v src/pwm.v src/LFSR_Design.v src/research_macros.v
```

### 2.4 `macros/p3_integration_matrix.py`

```diff
-veri = read_text(os.path.join(ROOT, 'v2_rtl', 'research_macros.v'))
+veri = read_text(os.path.join(ROOT, 'src', 'research_macros.v'))
```

**这一处如果不改，脚本会直接崩溃**（文件不存在）。

### 2.5 `v2_docs/P3_PROGRESS_P0_P3.md`

3 处路径引用从 `v2_rtl/` 改为 `src/`（历史文档同步）。

### 2.6 新增 `tools/check_source_files.py`

自动断言，防止再次出现路径错误（详见第 4 节）。

---

## 3. 完整 Diff

```diff
diff --git a/macros/p3_integration_matrix.py b/macros/p3_integration_matrix.py
-    veri = read_text(os.path.join(ROOT, 'v2_rtl', 'research_macros.v'))
+    veri = read_text(os.path.join(ROOT, 'src', 'research_macros.v'))

diff --git a/v2_rtl/research_macros.v b/src/research_macros.v
similarity index 100%
rename from v2_rtl/research_macros.v
rename to src/research_macros.v

diff --git a/test/Makefile b/test/Makefile
-PROJECT_SOURCES = project.v pwm.v LFSR_Design.v
+# Must mirror project.source_files in info.yaml. The V2 research macro models
+# (research_macros.v) live in src/ alongside the functional RTL, because the
+# Tiny Tapeout build only sees files listed under src/. A mismatch here was the
+# cause of the first CI failure: the test flow compiled project.v alone, hit
+# the research_* module instantiations, and cocotb never produced results.xml.
+PROJECT_SOURCES = project.v pwm.v LFSR_Design.v research_macros.v

diff --git a/v2_docs/P3_PROGRESS_P0_P3.md b/v2_docs/P3_PROGRESS_P0_P3.md
-v2_rtl/research_macros.v
+src/research_macros.v   (3 处)

diff --git a/v2_validation/synth_check.ys b/v2_validation/synth_check.ys
-read_verilog -sv src/project.v src/pwm.v src/LFSR_Design.v v2_rtl/research_macros.v
+# V2 synthesis check. Paths mirror project.source_files in info.yaml —
+# every file listed there must live in src/ and be listed here too.
+# (research_macros.v was in v2_rtl/ during the first CI attempt, which made the
+# official build fail with "research_macros.v doesn't exist in the repo".)
+read_verilog -sv src/project.v src/pwm.v src/LFSR_Design.v src/research_macros.v

新增：
  tools/check_source_files.py
  v2_docs/P3_OFFICIAL_CI_REPORT.md
```

**统计**：5 文件修改 + 1 文件重命名 + 2 文件新增。

---

## 4. 自动断言（防止复发）

`tools/check_source_files.py` 检查五项：

| # | 检查 | 失败示例 |
|---|---|---|
| 1 | `info.yaml` 可解析，`source_files` 非空 | — |
| 2 | 每个 `source_files` 条目在 `src/` 下真实存在 | `lists "X" but src/X does not exist` |
| 3 | `src/` 下每个 `*.v` 都被 `source_files` 覆盖 | `src/X.v exists but is not listed (will not be compiled)` |
| 4 | `test/Makefile` 的 `PROJECT_SOURCES` 与 `source_files` 一致 | `PROJECT_SOURCES [...] != source_files [...]` |
| 5 | 仓库内无同名 `.v` 的第二份副本 | `X exists in N places, version drift risk` |

### 负向测试（证明断言有判别力）

故意把 `research_macros.v` 改成 `nonexistent_macros.v`，断言立即报 3 个错误：

```
SOURCE FILE CHECK: FAIL (3)
  ! source_files lists "nonexistent_macros.v" but src/nonexistent_macros.v does not exist
  ! src/research_macros.v exists but is not listed in source_files (it will not be compiled)
  ! test/Makefile PROJECT_SOURCES [...] != info.yaml source_files [...]
```

恢复后重新 PASS。

---

## 5. 运行命令与结果

### 5.1 源文件一致性断言

```bash
$ python3 tools/check_source_files.py
info.yaml source_files (4):
src/ verilog files  (4): ['LFSR_Design.v', 'project.v', 'pwm.v', 'research_macros.v']

  project.v                OK
  pwm.v                    OK
  LFSR_Design.v            OK
  research_macros.v        OK

  test/Makefile PROJECT_SOURCES matches source_files: OK
  no duplicate copies of any source file: OK

SOURCE FILE CHECK: PASS — info.yaml / src/ / test-Makefile consistent
```

### 5.2 RTL 综合（新路径）

```bash
$ yosys -p "script v2_validation/synth_check.ys"
        1   research_cross
        1   research_dense
        1   research_fiducial
Used module:     \research_branch
Used module:     \research_near
Used module:     \research_via1
Used module:     \research_via2
```

**七宏全部保留。**

### 5.3 cocotb 测试（实跑，cocotb 2.1.0）

```bash
$ cd test && make
** TESTS=13 PASS=13 FAIL=0 SKIP=0 **
```

**13/13 PASS**，`results.xml` 成功生成（8130 B）。

```bash
$ python3 -m cocotb_tools.check_results results.xml
rc=0
```

**这直接证明了错误 2 已修复**——之前 `results.xml` 不生成，现在生成了。

### 5.4 七宏回归

| 检查 | 结果 |
|---|---|
| 几何 DRC | ✅ ALL STRUCTURES DRC: PASS |
| 拓扑 | ✅ TOPOLOGY VERIFY: PASS |
| 宏视图一致性 | ✅ written P3_MACRO_VIEW_CONSISTENCY |
| 电气连通性 | ✅ written P3_ELECTRICAL_CONNECTIVITY |
| 负向对照 | ✅ 3/3 违规被抓 |
| 四源一致性（含 5 µm） | ✅ CONSISTENCY: PASS |
| 集成矩阵 | ✅ LOCAL_INTEGRATED: 7/7 |
| RTL 冒烟测试 | ✅ SMOKE TEST: PASS |

### 5.5 info.yaml 结构检查

```
title          OK
author         OK
language       OK
clock_hz       OK
tiles          OK   -> 2x2 (valid)
top_module     OK   -> tt_um_jiahao_plus_counter (starts tt_um_)
source_files   OK   -> ['project.v', 'pwm.v', 'LFSR_Design.v', 'research_macros.v']
yaml_version   OK   -> 6
```

---

## 6. NOT_RUN 项（明确声明）

### 6.1 `tt_tool.py --create-user-config` / `--check-docs`

**状态：NOT_RUN**

原因：本机未安装 `tt-support-tools`。

```
$ which tt_tool.py          -> (无输出)
$ pip list | grep tt-support -> (无匹配)
```

Windows 侧 `py -3.13 -c "import tt_tool"` 也失败。

**替代验证**：用 PyYAML 解析 `info.yaml` 并检查官方 schema 的必需字段
（第 5.5 节）。这**不等价于**官方工具的完整校验，仅覆盖结构与取值合法性。

**不做的事**：不声称已运行官方工具。

---

## 7. 未修改的内容（按你的约束）

| 项 | 状态 |
|---|---|
| 七类研究结构的几何 | ✅ 未改 |
| 电气语义（blackbox/keep、pass-through） | ✅ 未改 |
| 宏放置坐标 | ✅ 未改 |
| 5 µm 间距规则 | ✅ 未改（断言仍通过） |
| V1 黄金版本 `24fc6a5` | ✅ 未改（零改动） |
| Pages 保护策略（viewer 分支条件） | ✅ 未改 |
| Windows/WSL hosts | ✅ **未改**（遵守学校网络策略） |
| 已吊销的 Token | ✅ 未使用 |

**没有修改任何 `.gds` / `.lef` / `config.json` / 放置数据。**

---

## 8. 一个意外处理

负向测试时我误用 WSL 的 `/tmp` 备份（与 Windows 的 `/tmp` 不同），
导致 `info.yaml` 一度被改坏。已用 `sed` 立即恢复并验证：

```
SOURCE FILE CHECK: PASS — info.yaml / src/ / test-Makefile consistent
```

同时恢复了被测试覆盖的 `test/tb.fst`（仓库跟踪的样例波形）
和三个负向对照 GDS（字节因时间戳变化，内容等价）。

---

## 9. 当前 Git 状态

```
 M macros/p3_integration_matrix.py
 M test/Makefile
 M v2_docs/P3_PROGRESS_P0_P3.md
 M v2_validation/synth_check.ys
R  v2_rtl/research_macros.v -> src/research_macros.v
?? tools/check_source_files.py
?? v2_docs/P3_OFFICIAL_CI_REPORT.md
```

**7 项变更，全部与本次路径修复相关，无附带改动。**

---

## 10. 预期效果

若本次修复正确，下次 CI 应该：

1. ✅ `gds` job 通过 "Fetch verilog and build config" 阶段
2. ✅ 真正进入 P&R（此前从未到达）
3. ✅ `test` job 生成 `results.xml` 并通过 `check_results`
4. ✅ `docs` job 能读取到所有源文件

**但不能预期**：
- ❌ P&R 一定成功（2×2 布通性仍未验证）
- ❌ MACROS 配置一定被接受（首次真实使用该语法）
- ❌ DRC/LVS 一定通过
- ❌ 七结构一定在最终 GDS 中正确保留

**这些只有真实 CI 结果能回答。**

---

## 11. 停止点

**已完成本地修复与全部可执行的验证。**

未做：
- ❌ 未 Commit
- ❌ 未 Push
- ❌ 未触发任何 CI
- ❌ 未修改芯片物理设计
- ❌ 未修改 V1

**等待你批准新的 Commit 与 Push。**

批准后我会：
1. Commit（记录 SHA）
2. Push
3. **首先确认 GDS 是否真正进入 P&R 阶段**（这是本次修复的核心目标）
4. 记录 Run ID 与各 job 真实状态
5. 若 CI 失败，分析原因并形成报告，**不擅自二次提交**
