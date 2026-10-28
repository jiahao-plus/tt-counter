# P3 三项决定执行报告（Final Pre-Commit）

日期：2026-10-28
分支：`exp/v2-2x2-research`
**未 Commit、未 Push**

---

## 决定 1：`research_dense` 恢复 `N` 朝向

### 执行

| 项 | 值 |
|---|---|
| orientation | `E` → **`N`** |
| LEF SIZE | 35.000 × 5.790（原始方向，未变） |
| GDS prBoundary | 35.000 × 5.790（与 LEF 一致） |
| 实例占用 | 35.000 × 5.790（与 LEF 一致）✅ |

**现在 LEF、GDS、实例占用三者完全一致，不存在旋转坐标变换问题。**

### 你指出的技术点

> "LEF SIZE 在旋转后需要进行坐标变换，并非旋转必然导致错误。"

你说得对。旋转本身不是错误——只要 placer 正确地对 LEF 做旋转变换。我上一轮的表述过于绝对。真正的问题是**我无法在本地验证该变换是否正确**，而 `N` 消除了这个不确定性。

### 遮挡的表述

`research_dense` 在 `N` 方向下，基于**外推 PDN** 估计会跨 1 条 strap。
**这不是实测值。** 真实 2×2 PDN 布局为 UNKNOWN。

首次 CI 后必须从真实 GDS/DEF 检查：
- `research_dense` 的实际位置
- 真实 PDN 遮挡范围
- 关键研究图形（0.14/0.20/0.30/0.50/1.00 µm 五档线宽）的可观测性

若关键结构受影响，重新提出放置或预旋转方案，由你批准。

---

## 决定 2：恢复 5.00 µm 最小间距

### 执行

| 项 | 值 |
|---|---|
| 最小间距要求 | **5.00 µm**（已写入断言） |
| 实测最小间距 | **5.10 µm**（B–C1） |
| 21 对全部达标 | ✅ |

### 全部 21 对间距（由近到远）

| 间距 (µm) | 宏对 |
|---|---|
| **5.10** | B–C1 |
| **5.50** | E–A |
| 8.19 | B–C3 |
| 9.69 | C1–C3 |
| 17.26 | C1–C4 |
| 22.36 | A–B |
| 24.98 | A–C1 |
| 25.98 | A–C3 |
| 29.50 | E–B |
| 34.07 | E–C1 |
| 34.76 | E–C3 |
| 37.00 | A–D |
| 37.14 | B–C4 |
| 37.86 | E–C4 |
| 39.29 | C3–C4 |
| 45.00 | E–D |
| 47.71 | B–D |
| 52.21 | C1–D |
| 68.00 | A–C4 |
| 69.29 | C3–D |
| 78.50 | C4–D |

### 5 µm 已写入自动断言的证据

`macros/p3_assert_consistency.py` 顶部：

```python
MIN_GAP_UM = 5.00  # hard requirement restored by the user; asserted here so it
                   # cannot be silently relaxed again
```

`check_placement_constraints()` 会：
- 检查 C1（全在 core 内）
- 检查 C2（无重叠）
- 检查 **C3（间距 ≥ 5.00 µm）**
- 检查 C4（全部 N 朝向）
- 交叉检查 `p3_placement.json` 自己声明的 `min_gap_required_um` 是否为 5.00

**任何未来把间距降到 5 µm 以下的改动都会被断言拦下。**

### 新坐标

| Tag | 位置 (µm) | 朝向 |
|---|---|---|
| E | (24.00, 208.00) | N |
| A | (33.50, 208.00) | N |
| B | (64.00, 208.00) | N |
| C1 | (79.32, 208.00) | N |
| C3 | (64.00, 191.57) | N |
| C4 | (102.00, 188.00) | N |
| D | (23.50, 150.00) | N |

### 关于 Halo / Pin Access / 布线通道 / ROI

