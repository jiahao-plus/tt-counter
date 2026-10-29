# Item 3 — Netgen LVS 44 个错误的独立根因调查

编写日期：2026-10-29
依据：第三轮官方 CI 产物，**未引用任何先验结论，全部从文件重新测量**。

---

## 0. 我此前 LVS 报告的两处错

| 我此前的说法 | 事实 |
|---|---|
| "44 个错误基本都能归因于 tap 不足" | **错**。44 里只有一部分与 tap 有关，见 §1 的权威分解 |
| "44 = 19 net 对 + 23 device 对 + 2 pin 对" | **错**。这是我把 `.rpt` 里**逐条列出的明细行数**当成了 LibreLane 的 `design__lvs_error__count`。两者的口径不同，见 §1.1 |
| "Magic 提取的顶层只有 8 个端口" | **错**。`.subckt` 用了 `+` 续行，实际 **45 个**端口。是我解析漏了续行 |
| "`pwm_out` 不在提取网表里" | **对，但原因不是我最初以为的物理断开** —— 见 §3 |

---

## 1. 44 个错误：权威分解

### 1.1 权威来源

`66-netgen-lvs/state_out.json` 的 `metrics` 里，LibreLane 自己写下的七个计数：

```
design__lvs_device_difference__count = 21
design__lvs_net_difference__count    = 16
design__lvs_property_fail__count     =  0
design__lvs_unmatched_device__count  =  1
design__lvs_unmatched_net__count     =  1
design__lvs_unmatched_pin__count     =  5
design__lvs_error__count             = 44      ← 汇总指标
```

**这六项相加恰好 = 44**（21+16+0+1+1+5）。这就是 `design__lvs_error__count` 的定义，
不是我事后凑出来的。

| 指标 | 值 | 含义 |
|---|---|---|
| `device_difference` | **21** | 器件总数差：Circuit 1 **388** vs Circuit 2 **367** |
| `net_difference` | **16** | 网络总数差：Circuit 1 **405** vs Circuit 2 **389** |
| `unmatched_device` | **1** | 器件类未匹配（`decap_3` 类）|
| `unmatched_net` | **1** | 网络未匹配（`pwm_out` / `FILLER_53_9/VPB` 这一对）|
| `unmatched_pin` | **5** | 顶层端口未匹配，见 §1.3 |
| `property_fail` | **0** | 无属性（参数）失配 |
| **合计** | **44** | |

### 1.2 `.rpt` 里的明细行是另一套口径

`.rpt` 报告里逐条列出的是**不匹配对**，与上面的指标口径不同，两者**不应相加**：

| 明细段落 | 对数 | 说明 |
|---|---|---|
| `NET mismatches` | 19 | 每个 `Net: X \| Net: Y` 一行 |
| `DEVICE mismatches` | 23 | 每个 `Instance: X \| Instance: Y` 一行 |
| `Subcircuit pins` 段不符行 | 5 | 见 §1.3 |

为什么 19/23/5 与 21/16/1/1/5 不是同一件事：
- `device_difference = 21` 是**总数差**（388−367），不是"23 对明细"；
  23 对里有 2 对是匹配上但扇出不同，21 对是 `(no matching instance)`。
- `net_difference = 16` 是**总数差**（405−389），而 `NET mismatches` 段有 19 行
  —— 其中 `VGND`、`VPWR` 两行是**名字匹配上但扇出不同**，不产生总数差；
  另外 `u_rs_*/net` 三行进的是 `unmatched_net` 之外的统计。
- `unmatched_pin = 5` 与 §1.3 的 5 行逐一对应，这点是**一致**的。

**所以我上一版写的 "44 = 19 + 23 + 2" 是错的**：它把明细行数当成了指标，
而且 PIN 段也数错了（实际 5 行不符，不是 2 行）。

### 1.3 顶层 PIN 的 5 处不符（逐行）

从 `lvs.netgen.json` 的 `pins` 两个列表按索引对齐（`tools/v2_ci_diagnostics/lvs_pins.py`），
46 个位置里有 **5 处不同**：

| 索引 | Circuit 1（Magic 提取） | Circuit 2（参考网表） | 性质 |
|---|---|---|---|
| 0 | `VGND` | `(no matching pin)` | 电源端口未匹配 |
| 1 | `VPWR` | `(no matching pin)` | 电源端口未匹配 |
| 32 | `uio_out[7]` | `(no matching pin)` | 对称歧义（R3）|
| 43 | `uio_oe[2]` | `(no matching pin)` | 对称歧义（R3）|
| 45 | `(no matching pin)` | `VPWR` | 电源端口未匹配 |

