# V2 官方规则证据（Official Rules Evidence）— v2 修订

日期：2026-10-28（v2 修订）
范围：Tiny Tapeout TTSKY26d + LibreLane 3.0.14 + SKY130A，2×2 Tile
方法：只读研究。**本轮不修改任何设计文件。**

> **v2 修订说明**：用户指出 v1 的判据「所有 PIN 位于同一 GDS 连通分量才允许有端口」
> **是错的**。多 Net 宏的 PIN 本就分属不同分量；真正危险的是「同一物理导体上的
> 多个 PIN 被接到不同逻辑 Net」。
>
> v1 还包含若干**过度推断**（从 `MAGIC_EXT_USE_GDS=False` 推出"必然不会触发 LVS"等），
> 已在 §7 逐条撤回。

---

## 1. 证据等级图例

- **OFFICIAL_REQUIREMENT** —— 官方明确强制
- **OFFICIAL_EXAMPLE** —— 官方示例用法，非强制
- **REPO_OBSERVATION** —— 实测本仓库
- **INFERENCE** —— 基于证据的推断，可能错
- **UNVERIFIED** —— 无法验证

---

## 2. Tiny Tapeout：宏的支持范围

### R1.1 官方 art 指南假设宏无端口

**OFFICIAL_REQUIREMENT** ｜ <https://tinytapeout.com/guides/creating-silicon-art/>

> "Silicon art is decorative — it has no inputs, outputs, or power connections."

**适用范围**：这是"Creating Silicon Art"指南，讲的是**装饰性**宏。
它**没有**说"所有自定义宏都必须无端口"。

**REPO_OBSERVATION**：V2 的 A/B/C1/C3 有真实端口，不属于该指南描述的场景。

### R1.2 `RUN_LVS: false` 只用于 art-only 项目

**OFFICIAL_REQUIREMENT** ｜ 同上

> "**Art-only projects (no logic)**
> If your tile contains only silicon art and little or no functional logic,
> you may also need: `ERROR_ON_PDN_VIOLATIONS: false, RUN_PDN: false, RUN_LVS: false`"

**V2 不适用**（有 Counter/PWM/LFSR）。✅ 我们的 config 未设这些键。

### R1.3 IGNORE_DISCONNECTED_MODULES 要列模块名+实例名

**OFFICIAL_REQUIREMENT** ｜ 同上

> "Add both the macro name (my_logo) and the instance name (logo) to
> IGNORE_DISCONNECTED_MODULES."

**REPO_OBSERVATION**：V2 已列 6 项（3 宏 × 2）。✅

---

## 3. LibreLane：宏集成机制

### R2.1 SPICE 视图是**可选**的

**OFFICIAL_REQUIREMENT** ｜ <https://librelane.readthedocs.io/en/stable/usage/using_macros.html>

> "**SPICE (.spice): Optional**
> currently unused, but may be used in the future for hierarchical LVS.
> As LibreLane produces a SPICE view of all macros, it is prudent to include
> it anyway."

**准确含义**：SPICE 文件**不是必填**，且 LibreLane 会自己生成某种视图。

**⚠️ v1 的过度推断**：v1 说"所以缺 CDL 不会失败"。
**实际**：这只说明文件可选，**不说明**生成的视图能否正确表达被动金属宏的内部连通。
→ 见 §7 的撤回。

### R2.2 `MAGIC_EXT_USE_GDS` 默认 **False**

**OFFICIAL_REQUIREMENT** ｜ <https://librelane.readthedocs.io/en/latest/reference/step_config_vars.html>

> "**MAGIC_EXT_USE_GDS** bool
> A flag to choose whether to use GDS for spice extraction or not.
> **If not, then the extraction will be done using the DEF/LEF, which is faster.**
> Default: **False**"

**REPO_OBSERVATION**：V2 `src/config.json` 未设置此键 → 生效值 `False`。

**能推出什么**：默认走 DEF/LEF 提取。
**不能推出什么**：❌ 不能推出"LVS 必然不检查宏内部"——DEF 里包含宏的实例化
几何（位置、朝向、LEF 抽象），提取器如何使用这些信息**取决于 Magic 实现**，
我没有读到该实现。→ §7 撤回。

### R2.3 `IGNORE_DISCONNECTED_MODULES` 的官方定义

