# P6：第四轮剩余 6 个 LVS 错误的只读根因定位

编写日期：2026-10-29
对应 CI：Commit `b4e32b8a2c679619acc03fe3ad415bb476258260` / Run `40832068010`
状态：**只读分析。未修改任何设计源、GDS/LEF、配置；未 Commit / Push；未触发第五轮 CI。**
证据版本：**草稿 v1** —— 四个独立调查 Agent 的纵深结果尚未全部返回，
本文中标注 `[待交叉核查]` 的条目将在终版中被证实或推翻。

> 证据等级：
> `MEASURED` = 直接读到的文件字节/工具输出；
> `DERIVED` = 由 MEASURED 严格推出；
> `STRONGLY_SUPPORTED_HYPOTHESIS` = 多方向证据一致，但尚缺工具内部源码/标准文本的正面确认；
> `HYPOTHESIS` = 有线索但未证实；
> `UNVERIFIED` = 无法取得证据。

---

## 0. 结论摘要（一句话）

> **6 个 LVS 错误全部来自同一件事：Magic 在 LEF-only 视图下把三个 research 宏的
> `PIN net` 放在了错误的位置——偏了恰好 `2 × ORIGIN`。**
> GDS 本身没有开路，布线也没有错；是 LEF 的 `ORIGIN` 在 Magic 的读入路径里被反向应用了。

错误计数可精确拆解（`librelane/steps/netgen.py:88-94` 的公式，MEASURED）：

```
total = device_diff + net_diff + property_fail + device_fail + net_fail + pin_fail
   6  =      0      +    3    +       0       +     0      +    1     +    2      ✅
```

其中 `badnets` 只有一组（netgen 自己的 JSON 报告，MEASURED）：三个 `u_rs_*/net`
悬空 ↔ 三个 `(no matching net)`。`badelements` 为**空**——没有任何器件错误。

---

## 1. 六个 LVS 指标与原始证据

### 1.1 指标（MEASURED，`final/metrics.json`）

| 指标 | 第 3 轮 | 第 4 轮 |
|---|---|---|
| `design__lvs_error__count` | 44 | **6** |
| `design__lvs_device_difference__count` | 21 | **0** |
| `design__lvs_net_difference__count` | 16 | **3** |
| `design__lvs_unmatched_device__count` | 1 | **0** |
| `design__lvs_unmatched_net__count` | 1 | **1** |
| `design__lvs_unmatched_pin__count` | 5 | **2** |
| `design__lvs_property_fail__count` | 0 | **0** |

### 1.2 netgen 自己的判定（MEASURED，`66-netgen-lvs/reports/lvs.netgen.json`）

```
"badelements": []                      <-- 没有错误器件
"badnets": [ [ <Circuit1 四个网>, <Circuit2 四个网> ] ]   <-- 只有一组
```

`Circuit1`（版图侧）四个网：`_214_/X`、`u_rs_branch/net`、`u_rs_via1/net`、`u_rs_via2/net`
`Circuit2`（原理图侧）四个网：`pwm_out`、`(no matching net)`、`(no matching net)`、`(no matching net)`

`66-netgen-lvs/netgen-lvs.log` 末尾：

```
Circuit 1 contains 366 devices, Circuit 2 contains 366 devices.     <-- 器件数已对齐
Circuit 1 contains 391 nets,    Circuit 2 contains 388 nets. *** MISMATCH ***
```

`66-netgen-lvs/reports/lvs.netgen.rpt:1151`：

```
Final result: Top level cell failed pin matching.
```

**关键**：失败发生在 **pin matching（顶层端口配对）**，不是器件、不是属性。
且器件数 366 vs 366 完全一致。

### 1.3 三个悬空网络的原始表（MEASURED，`lvs.netgen.rpt:1080-1094`）

```
Net: _214_/X          | Net: pwm_out
  a22o_2/B1 = 1       |   a22o_2/X = 1
  a22o_2/X  = 1       |   a22o_2/B1 = 1
                      |   research_branch/net = 1
                      |   research_via1/net = 1
                      |   research_via2/net = 1

Net: u_rs_branch/net  | (no matching net)
Net: u_rs_via1/net    | (no matching net)
Net: u_rs_via2/net    | (no matching net)
```

读法：**版图侧三个宏引脚各成一条孤立网络；原理图侧三个引脚被并进 `pwm_out`。**
这正是"一个单引脚宏，其引脚在版图里没有接触到任何东西"的标准 netgen 表现。

