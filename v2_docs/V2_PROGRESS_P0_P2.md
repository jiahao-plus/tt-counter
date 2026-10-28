# V2 进度汇报 — P0 + P1 + P2（部分）

日期：2026-10-28
分支：`exp/v2-2x2-research`（本地，**未 Commit、未 Push**）
工作区：`toposem_lesson8/tt-v2`（独立 git worktree）

---

## ① 本阶段确实完成的事项

### P0 — 只读审计与隔离

| # | 完成项 | 证据 |
|---|---|---|
| 1 | 凭据安全检查（不输出 Token） | `v2_docs/V2_BASELINE_AUDIT.md` §1 |
| 2 | 确认真实 Git 根、分支、HEAD | 同上 §2 |
| 3 | 工具环境实测（Windows / WSL 双路径） | 同上 §4 |
| 4 | 2×2 物理参数实测与外推 | 同上 §5 + `v2_spec/area_budget.json` |
| 5 | 建立隔离 worktree `tt-v2` + 分支 `exp/v2-2x2-research` | `git worktree list` |
| 6 | V1 校验和快照（用于变更检测） | 同上 §3 |

**P0 关键发现（3 条）**：

1. **两个旧副本的明文 PAT 仍存在**（`C:\Users\Lenovo\DoubaoWork\...`），项目内两个仓库已干净。
2. **本地有真实 PDK 参考数据**：`sky130hd` 的 liberty / LEF / 标准单元 GDS / **KLayout DRC 规则** 都在 `/root/openroad-flow-scripts/` 下——这改变了验证策略（原本以为完全不能验证）。
3. **`exp/2x2-feasibility` 不是"空分支"**，它与 `exp/1x1-finalization` 指向同一 commit，即"零改动分支"。修正了交接报告的表述。

### P1 — 需求与可行性

| # | 交付物 | 状态 |
|---|---|---|
| 1 | `v2_spec/sky130_rules_measured.md` | ✅ **全部数值从真实 PDK 提取** |
| 2 | `v2_spec/requirements_matrix.md` | ✅ A–G 七类结构逐项定义，MUST/BEST_EFFORT 分级 |
| 3 | `v2_spec/physical_plan.md` | ✅ 面积预算、放置约束、验证策略、风险 |
| 4 | `v2_spec/area_budget.json` | ✅ V1 实测 + 2×2 外推（标注为上界） |
| 5 | `macros/extract_rules.py` | ✅ 可复算规则提取器 |

**P1 关键数字（全部实测）**：

| 项 | 值 |
|---|---|
| M1/M2 min width & spacing | **0.140 µm** |
| M3 min width | **0.300 µm** |
| Via1 cut / M1 enclosure | **0.150 / 0.055 µm** |
| Via2 cut / M2,M3 enclosure | **0.200 / 0.040, 0.065 µm** |
| V1 core（实测） | 155.48 × 103.36 = **16 070 µm²**，39 行 × 338 列 = **13 182 sites** |
| 2×2 core（外推上界） | **71 774 µm²**，80 行 × 716 列 = **57 280 sites**（**4.47×**） |
| 研究结构总占用 | **≈ 1 882 µm²**（2.6% of core） |

### P2 — 最小原型（已完成宏 + RTL 集成，未做 P&R）

| # | 完成项 | 状态 |
|---|---|---|
| 1 | 7 个研究结构宏全部生成 GDS | ✅ `macros/out/struct_{A,B,C1,C3,C4,D,E}.gds` |
| 2 | 全部通过本地几何 DRC | ✅ **7/7 PASS，0 违规** |
| 3 | 全部通过拓扑语义验证 | ✅ **7/7 PASS** |
| 4 | DRC 检查器负向对照 | ✅ **3/3 故意违规被抓** |
| 5 | LEF 生成 + PIN-on-metal 校验 | ✅ 全部 PIN 落在真实金属上 |
| 6 | Verilog 行为模型 | ✅ 4 个电气结构有 pass-through 模型 |
| 7 | V2 `info.yaml`（2×2） | ✅ `tiles: "2x2"` |
| 8 | V2 顶层 RTL（功能不变 + 研究实例） | ✅ `src/project.v` |
| 9 | RTL 综合 | ✅ yosys 0.69，**4 个宏实例全部存活** |
| 10 | RTL 功能仿真 | ✅ iverilog，**4/4 检查 PASS** |

