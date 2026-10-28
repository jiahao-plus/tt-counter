# P3 阶段报告：七宏集成 + 本地验证（P3-0 — P3-3）

日期：2026-10-28
分支：`exp/v2-2x2-research`
HEAD（开始 P3 时）：`6191dce`
**本轮未 Commit、未 Push、未触发 CI**

---

## ① 完成了什么

### 1. 七类研究结构全部完成本地集成

P2 结束时只有 **4 个** RTL 实例（A/B/C1/C3）。本轮补齐到 **7 个**。

| Tag | 宏 | RTL 实例 | config 条目 | 综合存活 | 拓扑 | DRC |
|---|---|---|---|---|---|---|
| A | `research_via1` | `u_rs_via1` | ✅ | ✅ | ✅ | ✅ |
| B | `research_via2` | `u_rs_via2` | ✅ | ✅ | ✅ | ✅ |
| C1 | `research_branch` | `u_rs_branch` | ✅ | ✅ | ✅ | ✅ |
| C3 | `research_near` | `u_rs_near` | ✅ | ✅ | ✅ | ✅ |
| C4 | `research_cross` | `u_rs_cross` | ✅ | ✅ | ✅ | ✅ |
| D | `research_dense` | `u_rs_dense` | ✅ | ✅ | ✅ | ✅ |
| E | `research_fiducial` | `u_rs_fiducial` | ✅ | ✅ | ✅ | ✅ |

**7 / 7 `LOCAL_INTEGRATED`**（`v2_validation/P3_SEVEN_MACRO_INTEGRATION.csv`）

### 2. 撤销了 P2 的一个错误做法

P2 时我为了让空黑盒宏不被综合器删除，给 C4/D/E 加了 **pass-through 行为模型**
（`assign b = a`）。**这是错的**：

- C4 是"必须不连通"的负样本，给它一个 wire 行为等于伪造电气语义
- D/E 是纯几何，根本不承载信号

本轮改为官方推荐做法并实测验证：

```verilog
(* blackbox *) (* keep *) module research_cross (); endmodule
```

**实验对照**：

| 写法 | yosys `opt` 后 |
|---|---|
| `(* blackbox *)` 单独 | ❌ 被删除（`Removed 1 unused modules`）|
| `(* blackbox *) (* keep *)` | ✅ 保留（`Removed 0 unused modules`）|

来源：Tiny Tapeout 官方 silicon-art 指南明确要求两个属性同时存在。

### 3. `config.json` 宏配置完成

```json
"MACROS": { … 7 条 … },
"IGNORE_DISCONNECTED_MODULES": [
  "research_fiducial", "u_rs_fiducial",
  "research_cross", "u_rs_cross",
  "research_dense", "u_rs_dense"
],
"ERROR_ON_DISCONNECTED_PINS": false
```

**只对 C4/D/E 三个非电气宏做 disconnect 豁免。**
A/B/C1/C3 四个电气宏全部有真实 PIN，**不依赖**此开关。

**未添加**：`RUN_LVS`、`RUN_PDN`、`ERROR_ON_PDN_VIOLATIONS` —— 保持默认开启。

### 4. 放置方案避开 PDN strap

第一版放置（只看"在 core 内 + 不重叠"）导致 **`research_fiducial` 有 40% 宽度
落在假定 M4 strap 下**。M4 不透明，会遮挡 SEM 成像——直接损害 V2 的研究目的。

**第二版改用 strap 空档**：

| 宏 | x 范围 (µm) | 所在空档 | strap 穿越 |
|---|---|---|---|
| E `research_fiducial` | 24.0 – 28.0 | 23.20–57.20 | **0** |
| A `research_via1` | 31.0 – 39.1 | 23.20–57.20 | **0** |
| B `research_via2` | 64.0 – 74.2 | 62.00–96.00 | **0** |
| C1 `research_branch` | 64.0 – 74.1 | 62.00–96.00 | **0** |
| C3 `research_near` | 78.0 – 88.1 | 62.00–96.00 | **0** |
| C4 `research_cross` | 102.0 – 112.1 | 100.90–134.90 | **0** |
| D `research_dense` | 25.0 – 30.8 | 23.20–57.20（旋转）| **0** |

**`research_dense` 旋转 90°（orientation `E`）**：原尺寸 35.00 × 5.79 µm
比最宽空档（34.00 µm）还宽，旋转后变 5.79 × 35.00 µm 才能放进空档。

**基于外推 PDN 的预测遮挡率：从 40% 降到 0%。**

> ⚠️ **这不是经过真实 GDS 验证的结果。**
> 上表的 strap 位置是 V1 实测模式按 27.14 µm pitch 外推到 2×2 的**假设值**。
> 真实 2×2 PDN 布局仍是 **UNKNOWN**，必须由首次官方 CI 的 DEF 确认。
> 若真实 strap 位置与本假设不同，本节的 0% 预测不成立，放置方案需重做。

### 5. 全部本地验证通过