---

## 2. 三宏物理连通性逐项结果

### 2.1 坐标系标定（MEASURED，三条独立的链）

方法：用**真实多边形顶点**（非 bbox 近似）做精确相交。工具 `C:\tmp\p6\poly_exact.py`。
顶层 GDS 有 49 个 cell、18629 个 boundary，其中顶层 15060 个，met1 多边形最多 49 个顶点
——**bbox 近似会造出假接触，所以必须用精确多边形**（这一点已实测确认）。

对每个引脚测试三种坐标模型：

| 模型 | 公式（引脚绝对/局部位置） |
|---|---|
| **G** | `placement + ORIGIN + LEF_rect` |
| **M** | `placement − ORIGIN + LEF_rect` |
| **P** | `placement + LEF_rect`（完全忽略 ORIGIN） |

#### 链一：哪一个模型能让引脚落进宏**自身的** GDS 金属（MEASURED）

| 宏 | 引脚 | G 命中 | M 命中 | P 命中 |
|---|---|---|---|---|
| research_via1 | met1 | **Y** | N | N |
| research_via1 | met2 | **Y** | N | N |
| research_via2 | met2 | **Y** | N | N |
| research_via2 | met3 | **Y** | N | N |
| research_branch | met1 | **Y** | N | N |
| research_branch | met2 ×3 | **Y, Y, Y** | N, N, N | N, N, N |
| **合计** | 8 个引脚 | **8 / 8** | **0 / 8** | **0 / 8** |

进一步：每个 `LEF_rect + ORIGIN` 都精确**落在宏自身金属块内部**
（`CONTAINED_IN_LARGER_BOX`，8/8）——LEF 的引脚声明与宏 GDS 是自洽的。

#### 链二：`.ext` 报告的引脚位置 vs GDS 真值（MEASURED）

`.ext` 坐标为 **5 nm 单位、placement 相对**（用 LEF 引脚 140 nm ↔ 28 units 三点标定，
比例恒为 5.000 nm/unit）。

| 宏 | 层 | Magic 认为的位置 (abs µm) | GDS 真值 (abs µm) | 偏差 |
|---|---|---|---|---|
| research_via1 | m2 | (40.570, 208.070) | (42.430, 211.930) | **dx=+1.860, dy=+3.860** |
| research_via2 | m3 | (72.990, 208.990) | (74.850, 212.850) | **dx=+1.860, dy=+3.860** |
| research_branch | m2 | (87.390, 206.270) | (89.250, 215.930) | **dx=+1.860, dy=+9.660** |

对照各自的 `2 × ORIGIN`：

| 宏 | ORIGIN | 2 × ORIGIN |
|---|---|---|
| research_via1 | (0.930, 1.930) | **(1.860, 3.860)** ✅ |
| research_via2 | (0.930, 1.930) | **(1.860, 3.860)** ✅ |
| research_branch | (0.930, 4.830) | **(1.860, 9.660)** ✅ |

**三个宏全部吻合到 0.001 µm。**

#### 链三：外部布线实际接触在哪一侧（MEASURED）

用 `final/def/tt_um_jiahao_plus_counter.def` 的 `+ ROUTED` 顶点，与
`pwm_out` 网的所有布线点比对：

| 宏 | 层 | G 位端点属 pwm_out | M 位端点属 pwm_out |
|---|---|---|---|
| research_via1 | met2 | **1 个 @ (42.550, 212.000)** | 0 |
| research_via2 | met3 | **1 个 @ (75.000, 213.000)** | 0 |
| **合计** | | 外部布线终止在 **G** 位 | **M 位一个也没有** |

并且：`final GDS` 的顶层金属在 **M 位 8/8 全部 0 命中**，在 G 位 5/8 有真实接触。
（5 而非 8：三个 met1 引脚没有顶层金属接触——见 §2.3。）

> **三链结论（DERIVED）**：LEF 的 `ORIGIN` 语义在物理上是"G 模型"，
> OpenROAD 的路由、最终 GDS 的流片、以及 LEF 自身与宏 GDS 的自洽性，全部是 G；
> **只有 Magic 的 `.ext` 报告的是 M 位**。

### 2.2 为什么 8 个引脚里只有 5 个有顶层接触（MEASURED，重要但非缺陷）

