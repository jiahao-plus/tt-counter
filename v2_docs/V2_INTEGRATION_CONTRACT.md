# V2 集成契约（Integration Contract）— v2 修订

日期：2026-10-28（v2 修订）
依据：`V2_ARCHITECTURE_DECISION.md` v2（方案 α）、`V2_OFFICIAL_RULES_EVIDENCE.md` v2
状态：**契约定义，尚未实施。**

> **v2 修订**：统一契约为用户要求的五视图链——
> **物理连通分量 → LEF PIN → Verilog 端口 → 综合网表 Net → 最终 GDS**。
> v1 的"PIN 同分量"判据已被推翻（那是多 Net 宏的正常状态）。

---

## 1. 五视图链（本轮的核心契约）

每个宏必须在五个视图上**语义一致**：

```
  ┌─────────────────────────────────────────────────────────┐
  │ ① 物理连通分量（GDS）                                    │
  │    - 由实测确定，不由声明决定                             │
  ├─────────────────────────────────────────────────────────┤
  │ ② LEF PIN / PORT                                        │
  │    - PIN 名 == Verilog 端口名（逐字符）                   │
  │    - 同一 PIN 的所有 PORT 必须在①的同一分量上             │
  ├─────────────────────────────────────────────────────────┤
  │ ③ Verilog 端口                                           │
  │    - 名称、方向、数量与②一致                              │
  ├─────────────────────────────────────────────────────────┤
  │ ④ 综合网表 Net                                           │
  │    - 每个端口连接的 net                                   │
  │    - 同一 PIN 只能对应一个 net                            │
  ├─────────────────────────────────────────────────────────┤
  │ ⑤ 最终 GDS（CI 产物）                                    │
  │    - 宏实例存在、几何正确、未被 fill/PDN 破坏             │
  └─────────────────────────────────────────────────────────┘
```

### 1.1 一致性规则

| 规则 | 内容 | 违反的后果 |
|---|---|---|
| **V1** | ①同一分量上的所有 PORT → ②必须属于同一 PIN | 物理短路被拆成多个逻辑 net（当前 A/B/C1 的问题）|
| **V2** | ②的 PIN 名 == ③的端口名（**逐字符，含大小写**）| OpenROAD 找不到 pin（当前所有宏的问题）|
| **V3** | ③的每个端口 → ④只接一个 net | — |
| **V4** | ④的 net 数 == ③的端口数 | — |
| **V5** | ⑤中实例存在且几何与①一致 | 宏丢失或被改 |

---

## 2. 逐宏五视图表

### 2.1 A — `research_via1`（α′ 接口）

| 视图 | 内容 |
|---|---|
| **① 物理分量** | **C0**（含 M1 主线 + 垂直支 + via landing + M2 走线）<br>**C1**（M1 邻居线，无 PIN） |
| **② LEF PIN** | `net`（**单个 PIN**，**单个 PORT**）<br>该 PORT 内含 2 个 LAYER：met1 @ (0.000, 0.000)–(0.140, 0.140)、met2 @ (8.000, 2.000)–(8.140, 2.140) |
| **③ Verilog 端口** | `inout wire net`（1 个） |
| **④ 综合网表 Net** | `net` → `pwm_out`（**1 个 net**）|
| **⑤ 最终 GDS** | 待 CI |

**一致性**：一个 PORT 内的两个 LAYER 由 LEF 语义保证强连通 → 同一 PIN `net`
→ 同一 net `pwm_out`。✅

**为什么不是两个 PORT**：两个 PORT 只表达弱连通，router 不保证把它们当一个
节点，等于把"宏内部靠 via 相连"这个事实交给 router 去猜。α′ 改成一个 PORT
包住全部跨层 RECT，强连通由 LEF 直接声明。

**科研真值**：`SOURCE_GDS_TRUTH` + `ROUTED_DEF_NET_TRUTH`

### 2.2 B — `research_via2`

| 视图 | 内容 |
|---|---|
| ① 物理分量 | **C0**（M2 + Via2 + M3）|
| ② LEF PIN | `net`：**1 个 PORT**，内含 met2 与 met3 两个 LAYER |
| ③ Verilog | `inout wire net` |
| ④ Net | `pwm_out` |
| ⑤ 最终 GDS | 待 CI |

### 2.3 C1 — `research_branch`