| 项 | 状态 |
|---|---|
| Halo | 5.10 µm 最小间距，在 SKY130 下足够（M1 min spacing 0.14） |
| Pin Access | 电气宏 PIN 全在宏 bbox 内部边缘；5 µm 缝隙可容纳路由进入 |
| 布线通道 | 5.10 µm 可容纳约 10 条 M1 线（0.14 宽 + 0.14 间距） |
| ROI 完整性 | 七宏集中在 y 150–215 的"研究带"，便于 SEM 定位成一整片 |

**全部标注为规划阶段检查**——真实 Core/PDN 未知。

---

## 决定 3：GitHub Pages 保护（R1 + R2）

### R1：备份已完成

备份位置：`v2_validation/v1_pages_backup/`（已加入 `.gitignore`，不进 git）

| 文件 | 大小 | SHA256 |
|---|---|---|
| `tinytapeout.gds` | 1 180 168 B | `0e79d56a7688e6224a976182d5ac4ea4eb01a8341f768b4df5f75c0d8716155f` |
| `tinytapeout.oas` | 79 281 B | `771562741f30890588ead7f787e0aadb5e535b6f48421bcb90ae89e24a70b2d7` |
| `gds_render.png` | 217 371 B | `171fc059e4d6f2ab73a2386f950f7538b96fef713857ec28faa91ec6f1a810f3` |

原始 URL：`https://jiahao-plus.github.io/tt-counter/<file>`
部署时间（Last-Modified）：`Wed, 21 Oct 2026 01:49:39 GMT`

### 关于部署分支：你提醒得对，不是 main

**证据链**：

1. V1 的 CI run 记录在 `official_ci/tt_submission/tt_submission/commit_id.json`：
   `commit 24fc6a5`，run `39529088709`
2. `24fc6a5` 在远端只存在于 **`origin/exp/ip-integration`**
3. 本地的 `exp/1x1-finalization` 和 `exp/2x2-feasibility` 都指向同一 commit，
   但**没有 push 到 origin**
4. Pages 的 GDS 哈希 = V1 黄金 GDS 哈希

**结论：V1 Pages 是从 `exp/ip-integration` 部署的，不是 `main`。**

（`main` 仍停在 `9ecb930`，是更早的裸计数器版本，**不能**作为 Pages 来源。）

### R2：workflow 修改

`.github/workflows/gds.yaml` 的 `viewer` job 增加条件：

```yaml
  viewer:
    needs: gds
    if: >-
      github.ref == 'refs/heads/exp/ip-integration' ||
      github.ref == 'refs/heads/main'
    runs-on: ubuntu-24.04
    permissions:
      pages: write
      id-token: write
    steps:
      - uses: TinyTapeout/tt-gds-action/viewer@ttsky26d
```

**只限制 `viewer` job（即 Pages 部署）。**
`gds`、`precheck`、`gl_test` 三个 job **完全不受影响**——V2 的 GDS 构建、
Precheck、门级仿真照常运行。

### 各场景行为验证

| 场景 | viewer 是否部署 |
|---|---|
| push 到 `exp/v2-2x2-research` | ❌ **跳过** |
| push 到 `exp/ip-integration` | ✅ 部署 |
| push 到 `main` | ✅ 部署 |
| `workflow_dispatch` 在 V2 分支 | ❌ 跳过 |

### YAML 有效性验证

```
.github/workflows/gds.yaml               OK  jobs=['gds', 'precheck', 'gl_test', 'viewer']
.github/workflows/test.yaml              OK  jobs=['test']
.github/workflows/docs.yaml              OK  jobs=['docs']
.github/workflows/fpga.yaml              OK  jobs=['fpga']
```

`docs.yaml` 和 `test.yaml` **不部署 Pages**（已 grep 确认无 `pages:` / `deploy`）。

### 可执行的 Pages 恢复方案

如果 Pages 意外被覆盖，按以下顺序恢复：

| 步骤 | 操作 | 效果 |
|---|---|---|
| 1 | 确认备份完好：`sha256sum v2_validation/v1_pages_backup/*` | 验证三个文件哈希 |
| 2 | 在 `exp/ip-integration` 分支上触发 `workflow_dispatch` | 重跑 V1 的 CI，重新部署 Pages |
| 3 | 若步骤 2 不可行：手动创建 `gh-pages` 分支并上传备份文件，在仓库 Settings → Pages 指向该分支 | 恢复旧预览 |