| 宏 | 无顶层接触的引脚 | 原因 |
|---|---|---|
| research_via1 | met1 (0,0,140,140) | 物理上确实没有任何布线经过该点（其周围 2 µm 内顶层 met1 box 数 = **0**） |
| research_branch | met2 ×2（中间两个 pad） | 该两个 pad 位于 met1 bar 之上，只作为探针存在，未被外部布线触及 |

**这不构成开路**：每个宏内部是连通的，且每个宏都至少有一个引脚被 `pwm_out` 真正接触。

宏内部连通性（MEASURED，宏局部坐标，含 via 跨层）：

| 宏 | 金属/通孔形状 | 连通分量 | 引脚所属分量 |
|---|---|---|---|
| research_via1 | 6 金属 + 1 via1 | 2（met1 顶层 bar 单独一块） | **两个引脚都在分量 0** |
| research_via2 | 5 金属 + 1 via2 | **1** | 两个引脚都在分量 0 |
| research_branch | 10 金属 + 3 via1 | **1** | 四个引脚都在分量 0 |

`research_via1` 的 2 个分量中，孤立的那一块是 `(0.930,6.730)-(9.070,6.870)` 的 met1 顶栏；
两个声明引脚都在主分量里，因此不影响。

### 2.3 三个宏的层号 / Via 类型 / 跨层图（MEASURED）

| 宏 | 层清单（layer/datatype: 数量） | 跨层方式 |
|---|---|---|
| research_via1 | (68/20):4, (68/44):1, (69/20):2, (235/4):1 | **via1** 在 (5.925,3.925)-(6.075,4.075)，位于 li1 pad ∩ met1 pad 内 |
| research_via2 | (69/20):3, (69/44):1, (70/20):2, (235/4):1 | **via2** 在 (5.900,4.900)-(6.100,5.100)，位于 met1 pad ∩ met2 pad 内 |
| research_branch | (68/20):4, (68/44):3, (69/20):6, (235/4):1 | **三个 via1** 各在 li1/met1 的 0.340 µm pad 内 |

sky130 层号：68=met1, 69=met2, 70=met3；`/20` = drawing，`/44` = via-cut，`235/4` = prBoundary。

> **`[待交叉核查]`** D-Agent 正在核对"li1 pad(layer 68) 在 Magic 里被映射为 met1"这一点
> 与纯 met 视角的差异。若 li1 与 met1 是不同层，则 `research_via1` 的主分量在
> met-only 视角下可能再分裂，需要重新评估。目前实测的精确多边形求交是把
> 68/20 当作同一层处理的。

---

## 3. Magic 提取网络对照

### 3.1 本轮 Magic 到底用了什么视图（MEASURED，决定性）

`64-magic-spiceextraction/_env.tcl`：

```
52: set ::env(MAGIC_DEF_LABELS) 0
63: set ::env(MAGIC_EXT_USE_GDS) 0        <-- 不用 GDS
64: set ::env(MAGIC_EXT_UNIQUE) all
66: set ::env(MAGIC_EXT_ABSTRACT) 0       <-- 不启用 abstract
```

`magic-spiceextraction.log`：

- `> lef read` 出现 **10 次**：技术 LEF → sky130_fd_sc_hd.lef → sky130_ef_sc_hd.lef →
  struct_E / A / B / C1 / C3 / C4 / D 的 LEF（顺序见日志 20/50/54/58/62/66/70/74/78/82 行）
- `> gds read` 出现 **0 次**  ← **Magic 在整个提取会话中从未读取任何 GDS**
- `> def read ...53-odb-cellfrequencytables/...def -noblockage`（日志 86 行）

对应 `librelane/scripts/magic/extract_spice.tcl:27-36`：

```tcl
if { $::env(MAGIC_EXT_USE_GDS) } {
    gds read $::env(CURRENT_GDS)
} else {
    read_tech_lef
    read_pdk_lef
    read_macro_lef
    read_extra_lef
    read_pad_lef
    read_def
}
```

**→ 走的是 `else` 分支。Magic 数据库里三个 research 宏的几何 100% 来自 LEF 文件。**

`read_macro_gds` / `read_macro_gds_blackbox`（`common/read.tcl:73-104`）**没有被调用**——
日志里既没有 `> set GDS_FILE of ...` 也没有 `LEFview` 字样。

### 3.2 为什么只有这 3 个宏出问题（MEASURED，关键的对照实验）