| 视图 | 内容 |
|---|---|
| ① 物理分量 | **C0**（主干 + 3 个 via 分支全部汇于同一节点）|
| ② LEF PIN | `net`：**1 个 PORT**，内含 **4 个 RECT**（met1 主干端 ×1 + met2 三个分支端 ×3）|
| ③ Verilog | `inout wire net` |
| ④ Net | `pwm_out` |
| ⑤ 最终 GDS | 待 CI |

**C1 是 α′ 最自然的用例**：主干 + 3 分支 = 1 个节点、4 个接入点，全部写进
同一个 PORT，强连通显式声明。早期"4 个 PORT"的写法已废弃。

### 2.4 C3 — `research_near`（无端口）

| 视图 | 内容 |
|---|---|
| ① 物理分量 | **8 个独立分量**（C0–C7），实测 |
| ② LEF PIN | **0 个** |
| ③ Verilog | **无端口** |
| ④ Net | **无** |
| ⑤ 最终 GDS | 待 CI |

**为什么无端口**（科研论证，非合规性）：
- 研究问题是"SEM 能否区分靠得近与真的相连"
- 需要的是**几何真值**（8 条线的位置/宽度/间距）
- 若给端口，router 会在间距阶梯附近布线加 via，**污染测量**
- "8 条互不相连"由 GDS 几何直接表达，比 net 更准确

**注意**：C3 的 8 端口**技术上合法**（8 独立导体 = 8 net）。
选择无端口是**为了保住几何纯净度**，不是因为它非法。

**科研真值**：`SOURCE_GDS_TRUTH` + `FINAL_GDS_TRUTH`（**无 net 真值**）

### 2.5–2.7 C4 / D / E — 保持无端口

| 宏 | 分量 | PIN | 端口 | Net |
|---|---|---|---|---|
| C4 `research_cross` | 2（M1+横、M2+竖，交叉不连）| 0 | 无 | 无 |
| D `research_dense` | 13 | 0 | 无 | 无 |
| E `research_fiducial` | 4 | 0 | 无 | 无 |

---

## 3. 契约汇总表

| ID | ① 分量 | ② PIN | ③ 端口 | ④ Net | V1 | V2 | 模型 |
|---|---|---|---|---|---|---|---|
| A | 2（1 含 PIN）| `net`×1 | `net`×1 | `pwm_out`×1 | ✅ | ✅ | 电气抽头 |
| B | 1 | `net`×1 | `net`×1 | `pwm_out`×1 | ✅ | ✅ | 电气抽头 |
| C1 | 1 | `net`×1 | `net`×1 | `pwm_out`×1 | ✅ | ✅ | 电气抽头 |
| C3 | 8 | 0 | 无 | 无 | — | — | 几何宏 |
| C4 | 2 | 0 | 无 | 无 | — | — | 几何宏 |
| D | 13 | 0 | 无 | 无 | — | — | 几何宏 |
| E | 4 | 0 | 无 | 无 | — | — | 几何宏 |

**③ 端口**：α′ 接口下每个 PIN **只有 1 个** PORT，跨层的多个 `LAYER`/`RECT`
写在这一个 PORT 内部（强连通）。早期版本一个 PIN 下挂多个 PORT，那是弱连通，
router 不保证把它们当成同一个节点 —— 已改。A 的 2 个 PORT 版本与
`A`/`B`/`IN`/`TAP` 大小写不一致问题都在本轮修复，故 V2 列全为 ✅。

**① 分量**是 GDS 里的物理连通分量数（`p3_check_electrical_connectivity.py`
实测）。A 有 2 个分量（1 个含 PIN），因为 A 的 GDS 里除主通路外还有一条
**不与 PIN 相连的邻线** —— 这是刻意保留的负样本，不是缺陷。

---

## 4. 唯一数据源

### 4.1 三层源 + 派生产物

```
【源 1】macros/gen_v2_macros.py        ← 几何唯一定义
            ↓
        macros/out/struct_*.gds

【源 2】macros/gen_lef.py              ← PIN/PORT 唯一定义
            ↓
        macros/out/struct_*.lef
        macros/out/macro_index.json

【源 3】macros/p3_placement_plan.py    ← 放置唯一定义
            ↓
        v2_validation/p3_placement.json
            ↓ 派生
        P3_MACRO_BBOX.csv
        src/config.json 的 MACROS 段
        P3_MACRO_PLACEMENT_PLAN.md 表格

【源 4】src/research_macros.v          ← Verilog 端口唯一定义
            ↓ 派生
        src/project.v 的实例连接
        v2_validation/synth_netlist.v（综合产物）
```

