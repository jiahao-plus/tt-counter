# V2 最终接口方案（Final Interface Decision）

日期：2026-10-28
状态：**候选方案，等待批准后实施。**
本轮：只读验证 + 决策，未修改设计文件。

---

## 1. 推荐接口：**α′**

### 1.1 定义

**一个逻辑 PIN → 一个 PORT → PORT 内含多个跨层金属图形（同一真实连通分量）。**

```lef
PIN net
  DIRECTION INOUT ;
  USE SIGNAL ;
  PORT
    LAYER met1 ;
      RECT 0.00 0.00 0.14 0.14 ;     # M1 接入点
    LAYER met2 ;
      RECT 8.00 2.00 8.14 2.14 ;     # M2 接入点
  END
END net
```

注意：**一个 `PORT` 块内列多个 `LAYER`/`RECT`**，不是多个 `PORT` 块。

```verilog
(* blackbox *) (* keep *) module research_via1 (inout wire net);
endmodule
```

### 1.2 为什么是 α′ 而不是 α（多 PORT）

LEF/DEF 语义（**基于 ODB 数据结构 + 用户指出的规范**）：

| 结构 | 语义 | 路由器行为 |
|---|---|---|
| **同一 PIN 的多个 PORT** | **弱连接** | 路由器可各自接入；各 PORT 之间不保证连通 |
| **同一 PORT 内多个几何图形** | **强连接** | 视为一个整体接入点 |

**V1 的 VGND 多 PORT 不能作为依据**——VGND 是**电源网**，电源路由器
对多 PORT 的处理与信号路由器不同（电源网允许大量并联接入）。

**信号宏必须用强连接**，所以选 α′。

### 1.3 本地验证（已执行）

用 OpenROAD ODB 解析 α′ 结构的测试 LEF（临时文件，已删除）：

```
MASTER: ap_test
  PIN NET dir=INOUT
    PORT 1 : 2 geometry items, layers = met1 met2
    TOTAL PORTS: 1
```

**结果**：1 个 PIN、**1 个 PORT**、2 个几何图形。

ODB 数据结构（`src/odb/include/odb/db.h`）：
```
dbMTerm (PIN) → dbSet<dbMPin> (PORT) → dbSet<dbBox> (几何)
```

**这证明 α′ 在 LEF 解析层面可行。**

**⚠️ 不等同于**：Pin Access 成功、布线成功。那需要完整 P&R，本地做不到。

---

## 2. 备选：**β**

```lef
PIN A  ... END A      # 两个独立 PIN
PIN B  ... END B
```

```verilog
(* blackbox *) (* keep *) module research_via1 (inout wire a, inout wire b);
endmodule
```

```verilog
// project.v
research_via1 u_rs_via1 (.a(pwm_out), .b(pwm_out));   // 两端口接同一 net
```

**优点**：LEF 结构简单，无跨层 PORT 的风险。
**缺点**：网表里一个 net 驱动两个 pin，语义上不如 α′ 直接。

**仅在 α′ 的 Pin Access 失败时采用。**

---

## 3. 为什么 α′ 符合 LEF/DEF 语义

| 规范要点 | α′ 如何满足 |
|---|---|
| 一个 PIN = 一个逻辑端点 | ✅ 只有一个 PIN `net` |
| PORT 内的几何是强连接 | ✅ 两个金属图形在同一 PORT 块内 |
| 强连接保证 PORT 内几何属于同一节点 | ✅ 物理上 C0 分量确实连通（实测）|
| 路由器从 PORT 内选一个图形接入 | ✅ 从 M1 或 M2 接入，物理等价 |

**核心**：α′ 用 LEF 的**强连接**语义，精确表达了"这两个金属接入点是同一个节点"。

---

## 4. 端口方向

### 4.1 决策：`inout`

| 方案 | Verilog | LEF | 问题 |
|---|---|---|---|
| **输入** | `input wire net` | `DIRECTION INPUT` | ❌ 暗示信号流入，与被动金属不符；连续网表里会强制单向 |
| **输出** | `output wire net` | `DIRECTION OUTPUT` | ❌ 同上，反向 |
| **双向** | `inout wire net` | `DIRECTION INOUT` | ✅ **无方向语义，符合被动金属** |

**决策：全部用 `inout` / `INOUT`。**

**理由**：被动金属没有方向。用 `input`/`output` 会暗示这是一个有源器件，
在连续网表里可能引入不必要的约束。

**不虚构电气器件**：`inout` 是 Verilog/LEF 的原生方向值，不是伪造的。

---

## 5. 七宏的 Net / 几何归属