| 宏 | LEF 里 PIN 数 | ORIGIN | 是否出现在 badnets |
|---|---|---|---|
| **struct_A** (research_via1) | **1** | 0.930 1.930 | **是** |
| **struct_B** (research_via2) | **1** | 0.930 1.930 | **是** |
| **struct_C1** (research_branch) | **1** | 0.930 4.830 | **是** |
| struct_E (research_fiducial) | 0 | 3.000 3.000 | 否 |
| struct_C3 (research_near) | 0 | 0.930 0.930 | 否 |
| struct_C4 (research_cross) | 0 | 0.930 0.930 | 否 |
| struct_D (research_dense) | 0 | 0.500 0.850 | 否 |

**7 个宏全部有非零 `ORIGIN`，且全部等于各自 GDS bbox 左下角（7/7 实测吻合）。**
但只有声明了 `PIN` 的 3 个宏产生了 LVS 错误——另外 4 个只有 `OBS`，没有引脚参与网表比对，
所以即使位置算错也无从体现。

**这是一个天然对照实验：错的不是 ORIGIN 本身，而是「ORIGIN + PIN」这个组合。**

### 3.3 LEF 内容（MEASURED，`struct_A.lef` 全文要点）

```
MACRO research_via1
  CLASS BLOCK ;
  ORIGIN 0.930 1.930 ;
  SIZE 8.140 BY 4.940 ;
  SYMMETRY X Y ;
  PIN net
    DIRECTION INOUT ;
    USE SIGNAL ;
    PORT
      LAYER met1 ;  RECT 0.000 0.000 0.140 0.140 ;
      LAYER met2 ;  RECT 8.000 2.000 8.140 2.140 ;
    END
  END net
  OBS ... END
END research_via1
```

三个宏的 LEF 结构一致：**都有 `CLASS BLOCK`、`ORIGIN`、`SIZE`、`SYMMETRY X Y`，
`PIN net / DIRECTION INOUT / USE SIGNAL`，都带有 `OBS`。
三个都**没有 `FOREIGN` 语句**。**

`gen_lef.py:349` 把 ORIGIN 写成 `bbox[0], bbox[1]`（GDS bbox 左下角），
`gen_lef.py:401` 注释 `ox, oy = bb.left, bb.bottom  # dbu, macro origin`。

### 3.4 三个宏在两侧网表中的实例与端口（MEASURED）

| 项 | 版图侧（Magic 抽出 SPICE） | 原理图侧（OpenROAD `.nl.v`） |
|---|---|---|
| 子电路定义 | `.subckt research_via1 net`（175-176 行） | 由 LEF 自动生成 |
| 实例 | `Xu_rs_via1 u_rs_via1/net research_via1` | `research_via1 u_rs_via1 (.net(pwm_out));` |
| 该节点出现次数 | **1**（只有它自己） | — |
| 结论 | 悬空 | 接 `pwm_out` |

> **一个必须避免的误判**：单引脚宏的引脚节点在 SPICE 里出现 1 次，
> **本身不等于开路**。若该节点同时被外部顶层网引用，SMICE 里应出现 ≥2 次。
> 因此"出现 1 次"确实说明它在版图网表里是孤立的——但**这只说明 Magic 视角下是孤立的**，
> 不代表 GDS 物理上孤立（§2 已证明 GDS 物理上连通）。
> 二者的差异正是本文要解释的对象。

---

## 4. R3 顶层端口匹配结果（`uio_out[7]` / `uio_oe[2]`）

### 4.1 两者都由 conb_1 的 `.LO` 驱动（MEASURED，`final/nl/tt_um_jiahao_plus_counter.nl.v`）

```
19448:  sky130_fd_sc_hd__conb_1 tt_um_jiahao_plus_counter     (.LO(net));
19459:  sky130_fd_sc_hd__conb_1 tt_um_jiahao_plus_counter_40  (.LO(net40));
19467:  assign uio_oe[2]  = net;
19478:  assign uio_out[7] = net40;
```

两者都是 `sky130_fd_sc_hd__conb_1` 的 **`.LO`** 输出——即**恒 0**，电学完全等价。

### 4.2 常量网络电学等价成立，但 netgen 仍无法完成顶层 PIN 匹配

**成立。** 理由：两个端口各自接到一个只驱动恒 0 的 tie cell，二者驱动能力、电平、
延迟完全相同。交换它们不改变任何逻辑功能。

**为什么 netgen 仍然报不匹配**（DERIVED，依据 rpt 原文）：