**注意：`uio_out[7]` 与 `uio_oe[2]` 并没有互相交换**（不像上一版写的"互为错配"）。
在 JSON 的按索引对齐里，两者都只是 `(no matching pin)`；`.rpt` 里之所以显示
`uio_out[7] | uio_oe[2] **Mismatch**`，是 netgen 在打印时把两个未匹配端口**配对显示**的结果。
这两处本质是同一个对称歧义，**不是两个独立错误**。

`VGND`/`VPWR` 三处未匹配则与 R1（`MAGIC_DEF_LABELS = False`）直接相关 ——
电源网名没有从 DEF 传到 Magic，所以参考侧认得 `VPWR`、提取侧认不得。

### 1.4 `.rpt` 的 19 个 NET 明细对（辅助信息，与 §1.1 指标不同口径）

| # | Circuit 1（Magic 提取） | Circuit 2（参考网表） | 根因 |
|---|---|---|---|
| 1 | `FILLER_53_9/VPB` | `pwm_out` | **R1**（Magic 给同一节点起的临时名，与 `pwm_out` 无法按名对齐）|
| 2 | `VGND` | `VGND` | **R2**（扇出 761→719；电源网被碎片撑大）|
| 3 | `VPWR` | `VPWR` | **R2**（扇出 737→719）|
| 4–11, 13–15, 19 | `FILLER_{51,55,57,59,73,75,77,79,80}_9/VPB`（9 个）、`FILLER_{67,69,70}_189/VPB`（3 个） | （无匹配） | **R2：VPB 悬空，与 tap 相关** |
| 12 | `_214_/X` | （无匹配） | **R1** |
| 16–18 | `u_rs_branch/net`、`u_rs_via1/net`、`u_rs_via2/net` | （无匹配） | **R1** |

（行号即 `.rpt` 中 `NET mismatches` 段的实际输出顺序，可用 §8 的 `awk` 命令核对。）

上表行号 4–11、13–15、19 合计 **12** 个浮空的 `FILLER_*/VPB`；加上第 1 行的
`FILLER_53_9/VPB`（误配到 `pwm_out`）共 **13** 个 `FILLER_*/VPB`。

**重要**：13 个 `FILLER_*/VPB` 里只有 12 个是真正浮空，第 1 个是**名字问题**（R1），
不是悬空。真正与 tap 覆盖直接相关的 NET 明细是 **12 个**。

### 1.5 `.rpt` 的 23 个 DEVICE 明细对

Circuit 1 侧按单元类分：**14 × `decap_3` + 9 × `fill_2` = 23**。
Circuit 2 侧 **21 个是 `(no matching instance)`**，另 2 个是
`FILLER_0_100` / `FILLER_11_54`（匹配上了但节点扇出不同）。

21 这个数与 `device_difference = 21`（388−367）**恰好相等**，可互相印证。

```
Instance: sky130_fd_sc_hd__decap_3:FILLER_ |Instance: FILLER_0_100
  VGND = 761                               |  VGND = 719
  VNB  = 761                               |  VNB  = 719
  VPB  = 737                               |  VPB  = 719
  VPWR = 737                               |  VPWR = 719

Instance: sky130_fd_sc_hd__decap_3:FILLER_ |Instance: FILLER_11_54
  VPB  = 1     ← 悬空                         |  VPB  = 719
```

---

## 2. 独立证据链：三个电气宏**物理上是连通的**

### 2.1 最终 DEF 的直接证据

`final/def/tt_um_jiahao_plus_counter.def` 中：

```
- pwm_out ( u_rs_via2 net ) ( u_rs_via1 net ) ( u_rs_branch net ) ( _218_ B1 ) ( _214_ X ) + USE SIGNAL
      + ROUTED met1 ( 104190 216070 ) ( * 216750 )
      NEW met1 ( 103270 216750 ) ( 104190 * )
      NEW met2 ( 103270 200090 ) ( * 216750 )
      NEW met2 ( 89010 216000 ) ( 89320 * 0 )
      ...
```

三个宏的 `net` 引脚与 `_214_` 的 `X`、`_218_` 的 `B1` **在同一个 DEF net `pwm_out` 上**，
且有一条完整的 `ROUTED` 布线把它们连起来（met1→met2→met3，坐标覆盖 x=42.5..103.3）。

### 2.2 提取网表的对照

`final/spice/tt_um_jiahao_plus_counter.spice` 的顶层 `.subckt` 内：

```
Xu_rs_branch u_rs_branch/net research_branch
Xu_rs_near   research_near
Xu_rs_cross  research_cross
Xu_rs_fiducial research_fiducial
Xu_rs_via1   u_rs_via1/net research_via1
Xu_rs_via2   u_rs_via2/net research_via2
Xu_rs_dense  research_dense
...
X_214_ _196_/Y _260_/A _212_/X _213_/X VGND VGND VPWR VPWR _214_/X sky130_fd_sc_hd__a22o_2
```