| 检查 | 结果 | 证据 |
|---|---|---|
| 七宏几何 DRC | ✅ `LOCAL_GEOM_DRC` PASS ×7 | `macros/out/drc_all.json` |
| DRC 负向对照 | ✅ 3/3 违规被抓 | `macros/_negative_control.py` |
| 七宏拓扑语义 | ✅ `LOCAL_TOPOLOGY_CHECK` PASS ×7 | `macros/out/topology_verify.json` |
| `RTL_SYNTHESIS` | ✅ 七宏全部存活 | yosys 0.69 |
| `RTL_SIMULATION` | ✅ 4/4 功能检查 | iverilog 11.0 |
| 放置约束 | ✅ 全在 core 内、零重叠、零 strap 穿越 | `P3_MACRO_BBOX.csv` |

---

## ② 修改了哪些文件

### 修改

| 文件 | 改动 |
|---|---|
| `src/research_macros.v` | C4/D/E 从 pass-through 改为 `(* blackbox *) (* keep *)` |
| `src/project.v` | 加 `u_rs_cross` / `u_rs_dense` / `u_rs_fiducial` 实例 |
| `src/config.json` | 加 `MACROS`（7）、`IGNORE_DISCONNECTED_MODULES`（6）、`ERROR_ON_DISCONNECTED_PINS` |

### 新增

| 文件 | 用途 |
|---|---|
| `macros/p3_placement_plan.py` | 放置规划（避开 strap）|
| `macros/p3_patch_config.py` | config.json 补丁 |
| `macros/p3_integration_matrix.py` | 集成矩阵生成 |
| `macros/p3_render_placement.py` | 放置图渲染 |
| `macros/p3_pdn_conflict_check.py` | PDN 遮挡分析 |
| `v2_docs/P3_BASELINE_AUDIT.md` | P3-0 基线审计 |
| `v2_spec/P3_MACRO_PLACEMENT_PLAN.md` | 放置方案文档 |
| `v2_validation/P3_SEVEN_MACRO_INTEGRATION.csv` | 七宏集成矩阵 |
| `v2_validation/P3_MACRO_BBOX.csv` | 宏 bbox 与放置 |
| `v2_validation/P3_MACRO_PLACEMENT.png` | 放置图 |
| `v2_validation/P3_PDN_CONFLICT.json` | PDN 遮挡分析结果 |
| `v2_validation/p3_placement.json` | 放置数据 |

---

## ③ 实际执行的命令

```bash
# P3-0 基线
git rev-parse --abbrev-ref HEAD; git rev-parse HEAD
git worktree list; git cat-file -t 24fc6a5...
grep -c "ghp_" <旧副本 .git/config>      # 只计数

# 黑盒属性实验
yosys -p "read_verilog v2_validation/_kk.v; hierarchy -top top; proc; opt; stat"

# 七宏综合
yosys -p "read_verilog -sv src/project.v src/pwm.v src/LFSR_Design.v \
          src/research_macros.v; hierarchy -top tt_um_jiahao_plus_counter; \
          proc; opt; stat"

# 仿真
iverilog -g2012 -o /tmp/t.vvp v2_validation/tb_v2_smoke.v \
    src/project.v src/pwm.v src/LFSR_Design.v src/research_macros.v
vvp /tmp/t.vvp

# 宏回归
python3 macros/run_all_drc.py
python3 macros/verify_topology.py
python3 macros/_negative_control.py

# P3-B 放置
python3 macros/p3_placement_plan.py
python3 macros/p3_pdn_conflict_check.py
python3 macros/p3_render_placement.py
python3 macros/p3_patch_config.py
python3 macros/p3_integration_matrix.py
```

**无 CI Run ID** —— 本轮未触发任何远程操作。

---

## ④ PASS / FAIL / NOT_RUN / BLOCKED

| 检查 | 状态 |
|---|---|
| 七宏本地几何 DRC | ✅ **PASS** |
| DRC 检查器有效性 | ✅ **PASS** |
| 七宏拓扑语义 | ✅ **PASS** |
| 七宏 LEF/GDS/Verilog 名称一致 | ✅ **PASS** |
| 七宏 RTL 实例 | ✅ **PASS** |
| 七宏 config 配置 | ✅ **PASS** |
| `RTL_SYNTHESIS` | ✅ **PASS** |
| `RTL_SIMULATION` | ✅ **PASS** |
| 放置约束（core 内/无重叠/无 strap 遮挡）| ✅ **PASS** |
| **`OFFICIAL_DRC`** | ❌ **NOT_RUN** |
| **`OFFICIAL_LVS`** | ❌ **NOT_RUN** |
| **`OFFICIAL_STA`** | ❌ **NOT_RUN** |
| **`OFFICIAL_PRECHECK`** | ❌ **NOT_RUN** |
| **`OFFICIAL_GDS_ACTION`** | ❌ **NOT_RUN** |
| **2×2 完整 P&R** | ❌ **BLOCKED**（需 push）|
| **最终 GDS 实例验证** | ❌ **PENDING**（无 GDS）|