1. netgen 的顶层匹配是**按端口名逐一比对**的。`lvs.netgen.rpt:1132/1143`
   明确列出 `uio_out[7] | uio_oe[2] **Mismatch**` 与 `uio_oe[2] | uio_out[7] **Mismatch**`。
2. 它自己的提示是 `Port matching may fail to disambiguate symmetries.`
   —— 这是 netgen **明确声明**其端口匹配算法在遇到对称等价网络时可能失败。
3. 由于这两个端口在拓扑上完全对称（都连到同型的 tie cell），netgen 无法决定
   哪条网对应哪个端口名，于是放弃并报 mismatch。

> **重要边界**：这**不是**可以"豁免"的错误，也**不允许**通过交换顶层 PIN 名或改动
> IO 功能来绕过。它只是在电学上无害。是否接受，必须由项目决定，并有明确记录。

### 4.3 这门问题与 §2/§3 的悬空网络是两个独立问题

| | 悬空 `u_rs_*/net` | `uio_out[7]` ↔ `uio_oe[2]` |
|---|---|---|
| 性质 | 版图侧三个宏引脚孤立 | 两个等价常量端口名配对歧义 |
| 根因 | Magic 的 ORIGIN 坐标（§5） | tie cell 拓扑对称 |
| 是否影响功能 | 否（宏是无源探针） | 否（两者恒 0） |
| 修好前者能否消掉后者 | — | **不能**，需独立处理 |

> `[待交叉核查]` C-Agent 正在复核 RTL / 综合网表 / DEF / 抽取 SPICE 四处的连接，
> 以及是否确实两者同为 `.LO`。若发现任何一处不是恒 0，本节的"电学无害"结论必须推翻。

---

## 5. 根因与证据等级

### 5.1 主结论

> **`STRONGLY_SUPPORTED_HYPOTHESIS`：Magic 在 LEF-only 路径下把 `ORIGIN` 反向应用，
> 使三个宏的 `PIN net` 落在 `placement − ORIGIN + RECT`，而正确位置是
> `placement + ORIGIN + RECT`。**

支持它的证据（全部 MEASURED，且相互独立）：

| # | 证据 | 说明 |
|---|---|---|
| E1 | LEF_rect+ORIGIN 命中宏自身金属 8/8，其余两模型 0/8 | LEF 与 GDS 自洽于 G 模型 |
| E2 | `.ext` 偏差 = 2×ORIGIN，三个宏吻合到 0.001 µm | 差异量恰好是 ORIGIN 的两倍，唯一自洽解释是符号反了 |
| E3 | `pwm_out` 布线终点落在 G 位；M 位 8/8 无任何顶层金属 | OpenROAD 与最终 GDS 都用 G |
| E4 | 7 个宏都有非零 ORIGIN，只有 3 个有 PIN 的出错 | 天然对照：问题是 ORIGIN×PIN 的组合 |
| E5 | 日志中 `gds read` = 0 次 | Magic 无任何机会用 GDS 纠正 LEF 的位置 |
| E6 | 2×ORIGIN 的偏移方向使引脚落向**单元左下外方** | 若 Magic 正确应用 ORIGIN，引脚应在单元内部 |

### 5.2 为什么还不能升级为"确证的 Magic Bug"

缺三样正面证据：

1. **Magic 源码中 `lef read` 对 `ORIGIN` 的处理**——本机是否有 Magic 源码尚未确认；
2. **LEF 5.8 规范对 `ORIGIN` 的精确定义文本**——需要规范原文，不能凭记忆；
3. **一个最小复现**：单宏 + 单引脚 + 非零 ORIGIN，观察 `.ext` 是否稳定偏移 2×ORIGIN。
   （本轮不允许运行新工具配置，故未做。）

`[待交叉核查]` D-Agent 正在做第 1、2 两项；A-Agent 正在核对 `read.tcl` 的
`read_macro_gds_blackbox` 为何未被调用。

### 5.3 一个必须记录的反直觉点

`research_fiducial` 的 GDS 在 (3.000,3.000)-(7.000,7.000)，ORIGIN 也是 (3.000,3.000)。
若 Magic 真的反向应用 ORIGIN，它会把该宏整体移到 (−3,−3) 附近——但**这不影响 LVS**，
因为该宏没有引脚，不参与网表。所以"另外 4 个宏没有报错"**不能**被用作
"Magic 处理 ORIGIN 正确"的证据。这是一个容易犯的推理错误。