**OFFICIAL_REQUIREMENT** ｜ 同上

> "**IGNORE_DISCONNECTED_MODULES** PDK — List[str]?
> **Modules (or cells) to ignore when checking for disconnected pins.**"

**UNVERIFIED**：是否接受实例名（TT 指南要求列，LibreLane 定义只提 module/cell）。

### R2.4 MACROS schema

**OFFICIAL_REQUIREMENT** ｜ using_macros

```json
"MACROS": {
  "<name>": {
    "instances": { "<inst>": { "location": [x,y], "orientation": "N" } },
    "gds": [...], "lef": [...],
    "spice": [...], "sdf": [...], "json": [...]   // 全部可选
  }
}
```

**REPO_OBSERVATION**：V2 结构一致。✅

### R2.5 orientation 值域

**OFFICIAL_EXAMPLE**：LibreLane 只给 `"N"` 的例子。
**UNVERIFIED**：完整值域。

**REPO_OBSERVATION**：V2 全部用 `N`，不依赖该不确定点。✅

---

## 4. LEF/DEF：PIN 与 PORT 的语义（**本轮新增，最关键**）

### R4.1 一个 LEF PIN 可以有多个 PORT

**REPO_OBSERVATION（强证据）** ｜ `tt-counter-exp/official_ci/tt_submission/tt_submission/tt_um_jiahao_plus_counter.lef`

V1 的顶层宏 `VGND`：

```lef
PIN VGND
  DIRECTION INOUT ;
  USE GROUND ;
  PORT
    LAYER met4 ;
      RECT 21.580 2.480 23.180 109.040 ;
  END
  PORT
    LAYER met4 ;
      RECT 60.450 2.480 62.050 109.040 ;
  END
  PORT
    LAYER met4 ;
      RECT 99.320 2.480 100.920 109.040 ;
  END
  PORT
    LAYER met4 ;
      RECT 138.190 2.480 139.790 109.040 ;
  END
END VGND
```

**一个 PIN `VGND`，4 个 PORT，分布在不同 x 位置。**

**这是 V1 通过官方 Precheck 15/15 的真实文件。**

**结论**：LEF/DEF **原生支持**"一个逻辑 PIN 挂在多个物理接入位置"。
这正是用户第二项要求的方案，且**已被本项目自己的 V1 证实可用**。

### R4.2 我们的宏 GDS 没有 pin/label 标签层

**REPO_OBSERVATION**：

```
A:   label/pin layers = None
B:   label/pin layers = None
C1:  label/pin layers = None
C3:  label/pin layers = None
```

四个宏的 GDS 只有 `(68,20)` 金属、`(68,44)` via、`(69,20)` 等 + `(235,4)` prBoundary。

**对照 V1**：

| 层 | V1 顶层形状数 |
|---|---|
| `met4.pin` (71/16) | **51**（顶层 I/O 引脚）|
| `met4.label` (71/5) | 51 |
| `met1.pin` (68/16) | **0** |
| `met1.label` (68/5) | 0 |

**含义**：V1 的内部（标准单元）**不需要** met1 pin 标签层。只有顶层 I/O 需要。
所以我们的宏没有 pin 标签**可能是正常的**——但**未验证** LVS 是否需要。

→ 列为 §7 的风险项。

### R4.3 LEF PIN 名与 Verilog 端口名的**大小写不一致**（**本轮新增，真实缺陷**）

**REPO_OBSERVATION**：

| 宏 | Verilog 端口 | LEF PIN | 一致？ |
|---|---|---|---|
| A | `a`, `b` | `A`, `B` | ❌ **大小写不同** |
| B | `a`, `b` | `A`, `B` | ❌ |
| C1 | `in`, `tap` | `IN`, `TAP` | ❌ |
| C3 | `p0..p3`, `q0..q3` | `P0..P3`, `Q0..Q3` | ❌ |

**这是真实缺陷。** 用户第三项指出的问题成立。

**后果（INFERENCE，需验证）**：OpenROAD/LibreLane 用 LEF PIN 名去匹配 Verilog
实例的端口名。大小写不一致会导致：
- 找不到匹配 pin → Pin Access 失败或该 pin 被视为未连接
- 或工具做大小写归一化（未验证）

**这是必须修的。** 修法：让 `gen_lef.py` 的 PIN 名与 Verilog 端口名**逐字符相同**。