| ID | 宏 | ① GDS 分量 | ② LEF PIN | ③ Verilog | ④ 网表 Net | ⑤ 最终 GDS |
|---|---|---|---|---|---|---|
| **A** | `research_via1` | C0（含 M1+M2），C1（邻居线，无 PIN）| `net`（1 PORT，2 图形：met1+met2）| `inout net` | `pwm_out` | 待 CI |
| **B** | `research_via2` | C0（含 M2+M3）| `net`（1 PORT，2 图形：met2+met3）| `inout net` | `pwm_out` | 待 CI |
| **C1** | `research_branch` | C0（主干+3 分支）| `net`（1 PORT，**4 图形**：met1 主干 + 3×met2 分支）| `inout net` | `pwm_out` | 待 CI |
| **C3** | `research_near` | **8 个独立分量** | **无** | 无 | 无 | 待 CI |
| **C4** | `research_cross` | 2（交叉不连）| 无 | 无 | 无 | 待 CI |
| **D** | `research_dense` | 13 | 无 | 无 | 无 | 待 CI |
| **E** | `research_fiducial` | 4 | 无 | 无 | 无 | 待 CI |

### 5.1 关键约束

| # | 约束 | 验证 |
|---|---|---|
| 1 | 一个金属连通分量 → 一个功能 Net | 断言：PIN 的所有 PORT 几何在同一分量 |
| 2 | LEF PIN 名 == Verilog 端口名（逐字符）| 断言：字符串相等 |
| 3 | GDS 连通域 ↔ LEF 几何 ↔ 网表 Net 关联正确 | 断言：三分量交叉核对 |
| 4 | **物理独立的邻近金属不能误接功能 Net** | A 的 netC（邻居线）**无 PIN**；断言 PIN 不在该分量 |
| 5 | 综合后七宏实例全部保留 | `p3_synth_netlist_check.py` |

**第 4 条特别重要**：A 宏的 C1 分量（`y=6.73` 的邻居线）**必须保持无 PIN**。
当前 LEF 的 PIN B 在 M2 上，不在邻居线——✅ 正确。

---

## 6. 研究真值的三层区分

| 层级 | 含义 | 当前状态 |
|---|---|---|
| **T1** | GDS 中确实存在 Via 连接（M1–Via1–M2 物理连通）| ✅ 已实测（C0 分量）|
| **T2** | 该 Via 连通域被分配到功能信号 Net | ✅ **设计期已验证**（Verilog 端口 → 综合网表 net → LEF PIN 名三段一致，均为 `pwm_out`）；⏳ **布线后的物理归属未验证**，需 CI 的 routed DEF / final GDS |
| **T3** | 功能电流必须经过该 Via | ❌ **未验证，不得声称** |

**本课题的主要目标是 T1 和 T2。**

**T3 需要**：实际工作时该 net 的电流路径分析 + 物理证据（如 IR drop、电迁移）。
当前无任何证据，**不声称**。

---

## 7. LEF OBS

### 7.1 上一版的状态（已作废）

上一版此处记录"七个宏的 LEF **全部没有 OBS**（`grep -c OBS` = 0）"，
并决定"本轮不添加 OBS"。该决定已被本轮推翻，原因见 7.2。

### 7.2 为什么必须加

本轮从 V1 的真实交付物取证，而不是靠推测：

**证据一 —— V1 官方 LEF 的形状**（`tt-counter-exp/official_ci/GDS_logs/runs/
wokwi/final/lef/tt_um_jiahao_plus_counter.lef`，由 Magic 在 Precheck 15/15
通过的那次 CI 写出，491 行）：

- 没有 pin 的层（li1 / met1 / met2 / met3 / nwell）每层各 **一个** OBS 矩形，
  覆盖整层绘制范围；
- 有 pin 的层（met4）有 51 个 pin 与 50 个 OBS 矩形共存，
  **同层 pin/OBS 重叠面积为 0**。

即"官方流程自己产出的 LEF **有** OBS"，而且规则是"金属减去 pin"。上一版
"等 CI 报错再说"的做法与这个实证相反。

**证据二 —— 本流程里没有别的保护机制**（`.../runs/wokwi/flow.log`）：

- `PDN_OBSTRUCTIONS`、`ROUTING_OBSTRUCTIONS`、`FP_OBSTRUCTIONS` 三个键
  **均未定义**，对应的 obstruction 注入步骤全部跳过；
- 唯一与宏有关的预处理是第 18 步
  `cut_rows -halo_width_x 10.0 -halo_width_y 10.0`，它只切标准单元行。

所以对每个宏而言，**LEF 的 OBS 就是唯一的逐宏布线保护**。留空等于把
研究图形的完整性交给路由器的偶然行为。

