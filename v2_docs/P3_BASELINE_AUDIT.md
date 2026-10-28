# P3_BASELINE_AUDIT — P3-0 基线复核

日期：2026-10-28
审计范围：`toposem_lesson8/tt-v2`（V2 工作区）
本轮**只读 + 本地修改**。未执行 Git Commit / Push。

---

## 1. 凭据安全状态

| 位置 | `ghp_` 命中 | 判定 |
|---|---|---|
| `toposem_lesson8/tt-counter/.git/config` | **0** | ✅ 干净 |
| `toposem_lesson8/tt-counter-exp/.git/config` | **0** | ✅ 干净 |
| `tt-v2/.git/config`（worktree，共享主仓） | **0** | ✅ 干净 |
| `C:\Users\Lenovo\DoubaoWork\chats\2026-10-13\new-chat\tt-counter\.git\config` | **1** | ⚠️ **明文仍在磁盘** |
| `C:\Users\Lenovo\DoubaoWork\chats\2026-10-13\new-chat\tt-counter-exp\.git\config` | **1** | ⚠️ **明文仍在磁盘** |

**用户已在 GitHub 侧吊销该 Token**（本会话开始时告知）。
因此该明文即使被读取也无法再用于认证——风险已大幅降低。

**但文件本身仍在磁盘上**。建议清理（改 remote 或删目录），这是一次性动作。
本会话**未**读取、输出或复制任何 Token 内容，仅统计命中数。

---

## 2. Git 基线

| 项 | 值 | 判定 |
|---|---|---|
| V1 工作区 | `tt-counter-exp`，分支 `exp/1x1-finalization`，HEAD `24fc6a5` | ✅ |
| V1 已跟踪文件改动 | **0** | ✅ V1 未受影响 |
| V1 黄金 commit 对象 | `git cat-file -t 24fc6a5` → `commit` | ✅ 存在 |
| V2 工作区 | `tt-v2`（独立 worktree），分支 `exp/v2-2x2-research` | ✅ |
| V2 HEAD | `6191dce1cd6fcc750e4f49362703bed4734e0a73` | ✅ 与交接报告一致 |
| V2 与 V1 隔离 | 两个独立 worktree，共享同一 `.git` 对象库 | ✅ |

**工作树列表**：

```
tt-counter-exp   24fc6a5 [exp/1x1-finalization]   <- V1，冻结
tt-v2            6191dce [exp/v2-2x2-research]    <- V2，开发中
```

---

## 3. 工具环境（实测）

| 工具 | 版本 | 位置 |
|---|---|---|
| yosys | 0.69+ (conda-forge) | WSL `/usr/bin/yosys` |
| iverilog | 11.0 stable | WSL `/usr/bin/iverilog` |
| KLayout | 0.26.2 | WSL `/usr/bin/klayout` |
| Python (WSL) | 3.x + pya 0.30.12 | WSL |
| Python (Win) | 3.13.16 + pya 0.30.12 | `py -3.13` |

**缺失**：magic、netgen、完整 SKY130 PDK（`~/.ciel` 不存在）、完整 OpenROAD P&R。

**可用 PDK 参考数据**（`/root/openroad-flow-scripts/flow/platforms/sky130hd/`）：
liberty、LEF、标准单元 GDS（4.18 MB）、KLayout DRC 规则（`sky130hd.lydrc`）。

---

## 4. V2 已有产物的真实性核查

### 4.1 七个宏文件

| Tag | GDS | LEF | Cell 名 | 电气 | PIN 数 | 尺寸 (µm) |
|---|---|---|---|---|---|---|
| A | ✅ | ✅ | `research_via1` | 是 | 2 | 8.14 × 4.94 |
| B | ✅ | ✅ | `research_via2` | 是 | 2 | 10.22 × 3.24 |
| C1 | ✅ | ✅ | `research_branch` | 是 | 2 | 10.14 × 3.20 |
| C3 | ✅ | ✅ | `research_near` | 是 | 8 | 10.14 × 8.24 |
| C4 | ✅ | ✅ | `research_cross` | **否** | 0 | 10.14 × 8.14 |
| D | ✅ | ✅ | `research_dense` | **否** | 0 | 35.00 × 5.79 |
| E | ✅ | ✅ | `research_fiducial` | **否** | 0 | 4.00 × 4.00 |

**合计占用 490.46 µm²**（单实例），2×2 core 约 71 774 µm² → 占 0.68%。

### 4.2 与交接报告的差异（重要）