---

## 5. 物理连通性实测

### R5.1 四个宏的真实连通分量

**REPO_OBSERVATION** ｜ `v2_validation/P4_PIN_COMPONENT_AUDIT.json`

| 宏 | 总分量 | 每个 PIN 所在分量 |
|---|---|---|
| A | 2 | A→C0, B→C0 |
| B | 1 | A→C0, B→C0 |
| C1 | 1 | IN→C0, TAP→C0 |
| C3 | 8 | P0→C0, Q0→C1, P1→C2, Q1→C3, P2→C4, Q2→C5, P3→C6, Q3→C7 |

### R5.2 综合网表里两端的 Net（**本轮新增，核心矛盾**）

**REPO_OBSERVATION** ｜ `v2_validation/synth_netlist.v`

| 宏 | 端口 → Net | 端口数 | 同一 Net？ |
|---|---|---|---|
| A | `a=pwm_out`, `b=rs_a_out` | 2 | ❌ **不同 net** |
| B | `a=pwm_out`, `b=rs_b_out` | 2 | ❌ **不同 net** |
| C1 | `in=pwm_out`, `tap=rs_br_tap` | 2 | ❌ **不同 net** |

**这是必须解决的核心矛盾**：

- **物理**：A 的两个端口是**同一条连续金属**（实测 C0 分量含两个 PIN）
- **网表**：它们是**两个独立 net**（`pwm_out` 和 `rs_a_out`）

**这意味着**：router 会把 `pwm_out` 和 `rs_a_out` 当作两条独立的线去布线。
如果它们各自被连到别处，就会形成**设计者未预期的电气连接**。

**注意**：这不是 LVS 报错与否的问题，而是**网表与物理不自洽**的架构问题。

---

## 6. LVS 覆盖范围：能确定和不能确定的

### 6.1 能确定的

**REPO_OBSERVATION**：
- `MAGIC_EXT_USE_GDS` 未设置 → 默认 `False` → 提取用 DEF/LEF
- `RUN_LVS` 未设置 → 默认 `True` → LVS 会跑
- LEF 里只有 PIN/PORT/RECT，没有内部金属几何

### 6.2 **不能确定的**（v1 曾错误地"确定"了）

| 问题 | 为什么不能确定 |
|---|---|
| LVS 是否会因宏内部短路而报错 | 取决于 Magic 如何用 DEF 里的宏实例信息 |
| LVS 是否会因宏内部开路而报错 | 同上 |
| LVS 是否要求宏有 CDL | 官方说 SPICE 可选，但**没说**没有时行为如何 |
| LVS 是否要求 GDS pin 标签 | 未验证 |
| `MAGIC_EXT_USE_GDS=True` 时 Magic 能否正确提取 | 未验证 |

**结论：LVS 的行为在本轮无法确定，必须靠首次 CI 观察。**

---

## 7. 撤回 v1 的过度推断

| # | v1 的说法 | 为什么撤回 |
|---|---|---|
| 1 | "因为 `MAGIC_EXT_USE_GDS=False`，所以 A/B/C1 必然不会触发 LVS 问题" | ❌ **过度推断**。只知提取走 DEF/LEF，不知 Magic 如何使用宏实例信息 |
| 2 | "因为 SPICE 文件可选，所以任意被动金属宏都会被正确处理" | ❌ **过度推断**。文件可选 ≠ 自动生成正确 |
| 3 | "因为 C3 的 PIN 分属不同物理分量，所以它不能作为有端口宏" | ❌ **判据本身错误**。用户指出：多 Net 宏的 PIN 本就分属不同分量 |
| 4 | "因为没有 Net ID，所以物理导体必然彼此独立" | ❌ **因果颠倒**。物理独立是实测事实，与有无 Net ID 无关 |
| 5 | "路线 D 只剩唯一的 U1 风险" | ❌ **严重低估**。见 §8 的完整风险清单 |

### 7.1 关于第 3 条的详细更正

**v1 的错误判据**：「所有 PIN 位于同一 GDS 连通分量，才允许有电气端口」

**为什么错**：
- 一个正常的多 Net 宏（如一个双路缓冲器），两个输出 PIN 必然在两个不同分量
- 按 v1 的判据，这种宏"不允许有端口"——荒谬