- `pwm_out` 在**整个文件里出现 0 次**
- `u_rs_via1/net`、`u_rs_via2/net`、`u_rs_branch/net` 各只出现 **1 次**（就在各自的实例行上）
- `_214_/X` 出现 2 次（一次是 `X_214_` 的末尾端口，一次是 `X_218_` 的输入）

**结论：不是物理断开，是 net 命名丢失。** 三个宏和 `_214_/X` 在 Magic 里各自是独立的
连通分量（因为没有标签把它们连起来），所以永远只有 1–2 个引用点。

---

## 3. R1 根因：`MAGIC_DEF_LABELS = False`

`resolved.json`：

```
MAGIC_DEF_LABELS = False
```

作用：LibereLane 在 Step 57 `magic-streamout` 里把 DEF 写进 Magic 时，
**不把 DEF 的 net 名作为 text label 写入**。于是 Magic 的 `extract` 只能按几何连通分量
自动生成临时名（`u_rs_via1/net`、`_214_/X`、`FILLER_53_9/VPB`），
与参考网表（Verilog 里的 `pwm_out`）无法按名字对齐。

### 这解释了哪些症状

| 症状 | 是否由 R1 解释 |
|---|---|
| `u_rs_branch/net` / `u_rs_via1/net` / `u_rs_via2/net` 无匹配 | **是** |
| `_214_/X` 无匹配 | **是** |
| `FILLER_53_9/VPB` ↔ `pwm_out` 错配 | **是**（`FILLER_53_9/VPB` 只是 Magic 给同一节点起的另一个临时名） |
| 顶层 `VGND` / `VPWR` 未匹配（PIN 段 3 行） | **是**（电源网名未从 DEF 传入 Magic）|
| 顶层 `uio_out[7]` / `uio_oe[2]` 未匹配（PIN 段 2 行） | **否**，见 R3 |
| 21 个器件差 | **否**，见 R2 |
| 13 个 `FILLER_*/VPB` net 明细 | **否**（其中 12 个属 R2，1 个属 R1）|

### 为什么 `MAGIC_DEF_LABELS = False`

这是 Tiny Tapeout / LibreLane 的默认值。设为 `True` 会让 Magic 读入全部 DEF label，
可能带来庞大的 text 层与提取时间。**本次不改这个默认值**是更稳妥的选择，
除非能证明它是唯一的阻碍。

> **风险声明**：R1 是**基于文件证据的强推断**，但我**没有在本地跑过 Magic**
> （本机未安装 Magic）。"把 `MAGIC_DEF_LABELS` 设为 `True` 就能让 LVS 通过"这句话
> **我不能证明**。第四轮 CI 必须实测。

---

## 4. R2 根因：VPB/VNB 悬空导致 21 个物理单元被拆分

### 4.1 数字

| 类别 | Circuit 1（Magic） | Circuit 2（参考） | 差 |
|---|---|---|---|
| `sky130_fd_sc_hd__decap_3` | **14** | **1** | **−13** |
| `sky130_fd_sc_hd__fill_2` | **9** | **1** | **−8** |
| 其余各类 | 相同 | 相同 | 0 |
| **总器件数** | **388** | **367** | **−21** |

（`decap_3` 与 `fill_2` 这两行对应 `.rpt` 摘要表的 `(16182->14)` / `(138->9)`，
`->` 表示"该类 16182/138 个几何实例被折叠成 14/9 个连通块"。）

**`design__lvs_device_difference__count = 21` 就是 13 + 8。**
`.rpt` 的 23 对 DEVICE 明细与它口径不同：
- **2 对**匹配上了参考实例但节点扇出不同（`FILLER_0_100`、`FILLER_11_54`）；
- **21 对**是 `(no matching instance)`。

21 恰好等于总数差，这不是巧合 —— 每一个多出来的碎片块就是一个找不到对应的实例。

### 4.2 机理

DEVICE 不匹配段里每个 `decap_3` 实例的节点扇出：

```
Instance: sky130_fd_sc_hd__decap_3:FILLER_...   | Instance: FILLER_0_100
  VGND = 761                                    |   VGND = 719
  VNB  = 761                                    |   VNB  = 719
  VPB  = 737                                    |   VPB  = 719
  VPWR = 737                                    |   VPWR = 719
```

以及：

```
Instance: sky130_fd_sc_hd__decap_3:FILLER_11_54
  VPB  = 1     ← 悬空
  ...
```

**机理**：`decap_3` 与 `fill_2` 是纯物理单元（无逻辑功能）。它们的 `VPB`/`VNB`
如果没接到 tap 环，Magic 提取时就成为独立的小节点，同一个物理单元会被切成多个
只有 1–2 个节点的碎片实例。参考网表侧（Verilog + Liberty）里它们是完整单元，
于是 netgen 看到 21 个多出来的碎片。