| 交接报告说法 | 实际状态 | 处理 |
|---|---|---|
| "四个宏实例存活（A/B/C1/C3）" | **正确**（P2 结束时）| 本轮已扩到 7 个 |
| "C4/D/E 不实例化，由 floorplan 放置" | **这是错的** | 已改为实例化，见 §5 |

### 4.3 已撤销的错误做法（诚实记录）

P2 时我用 **pass-through 行为模型**（`assign b = a`）来防止空黑盒被综合器删除。
**这在电气语义上是错的**：C4 是"必须不连通"的负样本，D/E 是纯几何，
它们都不承载信号，给它们加 wire 行为模型等于伪造电气语义。

本轮改为官方推荐做法，并实测验证：

```verilog
(* blackbox *) (* keep *) module research_cross (); endmodule
```

**实验证据**：
- `(* blackbox *)` 单独 → yosys `opt` 后**被删除**（`Removed 1 unused modules`）
- `(* blackbox *) (* keep *)` → **保留**（`Removed 0 unused modules`，stat 中计数 1）

来源：Tiny Tapeout 官方 silicon-art 指南明确要求两个属性同时存在。

---

## 5. P3 本轮改动汇总

| 文件 | 改动 | 原因 |
|---|---|---|
| `v2_rtl/research_macros.v` | C4/D/E 改为 `(* blackbox *) (* keep *)` 空模块 | 撤销错误的 pass-through |
| `src/project.v` | 加 `u_rs_cross` / `u_rs_dense` / `u_rs_fiducial` 三个实例 | 七宏全部实例化 |
| `src/config.json` | 加 `MACROS`（7 宏）、`IGNORE_DISCONNECTED_MODULES`（6 项）、`ERROR_ON_DISCONNECTED_PINS: false` | 官方宏集成语法 |
| `macros/p3_placement_plan.py` | 新增 | 放置规划 |
| `macros/p3_patch_config.py` | 新增 | config.json 补丁 |
| `macros/p3_integration_matrix.py` | 新增 | 集成矩阵生成 |

**未改动**：`RUN_LVS`、`RUN_PDN`、`ERROR_ON_PDN_VIOLATIONS` 全部保持默认（开启）。
电气宏 A/B/C1/C3 必须通过真实 LVS/PDN 检查，不靠关闭检查蒙混。

---

## 6. 当前验证状态

| 检查 | 状态 | 证据 |
|---|---|---|
| 七宏本地几何 DRC | ✅ `LOCAL_GEOM_DRC` PASS ×7 | `macros/out/drc_all.json` |
| DRC 检查器负向对照 | ✅ 3/3 违规被抓 | `macros/_negative_control.py` |
| 七宏拓扑语义 | ✅ `LOCAL_TOPOLOGY_CHECK` PASS ×7 | `macros/out/topology_verify.json` |
| LEF/GDS/Verilog 名称一致 | ✅ 7/7 | `P3_SEVEN_MACRO_INTEGRATION.csv` |
| RTL 实例存在 | ✅ 7/7 | `src/project.v` |
| config.json 配置 | ✅ 7/7 | `src/config.json` |
| `RTL_SYNTHESIS` | ✅ PASS（七宏全部存活）| yosys 0.69 |
| `RTL_SIMULATION` | ✅ PASS（4/4 功能检查）| iverilog 11.0 |
| **`OFFICIAL_DRC`** | ❌ **NOT_RUN** | 无 2×2 P&R |
| **`OFFICIAL_LVS`** | ❌ **NOT_RUN** | 同上 |
| **`OFFICIAL_STA`** | ❌ **NOT_RUN** | 同上 |
| **`OFFICIAL_PRECHECK`** | ❌ **NOT_RUN** | 需 push |
| **`OFFICIAL_GDS_ACTION`** | ❌ **NOT_RUN** | 需 push |

---

## 7. 与交接报告的冲突

| 原报告说法 | 实际证据 | 处理 |
|---|---|---|
| "2×2 core 71 774 µm²" | 仍是**外推**（V1 边距套到 335×226） | 本轮沿用但明确标注 PLAN_ONLY |
| "七宏 DRC 通过" | 正确，但这是 `LOCAL_GEOM_DRC` 不是官方 | 已严格区分命名 |
| "四个宏实例存活" | P2 时正确；本轮已扩到 7 | 已更新 |

---

## 8. 本轮未做的事

- ❌ 未 Commit、未 Push、未触发 CI
- ❌ 未修改 V1 任何文件
- ❌ 未声称任何官方检查通过
- ❌ 未把 71 774 µm² 当作实测面积
- ❌ 未关闭任何 LVS/PDN/DRC 检查