**注意**：删除 V2 远端分支**不会**回滚 Pages。这一点你指出的完全正确。
真正的回滚必须重新部署。

---

## 额外要求逐项回应

### 1. 七宏 prBoundary 与 LEF SIZE 匹配 + 自动验证证据

**发现并修复**：七个宏原本**全部没有 prBoundary**。官方指南明确说这是必需的
（"required for macro placement"），SKY130 用 **235/4**。

已修复，并有专门的验证脚本 `macros/p3_verify_macro_views.py`：

| Tag | prB 数 | prBoundary (µm) | GDS metal bbox (µm) | LEF SIZE (µm) | prB=metal | LEF=prB | ORIGIN ok |
|---|---|---|---|---|---|---|---|
| A | 1 | 8.140 × 4.940 | 8.140 × 4.940 | 8.140 × 4.940 | ✓ | ✓ | ✓ |
| B | 1 | 10.220 × 3.235 | 10.220 × 3.235 | 10.220 × 3.235 | ✓ | ✓ | ✓ |
| C1 | 1 | 10.140 × 3.200 | 10.140 × 3.200 | 10.140 × 3.200 | ✓ | ✓ | ✓ |
| C3 | 1 | 10.140 × 8.240 | 10.140 × 8.240 | 10.140 × 8.240 | ✓ | ✓ | ✓ |
| C4 | 1 | 10.140 × 8.140 | 10.140 × 8.140 | 10.140 × 8.140 | ✓ | ✓ | ✓ |
| D | 1 | 35.000 × 5.790 | 35.000 × 5.790 | 35.000 × 5.790 | ✓ | ✓ | ✓ |
| E | 1 | 4.000 × 4.000 | 4.000 × 4.000 | 4.000 × 4.000 | ✓ | ✓ | ✓ |

证据文件：`v2_validation/P3_MACRO_VIEW_CONSISTENCY.json` / `.md`

### 2. `research_via2` 尺寸口径差异

**查明原因**：

| 来源 | 值 | 说明 |
|---|---|---|
| GDS bbox | **3235 dbu = 3.235 µm** | 权威 |
| LEF SIZE | **3.235** | 与 GDS 一致 |
| manifest `size_um` | **3.235** | 与 GDS 一致 |
| 我早期文档 | 3.24 | ❌ 2 位小数四舍五入错误 |
| 某次表格 | 3.23 | ❌ 2 位小数截断 |

**真实值 3.235 µm。** 3.24 和 3.23 都是不同精度的舍入产物，不是真实差异。

已在验证脚本中用 `.3f` 精度统一输出，三源一致。

### 3. C4/D/E 无虚假电气连接

| Tag | Verilog 定义 | 端口 | wire 行为 | 组件数 | via 数 |
|---|---|---|---|---|---|
| C4 | `(* blackbox *) (* keep *) module research_cross ();` | 0 | 0 | 2 | **0** |
| D | 同上 `research_dense` | 0 | 0 | 13 | **0** |
| E | 同上 `research_fiducial` | 0 | 0 | 4 | **0** |

- 零端口、零 wire 行为
- 零 via cut（C4 的关键特征：M1/M2 投影交叉但无 via）
- LEF 里零 PIN

**P2 的 pass-through 模型已彻底移除，无残留。**

### 4. 电气宏 PIN/Net 检查 + 不用全局开关掩盖

#### 新增检查脚本
`macros/p3_check_electrical_connectivity.py`