### 7.3 本轮决策：加 OBS，按宏分两条规则

两条规则均由 `macros/gen_lef.py` 的源规则生成（`OBS_RULE` 表 +
`obs_rule_e()` / `obs_rule_g()`），不是手工改派生 LEF。

**规则 E —— A/B/C1（电气宏）：`OBS = 绘制金属 − PIN 图形`**

这是 V1 规则在有 pin 宏上的推广。OBS 盖住 PIN 就等于废掉 PIN，减去 PIN
才能既隐藏内部金属又保留合法接入。生成后逐层断言：

- O1 任一 OBS 矩形与 PIN 矩形重叠面积 = 0；
- E 精确性：`金属 − OBS − PIN` 必须为空（否则留下路由器看不见的金属），
  且 `OBS − 金属` 必须为空（否则挡住空白区域，可能切断接近走廊）。

实测每个 PIN 至少保留三个自由接近方向（探测方法：在 PIN 矩形四边各
外扩一条 1 dbu 走廊，检查是否落在 OBS 内）。

**规则 G —— C3/C4/D/E（几何宏）：`OBS = 整个 prBoundary 矩形`**

这四个宏没有 PIN，没有任何理由让内部空间保持可布。放任它可布反而有害：
C3 的对间间隙实测 **2.000 µm**，是 met1 线宽 0.14 µm 的十四倍 —— 足够
路由器在一对线之间穿一条线，或在 0.28 / 0.50 µm 阶梯旁落一个 via。整块
阻挡把"最终 GDS 里的结构就是我们画的结构"变成**输入的属性**，而不是对
路由器的期望。A 的 2.600 µm 走廊、C1 的 3.8 µm 走廊同理。

规则 G **只施加于该宏真正绘制了图形的层**，刻意不写 met4/met5：

- 这些宏没有 met4/met5 图形，挡它没有意义；
- M4 是 PDN stripe 层（本流程 `PDN_VERTICAL_LAYER = met4`，1.6 µm stripe
  贯穿 core），且 `ERROR_ON_PDN_VIOLATIONS = True`。在没有证据表明 stripe
  会避开该宏的情况下挡 M4，等于主动制造一个 PDN 违规。

宏下方的 met1 电源轨由流程自己处理：第 18 步 `cut_rows` 带 10 µm halo，
早于第 21 步的 PDN 生成，所以宏内部及其 halo 内不会生成 followpin。

### 7.4 实测结果

```
tag  cell                 size_um            pins  ports  access  rule  obs_rect model
A    research_via1        8.140x4.940        1     1      2       E     7        ELECTRICAL
B    research_via2        10.220x3.235       1     1      2       E     6        ELECTRICAL
C1   research_branch      10.140x3.200       1     1      4       E     13       ELECTRICAL
C3   research_near        10.140x8.240       0     0      0       G     1        geometry-only
C4   research_cross       10.140x8.140       0     0      0       G     2        geometry-only
D    research_dense       35.000x5.790       0     0      0       G     3        geometry-only
E    research_fiducial    4.000x4.000        0     0      0       G     2        geometry-only
```

α′ 结构未被 OBS 破坏：PIN 数、PORT 数、接入点数与加 OBS 前完全一致
（A/B/C1 仍是 1 PIN / 1 PORT / 2–4 个跨层几何）。

### 7.5 仍未验证的

- OBS 是否被 LibreLane 的 router **实际遵守**：需要 routed DEF。
- 真实 2×2 的 M4 stripe 位置：`PDN_VERTICAL_LAYER` 若在 2×2 中改层或用
  不同的 stripe 模式，需要重新评估是否需要挡 M4。本地 `p3_pdn_conflict_check.py`
  给出的只是按 V1 pitch 外推的估计。

---

## 8. 必须改动的文件

### 8.1 源文件（4 个）

| 文件 | 改动 |
|---|---|
| **`macros/gen_lef.py`** | PIN 表改为：<br>A/B/C1 → `net` 单 PIN 单 PORT 多图形<br>C3 → 清空 PIN<br>方向改 `INOUT` |
| **`src/research_macros.v`** | A/B/C1 → `inout wire net`<br>C3 → 无端口 |
| **`src/project.v`** | 实例改为 `.net(pwm_out)`；C3 实例去端口 |
| **`src/config.json`** | IGNORE 加 `research_near` / `u_rs_near` |

### 8.2 新增断言（1 个）

**`macros/p3_assert_pin_port_contract.py`**：

