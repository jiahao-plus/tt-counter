# V2_BASELINE_AUDIT — P0 只读审计

日期：2026-10-28
审计范围：`C:/Users/Lenovo/Desktop/课题/lesson`
本轮**只读**。未执行任何 Git Commit / Push / PR / 远程 CI 触发。

---

## 1. 安全前置：凭据检查

**结论：项目中两个仓库干净，但两个旧工作副本仍含明文 PAT。**

| 位置 | `ghp_` 命中 | remote 形式 | 判定 |
|---|---|---|---|
| `toposem_lesson8/tt-counter/.git/config` | **0** | `git@github.com:jiahao-plus/tt-counter.git` | ✅ 干净 |
| `toposem_lesson8/tt-counter-exp/.git/config` | **0** | `git@github.com:jiahao-plus/tt-counter.git` | ✅ 干净 |
| `C:\Users\Lenovo\DoubaoWork\chats\2026-10-13\new-chat\tt-counter\.git\config` | **1** | `https://ghp_…@github.com/...` | ❌ **仍存在** |
| `C:\Users\Lenovo\DoubaoWork\chats\2026-10-13\new-chat\tt-counter-exp\.git\config` | **1** | 同上 | ❌ **仍存在** |

检测方法：仅统计 `grep -c "ghp_"` 命中数，**未输出、未复制任何 Token 内容**。

**处置建议（需你执行）**：到 GitHub 吊销该 Token；把这两个 `.git/config` 的 remote 改为 SSH，或直接删除这两个旧副本目录。**在清除前，本会话不做任何远程操作。**

---

## 2. 真实 Git 根与分支

| 项 | 值 |
|---|---|
| 仓库根 | `C:/Users/Lenovo/Desktop/课题/lesson/toposem_lesson8/tt-counter-exp` |
| 当前分支（审计时） | `exp/1x1-finalization` |
| HEAD | `24fc6a5be9271d023a20961d40685719b7e9f755` |
| 已跟踪文件 | **39** |
| 远端分支 | `origin/main`、`origin/exp/ip-integration` |
| 本地分支 | `exp/1x1-finalization`、`exp/2x2-feasibility`、`exp/ip-integration`、`main` |
| worktree | 仅主工作区一个 |

### 2.1 修正交接报告的一处说法

| 原报告说法 | 实际证据 | 处理 |
|---|---|---|
| "`exp/2x2-feasibility` 是空分支" | `git branch -vv` 显示它与 `exp/1x1-finalization` **指向同一 commit `24fc6a5`**。严格说是"未做任何改动的分支"，不是"空分支"（它有完整 V1 内容） | 记录准确表述，不作为 V2 起点 |

**V2 不得基于 `exp/2x2-feasibility`** —— 它没有任何 2×2 内容。

---

## 3. V1 不可变基线（只读记录，非 V2 验收依据）

| 项 | 值 |
|---|---|
| 顶层模块 | `tt_um_jiahao_plus_counter` |
| 黄金 Commit | `24fc6a5be9271d023a20961d40685719b7e9f755` |
| GDS SHA256 | `0e79d56a7688e6224a976182d5ac4ea4eb01a8341f768b4df5f75c0d8716155f` |
| Die | 161.000 × 111.520 µm，DBU 1 nm |
| Tiles | `1x1` |

V1 文件校验和（仅供变更检测，V2 不得修改）：

```
086cefd25415bdabd81318e427a2e0376cb20ce16a010e266e260b485804616f  info.yaml
548ffd2e1fbc7b75da38aad482bd4623236b92184a595fd8ff5224fe38c02cc8  src/project.v
da881c196b5dd1e7d1a41bb2f70fb1d335a7199abc64b63cd64ce09bf0880ddc  src/config.json
dd7dcc051e7427f25458bf441064fdc1bc27fc96127860322d11731e176e1005  docs/info.md
```

> `info.yaml` 的工作区版本是 CRLF（2325 B），git blob 是 LF（2268 B）。
> 上述哈希是**工作区 CRLF 版本**。V2 新建的 `info.yaml` 必须用 LF。

---

## 4. 工具环境实测

### 4.1 Windows

| 工具 | 状态 |
|---|---|
| `py -3.13` | ✅ Python 3.13.16，**pya/klayout 0.30.12 可用**，实测能读 GDS 并复算 |
| `python` (3.11) | ⚠️ 有，但**无 pya** |
| `python3` | ❌ Microsoft Store 空壳，报 `Python was not found` |
| yosys | ❌ 不在 PATH |

### 4.2 WSL Ubuntu 22.04

| 工具 | 版本 / 路径 | 可用性 |
|---|---|---|
| yosys | 0.69+ | ✅ |
| klayout | 0.26.2 | ✅ |
| openroad | "headless (reduced) build" | ⚠️ **reduced**，非完整 P&R |
| iverilog | 11.0 | ✅ |
| magic | — | ❌ MISSING |
| netgen | — | ❌ MISSING |
| verilator | — | ❌ MISSING |