**这 21 个器件差与 Item 1 的零 tap 行段直接相关**：`FILLER_11_54` 的 `VPB = 1`
就是悬空的直接读数；12 个浮空 `FILLER_*/VPB` net 与这 21 个碎片是同一现象的
net 侧与 device 侧两个视图。

---

## 5. R3 根因：`uio_out[7]` / `uio_oe[2]` 对称性歧义

```
uio_out[7]   |uio_oe[2] **Mismatch**
uio_oe[2]    |uio_out[7] **Mismatch**
```

netgen 自己的说明（`.rpt` 第 1454 行）：

> "Port matching may fail to disambiguate symmetries."

这两个端口在版图上完全对称（都是 `conb_1` 常量单元驱动的输出），
netgen 无法区分哪个是哪个。这是**工具局限性**，不是设计错误。

**这对应 `design__lvs_unmatched_pin__count` 里的 2 个**（索引 32 与 43，见 §1.3）。
`.rpt` 之所以打印成"互相错配"，是因为它对未匹配端口做了配对显示。

**处理建议**：这条可以通过在顶层加一个可区分的不对称结构解决，但那是**改动设计**，
不在本轮授权范围内。第四轮 CI 应观察：若除 R3 的 2 行与 R1 的 3 行外，
PIN 段不再有新的不符，则可判定为对称性歧义，需要单独决策。

---

## 6. Item 1（tap 修复）能解决什么、不能解决什么

| 根因 | 影响的指标 | Item 1 能解决？ |
|---|---|---|
| R2 器件拆分 | `device_difference` **21**（全部）| **能**（零 tap 行段清零后 VPB 不再悬空）|
| R2 浮空 VPB 网 | `net_difference` **16** 中的主要部分 | **能**（同上，但这两个指标不是一一对应）|
| R1 名字丢失（`pwm_out`、`u_rs_*/net`、`_214_/X`） | `unmatched_net` **1** + `net_difference` 的一部分 | **不能** |
| R1 电源端口未匹配 | `unmatched_pin` 5 个中的 **3** 个（`VGND`/`VPWR`）| **不能** |
| R3 对称性歧义 | `unmatched_pin` 5 个中的 **2** 个（`uio_out[7]`/`uio_oe[2]`）| **不能** |
| 属性失配 | `property_fail` **0** | — |

**所以：只修 tap，LVS 不会通过。**

这是本轮最重要的结论。剩下的 R1 与 R3 需要单独处理：

- **R1**：可以尝试 `MAGIC_DEF_LABELS = True`，但**未经验证**。
  另一个选项是在 Verilog 顶层把 `pwm_out` 拆成显式端口（改动设计，需批准）。
- **R3**：需要打破对称性或接受 netgen 的局限性（可能需要在 setup 里做 port 映射）。

> **注意口径**：`device_difference = 21` 与 `net_difference = 16` 是**总量差**，
> `unmatched_device/net/pin` 是**未匹配项计数**，两者**不能相加也不能互相替代**。
> 上一版把三者混成一个"44 = 19+23+2"，是这一轮最需要纠正的错误。

---

## 7. 本轮**没有**做的事（以及为什么）

- **没有添加任何虚假电源 PIN**（用户明令禁止）
- **没有关闭 LVS**
- **没有声称修复 tap 后 LVS 必然通过** —— §6 明确说明不能
- **没有修改 `src/config.json`** —— 本轮不授权
- **没有本地运行 Magic/Netgen** —— 本机未安装，所有结论均来自 CI 产物分析

---

## 8. 复现方法

```bash
# 44 个错误的权威分解（LibreLane 自己写的指标）
python3 -c "
import json
m=json.load(open('GDS_logs/runs/wokwi/66-netgen-lvs/state_out.json'))['metrics']
for k in sorted(m):
    if k.startswith('design__lvs_'): print(k,'=',m[k])
"

# .rpt 的明细对（不同口径，不要与上面的指标相加）
python3 tools/v2_ci_diagnostics/lvs_count.py        # 19 NET / 23 DEVICE
python3 tools/v2_ci_diagnostics/lvs_json_count.py   # badnets 19 / badelements 23 / 器件总数 388 vs 367
python3 tools/v2_ci_diagnostics/lvs_pins.py         # PIN 段按索引对齐，5 处不符

# DEF 里 pwm_out 的连接
grep -A6 '^- pwm_out ' GDS_logs/runs/wokwi/final/def/tt_um_jiahao_plus_counter.def

# 提取网表里的宏实例
grep '^Xu_rs_\|^X_214_' GDS_logs/runs/wokwi/final/spice/tt_um_jiahao_plus_counter.spice
```