---

## ② 新增或修改的准确文件路径

### 新建（V2 工作区 `tt-v2/`）

```
v2_docs/V2_BASELINE_AUDIT.md           P0 审计报告
v2_docs/V2_PROGRESS_P0_P2.md           本文件
v2_spec/sky130_rules_measured.md       实测设计规则
v2_spec/requirements_matrix.md         A–G 需求矩阵
v2_spec/physical_plan.md               物理计划
v2_spec/area_budget.json               面积预算（实测+外推）
macros/extract_rules.py                规则提取器
macros/area_budget.py                  面积预算计算
macros/gen_v2_macros.py                7 个结构生成器
macros/gen_lef.py                      LEF 生成 + PIN 校验
macros/geom_drc.py                     几何 DRC（pya 原生 check）
macros/run_all_drc.py                  批量 DRC
macros/verify_topology.py              拓扑语义验证
macros/feasibility_via_macro.py        单结构可行性（P1 首测）
macros/_negative_control.py            DRC 负向对照
macros/out/struct_{A,B,C1,C3,C4,D,E}.gds
macros/out/struct_*.lef
macros/out/{v2_structures.gds, macro_index.json, topology_verify.json, drc_all.json}
v2_rtl/research_macros.v               宏的 Verilog 模型
v2_rtl/patch_project_v2.py             顶层打补丁脚本
v2_rtl/project_v1_reference.v          V1 原始 project.v 快照
v2_validation/tb_v2_smoke.v            冒烟测试
v2_validation/synth_check.ys           综合脚本
v2_validation/klayout_headless_crash.txt  KLayout 崩溃证据
```

### 修改（**仅 V2 worktree 内**）

```
info.yaml        tiles: 1x1 -> 2x2；title/description 改为研究芯片；source_files 加 research_macros.v
src/project.v    加 V2 banner + 4 个研究宏实例（功能逻辑未变）
```

### **未修改**

- ❌ V1 主工作区 `tt-counter-exp/` 的**任何文件**
- ❌ V1 的 `24fc6a5` commit
- ❌ 任何 CI 配置、workflow

---

## ③ 执行命令与日志

| # | 命令 | 结果 |
|---|---|---|
| 1 | `git worktree add -b exp/v2-2x2-research ../tt-v2 24fc6a5` | 成功，无 Commit |
| 2 | `python3 macros/extract_rules.py` | 提取 6 个宽度 + 9 条 DRC 规则 |
| 3 | `python3 macros/area_budget.py` | V1 core 16 070 µm²；2×2 外推 71 774 µm² |
| 4 | `python3 macros/gen_v2_macros.py` | 7 个结构，尺寸 4.0×4.0 到 35.0×5.79 µm |
| 5 | `python3 macros/run_all_drc.py` | **7/7 PASS** |
| 6 | `python3 macros/_negative_control.py` | **3/3 违规被抓** |
| 7 | `python3 macros/verify_topology.py` | **7/7 PASS** |
| 8 | `python3 macros/gen_lef.py` | 全部 PIN 在金属上 |
| 9 | `yosys ... hierarchy -top tt_um_jiahao_plus_counter; proc; opt; stat` | 4 个宏存活 |
| 10 | `iverilog ... && vvp` | **SMOKE TEST: PASS** |

> **无 Run ID**：本轮未触发任何 CI（需你批准 push）。

---

## ④ 各项 PASS / FAIL / NOT_RUN