| 检查 | 保护 |
|---|---|
| LEF PIN 名 == Verilog 端口名（逐字符）| 大小写问题 |
| 同一 PIN 的所有 PORT 几何在同一 GDS 分量 | 强连接语义 |
| 无端口宏的 LEF PIN 数 == 0 | C3/C4/D/E |
| LEF PIN 数 == Verilog 端口数 | — |
| 邻居金属（A 的 netC）无 PIN | 规则 4 |

### 8.3 派生物（重新生成，不手改）

`struct_{A,B,C1,C3}.lef`、`macro_index.json`、`P3_MACRO_BBOX.csv`、
`P3_SEVEN_MACRO_INTEGRATION.csv`、`P3_MACRO_PLACEMENT_PLAN.md`

### 8.4 GDS 几何

**零改动。** 七个宏一个图形都不改。

---

## 9. 本地必须通过的验收

| # | 检查 | 脚本 | 通过标准 |
|---|---|---|---|
| 1 | 五视图契约 | **`p3_assert_pin_port_contract.py`**（新增）| 全通 |
| 2 | 四源一致 + 5 µm | `p3_assert_consistency.py` | PASS |
| 3 | prB = LEF = GDS | `p3_verify_macro_views.py` | PASS |
| 4 | 电气连通 + 分量数 | `p3_check_electrical_connectivity.py` | PASS |
| 5 | **综合网表七实例 + 端口名** | `p3_synth_netlist_check.py` | 7/7 存在，端口名匹配 |
| 6 | 源文件一致 | `tools/check_source_files.py` | PASS |
| 7 | 几何 DRC | `run_all_drc.py` | 0 违规 |
| 8 | 拓扑 | `verify_topology.py` | PASS |
| 9 | cocotb | `test/make` | 13/13 |
| 10 | DRC 负向对照 | `_negative_control.py` | 3/3 被抓 |

**第 5 项是本轮重点**：必须验证综合后每个实例的端口名与 LEF PIN 名逐字符一致。

---

## 10. 后续官方 CI 还需验证

| # | 项 | 为什么本地做不到 |
|---|---|---|
| 1 | **Pin Access** | 需要完整 P&R |
| 2 | α′ 的单 PORT 多图形是否被 router 正确使用 | 同上 |
| 3 | LVS 是否接受"内部短路的被动宏" | 需要 netgen + 真实 GDS |
| 4 | 宏是否被 fill/PDN 覆盖 | 需要最终 GDS |
| 5 | 最终 GDS 里七结构是否存在 | 同上 |
| 6 | C3 的 8 个分量是否仍独立 | 同上 |
| 7 | 真实 Core / PDN / 宏坐标 | 需要 DEF |
| 8 | 布线是否穿过研究图形 | 需要 routed DEF（OBS 已加，见 §7，但实际遵守情况仍需 DEF 验证）|
| 9 | STA 对无 Liberty 宏的处理 | 需要 STA 报告 |

---

## 11. 若 α′ 失败的处理路径

```
α′ Pin Access 失败
    ↓
① 先看错误类型
    ├─ 接入图形太小/位置不当 → **修正接入图形**（改 LEF 的 RECT，不改 GDS）
    │       ↓ 重新验证
    │   若修好 → 继续 α′
    └─ 工具根本不支持跨层强连接 PORT → 转 β
                ↓
            β：两 PIN 同 net
```

**禁止**：直接关闭检查、伪造器件、改 GDS 几何。

---

## 12. 实施顺序（获批后）

```
1. 改 gen_lef.py         4 个宏的 PIN 定义
2. 改 research_macros.v  3 个宏的端口
3. 改 project.v          实例连接
4. 跑 gen_lef.py         重生成 LEF
5. 跑 p3_patch_config.py 重生成 config
6. 新增 p3_assert_pin_port_contract.py
7. 跑 §9 的 10 项验收
8. 报告结果 → 等待批准 → Commit + Push
```

---

## 13. 本轮已做的验证（只读，未改仓库）

| 验证 | 方法 | 结果 |
|---|---|---|
| α′ 结构能被 ODB 解析 | 临时 LEF + OpenROAD | ✅ 1 PIN / 1 PORT / 2 几何 |
| 当前四宏的物理分量 | pya 连通性分析 | ✅ A:2, B:1, C1:1, C3:8 |
| 综合网表的端口-net 映射 | 解析 synth_netlist.v | ✅ A/B/C1 各两 net（矛盾确认）|
| 端口名大小写 | 读实际文件 | ✅ 全部不一致（缺陷确认）|
| 宏 GDS 的标签层 | pya 层扫描 | ✅ 无 label/pin 层 |
| LEF OBS | grep | 上一版：全部 0 → **本轮已加**，见 §7 |

**临时文件已删除。仓库设计文件未改动。**