### 4.3 PDK 与参考数据

| 资源 | 位置 | 状态 |
|---|---|---|
| `~/.ciel` / `~/.volare` | — | ❌ 不存在 |
| SKY130HD liberty | `/root/openroad-flow-scripts/flow/platforms/sky130hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib` | ✅ **可用** |
| SKY130HD LEF | 同目录 `lef/`：`sky130_fd_sc_hd.tlef`、`sky130_fd_sc_hd_merged.lef` | ✅ 可用（13 个 LAYER） |
| 标准单元 GDS | 同目录 `gds/sky130_fd_sc_hd.gds`（4.18 MB） | ✅ **可用** |
| KLayout DRC 规则 | 同目录 `drc/sky130hd.lydrc` | ✅ **可用**（DSL 脚本） |
| 完整 flow 脚本 | `/root/openroad-flow-scripts/` | ✅ 存在（含 `flow/`、`platforms/`） |
| 2×2 FP_DEF 模板 | — | ❌ 未找到（只有 `tt_block_1x1_pg.def` 的引用，实际文件在 CI 端） |

### 4.4 由此确定的验证能力边界

| 验证项 | 本地能力 | 说明 |
|---|---|---|
| RTL 仿真 | ✅ iverilog | 可跑 |
| 综合 | ✅ yosys + 官方 liberty | 可测绘面积、门数 |
| 门级仿真 | ✅ 综合网表 + 标准单元模型 | 需 liberty 或行为模型 |
| **KLayout DRC** | ✅ `sky130hd.lydrc` + 标准单元 GDS | **可对自建宏跑真 DRC** |
| 几何真值提取 | ✅ pya（3.13 或 WSL） | 可做层/几何/连通分析 |
| **完整 P&R** | ❌ | openroad 是 reduced build，且无完整 PDK（缺 tech LEF 之外的 GDS/RC 等） |
| **LVS** | ❌ | 无 netgen |
| **STA** | ⚠️ | openroad reduced 可能不支持；需实测 |
| 官方 Precheck / GDS Action | ❌ | 需 push，须你批准 |

**结论：本地可做"RTL→综合→宏 DRC→几何真值"，不可做"完整 P&R→LVS→官方 CI"。**
后者必须由官方 CI 回答，而这需要 push（须批准）。

---

## 5. 2×2 物理参数（实测）

### 5.1 已确认

| 参数 | 值 | 来源 |
|---|---|---|
| 2×2 名义尺寸 | **335 × 226 µm** | 官方文档 / `sky26d_2x2_constraints.md` |
| 名义面积 | 75 710 µm² | 计算 |
| 接受的 tiles 值 | `1x1, 1x2, 2x2, 3x2, 4x2, 6x2, 8x2` | `info.yaml` 注释（官方模板） |

### 5.2 V1 实测得到的行/轨道参数（可外推到 2×2）

从 V1 routed DEF 实测：

| 参数 | V1 值 | 对 2×2 的意义 |
|---|---|---|
| 行起点 | x = 2.760 µm, y = 2.720 µm | PDN 边距 ≈ 2.7 µm |
| 行数 | 39 | — |
| 每行列数 | 338（STEP 460 nm） | 行宽 = 2.76 → 158.24 µm |
| 行高 | 2.720 µm | 标准单元高度 |
| li1 X 轨道 | 350 条，STEP 460 nm | — |
| met1 X 轨道 | 473 条，STEP 340 nm | — |
| met2 Y 轨道 | **242 条**，STEP 460 nm | 2×2 会更多 |
| met3 Y 轨道 | **164 条**，STEP 680 nm | — |
| met4 Y 轨道 | 121 条，STEP 920 nm | — |

**关键观察**：V1 的 39 行 × 338 列 = 13 182 个单元位，但只放了 3994 个实例（占 30%）。
**2×2 名义上有 ~4.2 倍面积**，即使保守按 3× 可用行数计算，也有充足空间放研究结构。

### 5.3 尚不确定（必须在 P1 解决）

| 项 | 状态 | 阻塞什么 |
|---|---|---|
| 2×2 的**合法 Core 区域**（die 减去 PDN/IO 边距） | **UNKNOWN** | 面积预算只能按名义值保守估算 |
| 2×2 的 `tt_block_2x2_pg.def` 模板 | **本地不存在** | 无法本地复现官方 PDN；只能由 CI 生成 |
| 2×2 的 PDN strap 位置/宽度 | UNKNOWN | 研究宏必须避让，需知道位置 |
| SkY130 met2/met3 min width/spacing 精确值 | 可从 liberty/LEF 读，需提取 | 密度对照结构的合法取值 |