| 检查项 | 结果 | 说明 |
|---|---|---|
| 结构几何 DRC（7 个） | ✅ **PASS ×7** | `geom_drc.py`，用实测规则 |
| DRC 检查器有效性 | ✅ **PASS** | 负向对照 3/3 被抓 |
| 结构拓扑正确性 | ✅ **PASS ×7** | 显式 via-cut 图，不做跨层 2D 并集 |
| LEF PIN 有效性 | ✅ **PASS** | 全部 PIN 落在真实金属 |
| RTL 综合 | ✅ **PASS** | yosys，0 错误 |
| 宏实例存活 | ✅ **PASS** | 4/4 |
| RTL 功能仿真 | ✅ **PASS** | 4/4 检查 |
| **官方 KLayout DRC（`.lydrc`）** | ❌ **NOT_RUN** | KLayout 0.26.2 Ruby 解释器 headless 必崩（见下） |
| **完整 P&R** | ❌ **NOT_RUN** | openroad 是 reduced build，无完整 PDK |
| **LVS** | ❌ **NOT_RUN** | 无 netgen |
| **STA** | ❌ **NOT_RUN** | 无完整时序环境 |
| **官方 Precheck / GDS Action** | ❌ **NOT_RUN** | 需 push，**等你批准** |
| 结构 F（信号多 cut） | ⏳ **UNKNOWN** | 取决于布线工具，需真实 routed DEF |
| 结构 G（可电测 Via 链） | ⏳ **未实现** | 引脚资源评估未完成 |

### 关于 KLayout DRC 无法运行的证据

```
ERROR: Signal number: 11
Address: 0x8
Program Version: KLayout 0.26.2 (2022-01-13 rLatestSourcePackage)
```

`-b` / `-r` / `-rm` 三种 headless 方式均在 Ruby 解释器初始化阶段崩溃。
`pya.DRC` 在 Python 模块中不存在（DRC-DSL 是应用层功能）。

**替代方案（已实施）**：`macros/geom_drc.py` 用 `pya.Region` 的原生
`width_check` / `space_check` / `enclosing_check` / `isolated_check`，
配合**从 deck 精确提取的规则值**，重新实现了关键 BEOL 规则。
结果标记为 `LOCAL_GEOM_DRC`，**明确不是 OFFICIAL_DRC**。

---

## ⑤ 已知限制及下步行动

### 限制

| # | 限制 | 影响 |
|---|---|---|
| L1 | 本地无完整 SKY130 PDK | 不能跑官方 DRC/LVS/STA |
| L2 | openroad 是 reduced build | 不能做完整 P&R |
| L3 | 2×2 的 `tt_block_2x2_pg.def` 本地不存在 | 面积预算只能外推，非实测 |
| L4 | 结构 F（信号多 cut）无法本地判定 | 需真实 routed DEF |
| L5 | 本轮未触发任何 CI | 无 Run ID，无官方证据 |

### 一个 P2 期间发现并已修复的实质问题

**空黑盒宏会被综合器删除。**

`(* blackbox *)` + 空模块的实例在 yosys `opt` 阶段被完全移除——
`hierarchy -keep_position` 和 `setattr keep` 都救不回来。

用两模块对照实验确认（`v2_validation/_t1.v`）：空黑盒被删，有
`assign b = a` 的保留。

**修复**：给每个电气结构加 pass-through 行为模型。这在电气上是**正确的**——
每个结构本身就是一条从一层经 via 到另一层的网，wire 是它的准确行为。
非电结构（C4/D/E）不实例化，由 floorplan 放置。

同时 `research_branch` / `research_near` 原来只有输入没有输出，也加了
真实输出端口（`tap` / `q0..q3`），否则同样会被删。

### 下步行动（P2 剩余 + P3）

| 优先级 | 事项 | 是否需你批准 |
|---|---|---|
| 1 | 写 `src/config.json` 的 MACROS 配置（LibreLane 语法） | 否 |
| 2 | 用 yosys 生成门级网表，跑门级仿真 | 否 |
| 3 | 做结构 F 的可行性分析（从 V1 routed DEF 统计 ROWCOL，外推） | 否 |
| 4 | 补齐 `v2_truth/` 的层几何与外推真值 | 否 |
| 5 | 写 `V2_ISSUES.md` 记录全部 FAIL/SKIPPED | 否 |
| **6** | **首次官方 CI 验证 2×2 能否布通** | **✅ 需你批准 push** |
| **7** | 提交投片 | **✅ 需你批准** |

---

## 需要你决定的事项

1. **是否批准 push `exp/v2-2x2-research` 到 GitHub 触发首次 CI？**
   这是唯一能回答"2×2 能否布通"和"MACROS 配置是否被接受"的方法。
   我会先给你完整的文件清单与将触发的 workflow。

2. **旧副本的明文 PAT 是否已吊销？**
   在清除前我不会做任何远程操作。