| Tag | 电气 | PIN 数 | PIN 全在金属 | 连通分量 | 期望 | 结果 |
|---|---|---|---|---|---|---|
| A | ✓ | 2 | ✓ | 2 | 2 | ✓ |
| B | ✓ | 2 | ✓ | 1 | 1 | ✓ |
| C1 | ✓ | 2 | ✓ | 1 | 1 | ✓ |
| C3 | ✓ | 8 | ✓ | 8 | 8 | ✓ |
| C4 | ✗ | 0 | — | 2 | — | ✓ |
| D | ✗ | 0 | — | 13 | — | ✓ |
| E | ✗ | 0 | — | 4 | — | ✓ |

**RTL 端口绑定**：四个电气宏实例的所有端口都接到具名 wire，无悬空。✓

#### 组件数的期望值来源（不是猜的）

| Tag | 期望 | 理由 |
|---|---|---|
| A | **2** | `build_A()` 明确画了 netA（M1-Via1-M2）+ netC（独立邻居线）|
| B | 1 | 单一 M2-Via2-M3 网络 |
| C1 | 1 | 单 net 三分支（同一节点）|
| C3 | **8** | 4 对 × 2 条独立线 |

> 第一版我把 A 写成 1、C3 写成 4，检查报 FAIL。查 `build_A()` 源码后确认
> 是我的期望值错了，不是设计缺陷。已修正。

#### 全局开关已移除

**`ERROR_ON_DISCONNECTED_PINS` 已从 config.json 删除**。

原因：它是**全局**开关，会同时屏蔽 A/B/C1/C3 的引脚断开错误，
正是你要求防范的情况。

改用 `IGNORE_DISCONNECTED_MODULES` 精确豁免 C4/D/E：
```json
"IGNORE_DISCONNECTED_MODULES": [
  "research_fiducial", "u_rs_fiducial",
  "research_cross", "u_rs_cross",
  "research_dense", "u_rs_dense"
]
```

**风控**：若首次 CI 因 C4/D/E 无 pin 而报错，说明 `IGNORE_DISCONNECTED_MODULES`
不足以覆盖这种情况——那是一个需要重新评估的信号，**不应**用全局开关糊过去。

### 5. 完整回归（全部重跑）

| # | 检查 | 结果 |
|---|---|---|
| 1 | 七宏几何 DRC | ✅ `LOCAL_GEOM_DRC` PASS ×7 |
| 2 | 七宏拓扑 | ✅ `LOCAL_TOPOLOGY_CHECK` PASS ×7 |
| 3 | DRC 负向对照 | ✅ 3/3 违规被抓 |
| 4 | `RTL_SYNTHESIS` | ✅ 七宏全部存活 |
| 5 | `RTL_SIMULATION` | ✅ 4/4 功能检查 |
| 6 | 四源放置一致性 | ✅ PASS（含 5 µm 断言）|
| 附加 | 宏视图一致性 | ✅ ALL CONSISTENT |
| 附加 | 电气连通性 | ✅ PASS |

### 6. V1 Git 状态

```
V1 branch: exp/1x1-finalization
V1 HEAD:   24fc6a5be9271d023a20961d40685719b7e9f755
V1 tracked changes: 0
```

✅ **黄金 Commit 未改变，V1 零改动。**

### 7. 七结构全部保留

| Tag | 宏 | 状态 |
|---|---|---|
| A | `research_via1` | ✅ 保留 |
| B | `research_via2` | ✅ 保留 |
| C1 | `research_branch` | ✅ 保留 |
| C3 | `research_near` | ✅ 保留 |
| C4 | `research_cross` | ✅ 保留 |
| D | `research_dense` | ✅ 保留 |
| E | `research_fiducial` | ✅ 保留 |

**无删减。**

---

## 期间发现并修复的另一个问题

### `src/config.json` 的注释被破坏

第一版 `p3_patch_config.py` 用 `json.load` + `json.dump` 往返，把 TT 的
27 个 `"//"` 注释键**合并成一条**（Python dict 不允许重复键）。

**已撤销并重写**：改用文本注入，在最后一个 `}` 前插入新键值对，
其余内容逐字节保留。

**验证**：diff 现在是 `+125 −1`（纯增量），27 个注释键全部保留。

---

## 最终 Git Diff 摘要

### 修改（20 个）