---

## 6. 最小修复候选与影响面

> **本轮不实施任何修改。** 以下仅为候选分析，供下一次授权决策。

### 6.1 首选（最小、改动面最窄）：在 LEF 生成器里同时写 `FOREIGN`

**做法**：`gen_lef.py` 在每个宏的 LEF 里，`ORIGIN` 之后追加一条

```
FOREIGN <macro_name> <bbox_left_um> <bbox_bottom_um> ;
```

或把 `ORIGIN` 改为 `0 0` 并同步调整 `PIN`/`OBS` 的坐标基准。

**为什么可能需要 `FOREIGN`**：按 LEF 语义，`ORIGIN` 声明的是"设计坐标原点在这个宏的
哪个位置"，它需要配合 `FOREIGN` 才能确定 `MACRO` 内部坐标的相对关系。
这三个 LEF **只有 `ORIGIN` 没有 `FOREIGN`** —— 这是一个可能让不同工具产生分歧的
不完整声明。`[待交叉核查]` D-Agent 正在核对规范文本。

**影响面预测**：

| 已通过项 | 是否受影响 | 理由 |
|---|---|---|
| Magic DRC（669→0） | **不受影响** | LEF 不参与 DRC，GDS 不变 |
| Pin Access | **可能受影响** | OpenROAD 用 LEF 端口做 pin access；若端口坐标基准改变，需重跑 |
| Detailed Routing | **可能受影响** | 同上，布线终点会移动到新位置 |
| `design__rows` / 剪枝 | 不受影响 | 与宏 LEF 无关 |
| 面积（die 75602.5 / core 72564.6） | 不受影响 | 宏放置是 FIXED，尺寸不变 |

**风险**：改动 LEF 会连锁影响 pin access 与 routing，而这两项在第四轮**已经通过**。
这是本方案最大的代价。

### 6.2 备选一（不改 LEF，只让 Magic 看到真实 GDS）

**做法**：让 SpiceExtraction 走 GDS 分支，即 `MAGIC_EXT_USE_GDS = 1`。

**现状**：`_env.tcl:63` 为 `0`；这是 Tiny Tapeout 的默认，非本项目设置。
要改必须在 `src/config.json` 里加 `"MAGIC_EXT_USE_GDS": 1`。

**影响面**：

| 已通过项 | 是否受影响 |
|---|---|
| Magic DRC | 不受影响（DRC 是独立步骤） |
| Pin Access / Routing | **不受影响**（OpenROAD 不读这个变量） |
| LVS | 理论上直接消除本类错误（Magic 有真实几何） |
| 新增风险 | Magic 改为读 GDS 后，**整个设计**的提取路径都变了，可能引入全新的 LVS 差异（std cell 也不再走 LEF） |

**风险**：改动的是**全局提取路径**，不是只影响 3 个宏。第四轮的 44→6 进步是在
LEF 路径下取得的，切到 GDS 路径等于换了一条验证链。
而且**变更了验证开关**，这一点用户本轮明确禁止（本轮只读，下一轮需单独授权）。

### 6.3 备选二（最保守，不改任何设计）：记录为已知可接受差异

承认这 6 个错误，在项目文档中登记为"无源探针宏的 LEF 抽象端口在 Magic LEF-only
提取下不可见"，并明确其不影响任何功能。

**代价**：CI 永远红。Tiny Tapeout 的 `ERROR_ON_LVS_ERROR` 默认 True，
不会因为项目声明而放行。

### 6.4 推荐顺序与理由

1. **首选 6.1 的 `FOREIGN` 变体** —— 如果 D-Agent 确认规范要求 `FOREIGN`，
   这是"补齐一个缺失声明"而不是"改设计"，改动最小、语义最正确。
   但仍需重跑 pin access / routing 验证。
2. **其次 6.1 的 `ORIGIN 0 0` 变体** —— 把所有 `PIN`/`OBS` 坐标整体平移 `−ORIGIN`，
   使 `ORIGIN` 为 0。这样任何工具无论怎么理解 `ORIGIN` 都不会错。
   代价是 LEF 与 GDS 的坐标基准不再一致，需要重新校对 `OBS`。
3. **6.2 需单独授权**，且必须认识到它改变的是全局提取路径。
4. **6.3 不可作为通过 CI 的手段**，只能作为文档记录。

### 6.5 明确回答"是否需要改 GDS 几何"