**规则**：
- 不手工编辑派生物
- 改动从源出发重新生成
- 断言保护源与派生的一致性

### 4.2 需要新增的断言

**`macros/p3_assert_pin_port_contract.py`**（核心新增）：

| 检查 | 保护 |
|---|---|
| `PIN 名 == Verilog 端口名`（逐字符，区分大小写）| V2 |
| `同一 PIN 的所有 PORT 在同一 GDS 分量` | V1 |
| `无端口宏的 LEF 里 PIN 数 == 0` | — |
| `综合网表里实例的端口名与 LEF 一致` | V2/V3 |
| `每个端口只接一个 net` | V3 |

**复用已有**：
- `p3_assert_consistency.py`（四源坐标 + 5 µm）
- `p3_verify_macro_views.py`（prB = LEF SIZE = GDS bbox）
- `tools/check_source_files.py`（info.yaml / src / Makefile）

---

## 5. 拟修改的文件

### 5.1 必须修改的源文件

| 文件 | 改动 | 理由 |
|---|---|---|
| **`macros/gen_lef.py`** | A/B/C1: PIN 表改单 PIN 多 PORT，名 = `net`<br>C3: PIN 表清空 | V1 + V2 |
| **`src/research_macros.v`** | A/B/C1: `inout wire net`<br>C3: 无端口 | 同上 |
| **`src/project.v`** | `.net(pwm_out)`；C3 实例去端口 | 同上 |
| **`src/config.json`** | IGNORE 加 `research_near`/`u_rs_near` | C3 变几何宏 |

### 5.2 派生物（重新生成）

`struct_{A,B,C1,C3}.lef`、`macro_index.json`、`P3_MACRO_BBOX.csv`、
`P3_SEVEN_MACRO_INTEGRATION.csv`、`P3_MACRO_PLACEMENT_PLAN.md`

### 5.3 几何（**零改动**）

七个宏的 GDS 一个图形都不改。

---

## 6. C3 变更的可验证要求

| # | 要求 | 验证方式 |
|---|---|---|
| 1 | 研究负样本真值不丢失 | 8 个分量在 GDS 中仍独立（`P4_PIN_COMPONENT_AUDIT.json`）|
| 2 | LEF PIN 移除由 `gen_lef.py` 规则维护 | C3 的 `PINS` 表改为 `[]`，重新生成后 PIN 数 = 0 |
| 3 | 派生产物可重复生成 | 重跑 `gen_lef.py` + `p3_integration_matrix.py`，比对哈希 |
| 4 | GDS 无遗留 PIN 标签 | 已实测：C3 GDS 只有 `(68,20)` 和 `(235,4)`，无 label 层 ✅ |
| 5 | 8 个分量在最终 GDS 中再次验证 | CI 后从 `FINAL_GDS_TRUTH` 重跑分量审计 |

---

## 7. 分阶段验收

### 阶段 1：本地（无需 CI）

| # | 检查 | 通过标准 |
|---|---|---|
| 1 | **`p3_assert_pin_port_contract.py`** | 五视图链全通 |
| 2 | `p3_assert_consistency.py` | 四源一致 + 5 µm |
| 3 | `p3_verify_macro_views.py` | prB = LEF = GDS |
| 4 | `p3_check_electrical_connectivity.py` | 分量数符合预期 |
| 5 | `p3_synth_netlist_check.py` | 七实例存活 + 端口名匹配 |
| 6 | `tools/check_source_files.py` | 源文件一致 |
| 7 | `run_all_drc.py` | 0 违规 |
| 8 | `verify_topology.py` | 拓扑正确 |
| 9 | **`p3_verify_lef_obs.py`** | O1–O6 + 规则 E/G；每 PIN ≥3 条 1 µm 全空进路；ODB 三方一致 |
| 10 | **`p3_gds_identity.py`** | 七宏逐图形摘要 = HEAD；日期记录之外字节差 = 0 |
| 11 | **`p3_v1_lef_evidence.py`** | V1 LEF/flow.log 支持规则 E/G（产物缺失时 SKIP，**非 PASS**）|
| 12 | cocotb | 13/13 |
| 13 | `_negative_control.py` | 3/3 被抓 |
| 14 | **`_neg_obs.py`** | 4/4 扰动被抓 |
| 15 | **`_neg_gds_identity.py`** | 3/3 扰动被抓 + roundtrip 反向对照 |