---

## ⑤ 新发现的问题

### 问题 1：官方 silicon-art 指南的配置不能直接套用到电气宏

指南里给的 `RUN_LVS: false` / `RUN_PDN: false` / `ERROR_ON_PDN_VIOLATIONS: false`
是给**纯装饰性**宏用的。本设计的 A/B/C1/C3 是真实电气结构，
**绝不能**关这些检查。

本轮只加了必需的 `IGNORE_DISCONNECTED_MODULES` + `ERROR_ON_DISCONNECTED_PINS`，
并把豁免范围严格限制在 C4/D/E 三个非电气宏。

### 问题 2：35 µm 宽的宏塞不进 34 µm 的空档

`research_dense` 原尺寸 35.00 × 5.79 µm，而 V1 外推的最宽 strap 空档只有
34.00 µm。必须旋转 90°。

**风险**：旋转后的 LEF/GDS 对应关系需要在真实 P&R 后验证。
若 CI 的 placer 不支持 `orientation: E`，需要退回并重新规划。

### 问题 3：2×2 的 PDN 布局仍然完全未知

本轮的 strap 位置是 **V1 实测模式按 27.14 µm pitch 外推**，
真实 2×2 可能有完全不同的 PDN。

若真实 strap 位置与本轮假设不同，放置方案需要重做。

---

## ⑥ 下一阶段

**P3-4：请求用户批准 push，触发首次官方 2×2 CI。**

这一步能得到：
- 真实的 2×2 DEF（含真实 core 边界与 PDN）
- 官方 DRC / LVS / STA / Precheck 结果
- 最终 GDS（用于七结构独立验收）

在此之前无法推进 P3-5 之后的任何步骤。

---

## ⑦ 需要用户批准什么

**批准 push `exp/v2-2x2-research` 到 GitHub。**

具体操作：
- 分支：`exp/v2-2x2-research`
- 需要的本地 Commit：先 commit 本轮改动（P3 的宏集成 + 配置 + 放置）
- 会触发：`gds.yaml`（GDS Action + viewer job，会覆盖 GitHub Pages）、
  `test.yaml`、`docs.yaml`、`fpga.yaml`
- 影响：公开 CI 运行；Pages 从 V1 内容切到 V2

**回退**：删除远端分支即可；V1 的 `exp/ip-integration` 和 `main` 不受影响。

---

## ⑧ 回答任务要求的三个问题

### Q1：哪几类已经具备最终芯片集成条件？

**七类全部具备本地集成条件**（`LOCAL_INTEGRATED`）：

| 类别 | 依据 |
|---|---|
| A `research_via1` | 几何 DRC + 拓扑（M1-Via1-M2 单一分量）+ RTL 实例 + config |
| B `research_via2` | 同上，M2-Via2-M3 |
| C1 `research_branch` | 单 net 3 分支合并为 1 分量 + via1×3 |
| C3 `research_near` | 8 条线 8 个独立分量（负向关系保持）|
| C4 `research_cross` | 2 分量、via1=0（交叉不连接保持）|
| D `research_dense` | 线宽实测精确匹配 `[0.14,0.2,0.3,0.5,1.0]` |
| E `research_fiducial` | M1/M2 坐标逐一相同 |

**但"具备本地集成条件"≠"已在最终 GDS 中验证"。**
所有七类的 `final_gds_instance` 列都是 **PENDING**。

### Q2：哪几类仍然存在阻塞？

**零类结构本身阻塞**。所有七个宏都通过了本阶段能做的全部检查。

存在的是**三类跨结构的系统性阻塞**：

| 阻塞 | 影响 | 解除条件 |
|---|---|---|
| **无 2×2 P&R** | 七类都无法在最终 GDS 中验证 | 官方 CI |
| **无官方 DRC/LVS/STA/Precheck** | 无法签核 | 官方 CI |
| **2×2 PDN 未知** | 放置方案可能需重做 | 官方 CI 的 DEF |

**另有两个需要在 CI 后复核的风险点**：
1. `research_dense` 的 90° 旋转是否被 placer 正确支持
2. 假设的 strap 位置是否与真实 2×2 PDN 一致

### Q3：下一步需要用户批准什么操作？

**批准 push `exp/v2-2x2-research` 分支。**

必须先 commit 本轮改动（当前是未提交状态）。
批准后我会：
1. 展示完整 diff 与将触发的 workflow
2. 执行 commit + push
3. 监控 CI
4. 下载 DEF/GDS/DRC/LVS/STA/Precheck 产物
5. 从真实 DEF 重算 core 与 PDN，必要时调整放置并重新 push
6. 用最终 GDS 做七结构独立验收

**在此之前，V2 停在 `LOCAL_INTEGRATED`，不能声称 `PHYSICAL_VERIFIED` 或 `SUBMISSION_READY`。**