**正确的判据**（用户给出的）：
- **同一物理导体上的多个 PIN，必须对应同一逻辑 Net**（否则网表与物理矛盾）
- **不同物理导体上的 PIN，对应不同逻辑 Net**（正常情况）

**对 C3 的影响**：C3 有 8 个独立导体、8 个 PIN。若每个 PIN 对应一个独立 net，
**技术上完全合法**——它就是一个 8 端口的无源连接器。

**所以"C3 必须无端口"的结论需要重新论证**——见 `V2_ARCHITECTURE_DECISION.md` v2。

---

## 8. 完整风险清单（替代 v1 的"唯一风险 U1"）

| # | 风险 | 等级 | 状态 | 依据 |
|---|---|---|---|---|
| **K1** | **A/B/C1 的物理短路与网表两 net 不自洽** | **高** | **未解决** | R5.2 |
| **K2** | **LEF PIN 名与 Verilog 端口名大小写不一致** | **高** | **未解决** | R4.3 |
| K3 | LVS 如何处理"LEF 有 pin、内部无逻辑"的宏 | 高 | UNVERIFIED | §6.2 |
| K4 | 宏 GDS 无 pin 标签层是否影响 LVS/OpenROAD | 中 | UNVERIFIED | R4.2 |
| K5 | LEF 无 OBS，宏内部金属对 router 不可见 | 中 | **已处理（后续轮次）** | 实测 OBS 数 = 0（当时）；现已按 V1 实证加 OBS，见 `V2_FINAL_INTERFACE_DECISION.md` §7 |
| K6 | 无 Liberty 的宏在 STA 中如何处理 | 中 | UNVERIFIED | — |
| K7 | `IGNORE_DISCONNECTED_MODULES` 是否接受实例名 | 低 | UNVERIFIED | R2.3 |
| K8 | C3 若保留 8 端口，其 net 语义是否合理 | 中 | **需重新论证** | §7.1 |
| K9 | 2×2 真实 Core/PDN/宏坐标 | 高 | 未获得 | 无 CI 产物 |
| K10 | Pin Access 是否合法（LEF PIN 位置 + 5 µm 间距） | 中 | 未验证 | — |

---

## 9. 仍需官方确认的问题

| # | 问题 | 阻塞什么 |
|---|---|---|
| Q1 | LibreLane LVS 如何处理被动短路宏（两 pin 内部相连）？ | K1/K3 的解法 |
| Q2 | LEF PIN 名与 Verilog 端口名是否必须逐字符相同？ | K2 |
| Q3 | 宏是否需要 GDS pin 标签层（68/16 等）？ | K4 |
| Q4 | 无 Liberty 的宏在 STA 中的处理方式？ | K6 |
| Q5 | 单 PIN 多 PORT 在 OpenROAD Pin Access 中的行为？ | 方案选择 |

---

## 10. 本轮证据等级汇总

| # | 结论 | 等级 |
|---|---|---|
| R1.1 | art 指南假设无端口 | OFFICIAL_REQUIREMENT |
| R1.2 | `RUN_LVS:false` 仅 art-only | OFFICIAL_REQUIREMENT |
| R1.3 | IGNORE 要列模块+实例名 | OFFICIAL_REQUIREMENT |
| R2.1 | SPICE 可选 | OFFICIAL_REQUIREMENT |
| R2.2 | `MAGIC_EXT_USE_GDS` 默认 False | OFFICIAL_REQUIREMENT |
| R2.3 | IGNORE 定义只提 module/cell | OFFICIAL_REQUIREMENT |
| R2.4 | MACROS schema | OFFICIAL_REQUIREMENT |
| R2.5 | orientation 值域 | UNVERIFIED |
| **R4.1** | **一个 PIN 可有多 PORT（V1 VGND 实证）** | **REPO_OBSERVATION** |
| **R4.2** | **宏 GDS 无 pin 标签层** | **REPO_OBSERVATION** |
| **R4.3** | **PIN 名与端口名大小写不一致** | **REPO_OBSERVATION** |
| **R5.1** | 四宏连通分量实测 | **REPO_OBSERVATION** |
| **R5.2** | **A/B/C1 两端在网表是不同 net** | **REPO_OBSERVATION** |
| 6.1 | LVS 提取走 DEF/LEF | INFERENCE |
| 6.2 | LVS 具体行为 | UNVERIFIED |