```
M  .github/workflows/gds.yaml              viewer job 加分支条件
M  macros/gen_lef.py                       C1 TAP pin 坐标修正
M  macros/gen_v2_macros.py                 加 prBoundary
M  macros/out/macro_index.json             重新生成
M  macros/out/neg_{3 个}.gds               负向对照重新生成
M  macros/out/struct_{7 个}.gds            含 prBoundary
M  macros/out/struct_C1.lef                TAP pin 修正
M  macros/out/v2_structures.gds
M  macros/out/v2_structures_manifest.json
M  src/config.json                         MACROS + IGNORE（注释保留）
M  src/project.v                           7 个宏实例
M  v2_rtl/research_macros.v                C4/D/E blackbox+keep
```

### 新增（23 个）

```
?? macros/p3_assert_consistency.py         四源一致性 + 5 µm 断言
?? macros/p3_check_electrical_connectivity.py  PIN/Net 静态检查
?? macros/p3_integration_matrix.py         集成矩阵
?? macros/p3_patch_config.py                config 文本注入
?? macros/p3_pdn_conflict_check.py         PDN 遮挡分析
?? macros/p3_placement_plan.py             放置规划（5 µm + 全 N）
?? macros/p3_render_placement.py           放置图
?? macros/p3_sync_docs.py                  MD 同步
?? macros/p3_verify_macro_views.py         prBoundary/LEF/GDS 一致性
?? v2_docs/P3_BASELINE_AUDIT.md
?? v2_docs/P3_PRECOMMIT_REVIEW.md
?? v2_docs/P3_PROGRESS_P0_P3.md
?? v2_docs/P3_DECISIONS_EXECUTION.md        本文件
?? v2_spec/P3_MACRO_PLACEMENT_PLAN.md
?? v2_validation/P3_ELECTRICAL_CONNECTIVITY.{json,md}
?? v2_validation/P3_MACRO_BBOX.csv
?? v2_validation/P3_MACRO_PLACEMENT.png
?? v2_validation/P3_MACRO_VIEW_CONSISTENCY.{json,md}
?? v2_validation/P3_PDN_CONFLICT.json
?? v2_validation/P3_SEVEN_MACRO_INTEGRATION.csv
?? v2_validation/p3_placement.json
```

**未纳入 git**：`v2_validation/v1_pages_backup/`（1.4 MB 二进制，已 gitignore）

---

## GitHub Actions 触发范围

push `exp/v2-2x2-research` 后：

| Workflow | 会运行 | 说明 |
|---|---|---|
| `gds.yaml` → `gds` | ✅ | 真实 2×2 P&R，产出 GDS/DEF |
| `gds.yaml` → `precheck` | ✅ | 官方 Precheck |
| `gds.yaml` → `gl_test` | ✅ | 门级仿真 |
| `gds.yaml` → `viewer` | ❌ **跳过** | 分支条件拦截，不覆盖 Pages |
| `test.yaml` | ✅ | cocotb 测试 |
| `docs.yaml` | ✅ | 文档构建 |
| `fpga.yaml` | ❌ | `branches: none` |

---

## Pages 保护总结

| 项 | 状态 |
|---|---|
| V1 产物备份 | ✅ 三个文件 + SHA256 |
| 部署分支已核实 | ✅ `exp/ip-integration`（**不是 main**）|
| `viewer` job 加条件 | ✅ 只允许 `exp/ip-integration` / `main` |
| V2 分支不部署 | ✅ 已验证 |
| GDS 构建不受影响 | ✅ `gds`/`precheck`/`gl_test` 照常 |
| YAML 有效性 | ✅ 四个 workflow 全部解析通过 |
| 恢复方案 | ✅ 三步（验证备份 → 重跑 V1 CI → 手动 gh-pages）|

---

## 停止点

**本轮已完成你批准的全部三项决定及附加要求。**

未做：
- ❌ 未 Commit
- ❌ 未 Push
- ❌ 未触发任何 CI
- ❌ 未修改 V1

**等待你对 Commit 与 Push 的明确批准。**