**不需要。** 理由是本文 §2 已证明：最终 GDS 的三个宏与 `pwm_out` 物理连通、
宏内部连通、DRC 为 0、路由为 0 错误。**改动 GDS 会引入新的 DRC 风险而收益为零。**

---

## 7. 五轮之前必须避免重复的错误假设

按危害排序，每条都附上它错在哪、以及本轮的实测反驳：

| # | 错误假设 | 为什么错 | 实测反驳 |
|---|---|---|---|
| 1 | 「`deferred` 错误不致命，所以 CI 失败与 LVS 无关」 | `deferred` 只是"延迟到末尾才报错"，仍会 exit 2 → Build GDS 失败 | 第四轮：DRC 已归零，仅 6 个 LVS 就让 CI 红 |
| 2 | 「单个宏只出现一个 PIN，所以是开路」 | 单引脚宏的节点天然只出现 1 次；必须看它是否被外部引用 | §2 已证 GDS 物理连通，是 Magic 视图孤立 |
| 3 | 「另外 4 个宏没报错，所以 Magic 的 ORIGIN 处理是对的」 | 那 4 个宏没有 `PIN`，不参与网表比对 | §3.2 的 7 宏对照表 |
| 4 | 「bbox 重叠就算连通」 | 顶层 met1 最多 49 个顶点，bbox 会覆盖凹陷区造成假连通 | 本报告全程用真实多边形求交 |
| 5 | 「LEF ORIGIN 写错了，应该改 GDS」 | ORIGIN = bbox 左下角是**正确**的 LEF 语义，7/7 自洽 | §2.1 链一 8/8 命中 |
| 6 | 「把 `uio_out[7]`/`uio_oe[2]` 的名字对调就能通过」 | 那会改变 IO 功能定义，且掩盖真实问题 | §4 二者均为恒 0，但交换端口名是禁止的手段 |
| 7 | 「artifact 在本机拿不到」 | `nightly.link` 可匿名取得，SHA-256 与 GitHub digest 一致 | 第四轮分析已更正 |

---

## 8. 未决事项与仍需的证据

| # | 未决事项 | 需要的证据 | 状态 |
|---|---|---|---|
| U1 | Magic `lef read` 对 `ORIGIN` 的确切处理 | Magic 源码或最小复现 | `[待交叉核查]` D-Agent |
| U2 | LEF 5.8 规范对 `ORIGIN` / `FOREIGN` 的原文定义 | 规范文本 | `[待交叉核查]` D-Agent |
| U3 | li1 与 met1 在 Magic 中是否同层 | Magic tech 文件 `sky130A.tech` | `[待交叉核查]` A-Agent |
| U4 | `read_macro_gds_blackbox` 为何未被调用 | `MAGIC_EXT_USE_GDS=0` 时的调用图 | `[待交叉核查]` A-Agent |
| U5 | R3 两个端口在 RTL 层是否真的都是常量 | RTL 源 | `[待交叉核查]` C-Agent |
| U6 | 修复 LEF 后 pin access / routing 的具体变化 | 需实际重跑（本轮禁止） | `UNVERIFIED` |

---

## 9. 本轮边界遵守

| 约束 | 执行情况 |
|---|---|
| 只读分析 | ✅ 仅读取 artifact 与本机文件；写入仅限 `C:\tmp\p6` |
| 不修改 `src/`、`macros/`、GDS/LEF、`info.yaml`、`.github/` | ✅ 未修改（见 §10 校验） |
| 不改变任何验证开关 | ✅ `MAGIC_*`、`LVS_*` 全部只读引用，未改 |
| 不 Commit / Push / 触发第五轮 CI | ✅ 未执行任何 git 写操作 |
| 不修改 V1 | ✅ 未触碰 |
| 不强行选一个根因 | ✅ 主结论标为 `STRONGLY_SUPPORTED_HYPOTHESIS`，并列出 U1-U6 未决项 |

---

## 10. 待终版补充

- [ ] 四个调查 Agent 的结果并入 §3（Magic 路径）、§4（R3）、§5（ORIGIN 约定）
- [ ] 冲突时**不投票**：逐条指出冲突并追查原始坐标/源码
- [ ] §2.3 的 li1/met1 同层假设复核
- [ ] 最小复现的可行性评估（是否可在只读约束下完成）
- [ ] 终版确认 §6.1 与 §6.2 的影响面预测