**这四项是 P1 必须先回答的**，否则面积预算和研究宏布局都是猜的。

---

## 6. 发现的阻塞与风险

| # | 阻塞/风险 | 严重度 | 影响 |
|---|---|---|---|
| B1 | 旧副本明文 PAT 未清 | **P0 安全** | 远程操作前必须清除 |
| B2 | 无完整 SKY130 PDK，无 magic/netgen | P1 | 无法本地 LVS/完整 DRC |
| B3 | openroad 是 reduced build | P1 | 无法本地完整 P&R |
| B4 | 2×2 FP_DEF 模板与 Core 区域 UNKNOWN | P1 | 面积预算与宏布局缺依据 |
| B5 | 2×2 物理可行性从未验证 | **P1 关键** | 整个 V2 的前提 |
| B6 | `python3` 空壳、默认 python 无 pya | P2 | 脚本必须显式指定解释器 |
| B7 | WSL 中文路径 + OpenCV 非 ASCII 静默失败 | P2 | 所有脚本须用相对路径并做语义检查 |
| B8 | `official_ci/ground_truth/` 6 个 mask 名错位一层 | P2 | **不得复用**，V2 须自行提取 |
| B9 | DEF `+ USE CLOCK` 多行解析 bug | P2 | V2 的 DEF 解析器必须按完整记录 |

---

## 7. V1 已证伪、V2 不得继承的数字

| 数字 | 状态 | 正确值 |
|---|---|---|
| `976 via / 317 nets` | ❌ 已证伪 | 1143 via（1140 + 3 MR） |
| `104 个触发器` | ❌ 已证伪 | **51**（dfxtp_2 43 + dfrtp_2 8） |
| `SIGNAL 370 / CLOCK 1` | ❌ 已证伪 | **SIGNAL 361 / CLOCK 10 / POWER 2** |
| `58 个 GDS stage` | ❌ 已证伪 | **74** |
| `official_ci/ground_truth/mask_*.gds` | ❌ 层号全部错位 | 用 `ground_truth_corrected/` 或从 V2 自己的 GDS 提取 |
| L9 的 5 个样本 | ⚠️ 2 个是时钟树 | 不能当纯信号网样本 |

---

## 8. 本轮已完成的隔离动作

| 动作 | 结果 |
|---|---|
| 创建 worktree | `toposem_lesson8/tt-v2` |
| 创建本地分支 | `exp/v2-2x2-research`（基于 `24fc6a5`） |
| 创建目录 | `v2_spec/`、`macros/`、`v2_truth/`、`v2_validation/`、`v2_docs/` |
| 记录 V1 校验和 | 见 §3 |
| Git Commit | ❌ **未执行** |
| Git Push | ❌ **未执行** |
| 远程 CI 触发 | ❌ **未执行** |

**V1 完好**：主工作区 `tt-counter-exp` 仍在 `exp/1x1-finalization`，HEAD `24fc6a5`，未触碰。

---

## 9. 首轮任务（P1）

按依赖顺序：

1. **提取 SKY130 精确设计规则**（从 `sky130_fd_sc_hd.tlef` + `sky130hd.lydrc`）
   → 得到 M1/M2/M3 min width、min spacing、via enclosure 的**实测值**，作为密度对照结构的合法参数。
2. **确定 2×2 Core 区域与 PDN 布局**
   → 若本地无模板，从 V1 的 `tt_block_1x1_pg.def` PDN 规律外推，并**明确标注为外推而非实测**。
3. **写 `v2_spec/requirements_matrix.md`**：A–G 七类结构逐项列 目的/实现/层/电气性/DRC风险/真值可追溯性/验收方法。
4. **写 `v2_spec/physical_plan.md`**：基于实测规则的面积预算，MUST / BEST_EFFORT 分级。
5. **最小可行性试验**：只做一种结构（建议 A：M1–Via1–M2 信号连接宏），
   跑 yosys 综合 + KLayout DRC + 几何真值提取，验证工具链端到端可用。

**需要你批准才能做的**：
- 任何 Git Commit
- Push 到 GitHub（触发官方 CI）
- 任何远程操作

---

## 10. 审计命令记录

```bash
# 凭据（不输出内容）
grep -c "ghp_" <config>                       # → 0 / 1
# git 状态
git rev-parse --abbrev-ref HEAD; git rev-parse HEAD; git branch -vv
git worktree list; git branch -r; git ls-files | wc -l
# 工具
py -3.13 -c "import pya,klayout;print(klayout.__version__)"   # 0.30.12
wsl -d Ubuntu2204 -- bash -lc 'command -v yosys openroad klayout iverilog'
# PDK 数据
ls /root/openroad-flow-scripts/flow/platforms/sky130hd/{lib,lef,gds,drc}
# V1 几何
grep "DIEAREA\|^ROW \|^TRACKS" <routed.def>
```