> 这 15 项由 `bash macros/_run_all_checks.sh` 一键覆盖（其中 cocotb 需另跑
> `cd test && make`）。脚本总数 22：上表未逐行列出的驱动脚本
> （`gen_v2_macros.py`、`gen_lef.py`、`p3_placement_plan.py`、
> `p3_patch_config.py`、`p3_integration_matrix.py`、`p3_render_placement.py`、
> `p3_pdn_conflict_check.py`、`p3_sync_docs.py`）在本地全跑中一并执行。

### 阶段 2：官方 CI

| # | 检查 | 通过标准 |
|---|---|---|
| 11 | `CheckMacroInstances` | 七宏识别 |
| 12 | GDS 进入 P&R | 有 routed DEF |
| 13 | **Pin Access** | 无失败 |
| 14 | LVS | 无短路/开路（或可解释）|
| 15 | Precheck | 全过 |
| 16 | DRC | 0 违规 |
| 17 | STA | 无违例或可解释 |

### 阶段 3：最终 GDS 七结构验收

| # | 结构 | 验收 |
|---|---|---|
| 18 | A/B/C1 | 实例存在、`net` PIN 连接、net 归属正确 |
| 19 | C3 | 8 条线存在、间距正确、**互不相连** |
| 20 | C4 | 交叉不连（via = 0）|
| 21 | D | 5 档线宽完整 |
| 22 | E | M1/M2 坐标对齐 |

### 阶段 4：外部确认

2×2 价格、QFN 引脚、去层工艺、停层精度

---

## 8. 实施顺序

```
1. 改 gen_lef.py             A/B/C1 单 PIN 多 PORT；C3 清空 PIN
2. 改 research_macros.v      A/B/C1 → inout net；C3 → 无端口
3. 改 project.v              实例连接改为 .net(pwm_out)
4. 跑 gen_lef.py             重新生成 LEF
5. 跑 p3_patch_config.py     重新生成 config.json
6. 新增 p3_assert_pin_port_contract.py
7. 跑阶段 1 的 10 项检查
8. 报告 → 等待批准 → Commit + Push
9. 观察 CI（重点：Pin Access + LVS）
```

---

## 9. 明确禁止

| 禁止 | 理由 |
|---|---|
| ❌ 伪造 SPICE/CDL | 欺骗工具 |
| ❌ 关 `RUN_LVS` / `RUN_PDN` / `ERROR_ON_PDN_VIOLATIONS` | 掩盖真实问题 |
| ❌ 改 C3 的 GDS 几何使其"能连通" | 破坏研究意图 |
| ❌ 删任何研究结构 | 用户要求七类全保留 |
| ❌ 用全局 `ERROR_ON_DISCONNECTED_PINS:false` | 会掩盖 A/B/C1 的问题 |
| ❌ 为 C3 编造 net ID | 物理上没有 |

---

## 10. 本轮未做

- ❌ 未修改任何设计文件
- ❌ 未 Commit / Push / 触发 CI
- ❌ 未修改 V1
- ✅ 只做了只读检查 + 一个**不修改仓库**的 OpenROAD LEF 解析验证
  （验证文件已删除）

---

## 11. 新增证据：OpenROAD 接受跨层多 PORT PIN

**本轮实测**（临时文件，已删除）：

创建测试 LEF：

```lef
MACRO mp_test
  PIN NET
    DIRECTION INOUT ;
    USE SIGNAL ;
    PORT
      LAYER met1 ;
        RECT 0.0 0.0 0.14 0.14 ;
    END
    PORT
      LAYER met2 ;
        RECT 9.86 4.86 10.0 5.0 ;
    END
  END NET
END mp_test
```

OpenROAD ODB 解析结果：

```
MASTER: mp_test
  PIN NET
    PORT 1 layer=...
    PORT 2 layer=...
    TOTAL PORTS: 2
```

**结论**：ODB 正确识别了"一个 PIN、两个跨层 PORT"。
方案 α 在 **LEF 解析层面可行**。

**仍未验证**：真正的 Pin Access（需要完整 P&R）。
