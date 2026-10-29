# P5 CLOSEOUT B — R1 / R2 / R3 因果隔离

**状态：** 证据已收集完毕。
**本轮约束（全部遵守）：** 不修改正式 `src/config.json`；不 Commit；不 Push；不触发第四轮 CI；不修改 V1；不关闭任何物理验证。

本文所有结论都带标签：

| 标签 | 含义 |
|---|---|
| **MEASURED** | 从本轮保存的第三轮 CI 产物（`.rpt` / DEF / GDS / SPICE / pnl.v）直接读出或计算得出，脚本可复现 |
| **DERIVED** | 由 MEASURED 数值经明确算式推导，算式写在正文里 |
| **PREDICTED** | 尚未在任何真实运行中被观察到；仅为本轮静态推演 |
| **UNVERIFIED** | 本地无法验证（无 Magic / Netgen / LibreLane 源码，无网络） |

---

## 0. 权威指标口径（沿用上一轮认可值，本轮独立复算）

```
design__lvs_error__count = 44
  = device_difference  21
  + net_difference     16
  + property_fail       0
  + unmatched_device    1
  + unmatched_net       1
  + unmatched_pin       5
```

**MEASURED**：本轮用 `tools/v2_ci_diagnostics/b_net_count.py` 直接从两个网表数节点：
- C1（Magic 从最终版图提取的 SPICE）：**18536 个实例 / 405 个不同节点**，与 netgen 打印的 `Number of nets: 405` 精确相等。
- `.rpt` 中带 `(no matching net)` 的行恰好 **16** 行，与 `net_difference = 16` 精确相等。

这确认了：`.rpt` 的明细行数与 LibreLane 指标**不是同一套计数**，但两者可以通过 netgen 自己的汇总行对上。上一轮的更正成立，本轮不再用明细行数冒充指标。

---

## 1. R2 — `device_difference = 21`

### 1.1 结论先行

**R2 的全部 21 都由「提取网表中 decap_3 / fill_2 的 VPB 引脚落在悬空网络上」造成，与任何短路无关，也与参考网表与版图的单元数量差异无关。**

### 1.2 先排除一个错误解释

`decap_3 (16182->14) | decap_3 (16182->1)` 这一行容易被读成「版图比参考多 13 个 decap」。**这个读法是错的。**

**MEASURED**（`tools/v2_ci_diagnostics/b_reduction_proof.py` 第 1 步，逐类数实例）：

| 单元类 | C1 提取 SPICE | C2 参考 pnl.v | 是否相等 |
|---|---:|---:|---|
| `sky130_fd_sc_hd__decap_3` | 16182 | 16182 | 相等 |
| `sky130_fd_sc_hd__fill_2` | 138 | 138 | 相等 |
| `sky130_fd_sc_hd__fill_1` | 856 | 856 | 相等 |
| `sky130_fd_sc_hd__tapvpwrvgnd_1` | 997 | 997 | 相等 |
| `sky130_fd_sc_hd__conb_1` | 12 | 12 | 相等 |

两侧的单元population完全一致。所以 `16182->14` 里的 `16182` 是**原始实例数**，`->14` 是 netgen 做串并联归并（series/parallel reduction）后剩下的**器件组数**。参考侧同样的 16182 个实例归并成 **1 个**器件组。

`21` 因此不是「版图多了 21 个单元」，而是「C1 把这些原本可归并的单元切成了更多组」。

### 1.3 21 的闭合分解

**MEASURED + DERIVED**（`tools/v2_ci_diagnostics/b_final_decomp.py`、`tools/v2_ci_diagnostics/b_reduction_proof.py`）：

```
device_difference = 21
  = 13  (VPB 悬空的 decap_3 器件组)
  +  8  (VPB 悬空的 fill_2  器件组)
```

三条互相独立的佐证：

1. **组数闭合**：13 个悬空 + 1 个正常归并组 = **14**，netgen 报 `->14`，相等。
   8 个悬空 + 1 个正常归并组 = **9**，netgen 报 `->9`，相等。（`b_reduction_proof.py` STEP 3，两个 `MATCH: True`）
2. **扇出闭合**：`decap_3/VGND = 14`（C1）对 `1`（C2）；`decap_3/VPWR = 14` 对 `1`；`fill_2/VGND = 9` 对 `1`；`fill_2/VPWR = 9` 对 `1`。器件组数和电源引脚扇出严格一致。
3. **实例差闭合**：上一轮记录 `decap_3 +13`、`fill_2 +8`，和 1、2 完全一致。

### 1.4 为什么 VPB 会悬空

**MEASURED**：13 个 `FILLER_*/VPB` 网络全部出现在 netgen 的 NET mismatch 段，C2 侧一律 `(no matching net)`。其中 12 个只承载 decap/fill 的 VPB 端口，1 个（`FILLER_53_9/VPB`）同时承载 `decap_3/VPB` 和 `fill_2/VPB`。

> 注意计数口径：13 是**网络数**，21 是**端口/器件组数**。因为 `FILLER_53_9/VPB` 一个网络上有 2 个端口，所以 13 个网络对应 13 个 decap 端口 + 8 个 fill 端口 = 21 个端口。上一轮的「13 + 8」是端口口径，本轮明确区分，不再混用。

### 1.5 R2 对 Tap / Row 的敏感性

**MEASURED**（`tools/v2_ci_diagnostics/b_final_decomp.py`）：把每个 FILLER 按 `52-openroad-fillinsertion` 的坐标落到 `18-openroad-cutrows` 的 row segment 上，按 `w < 25.76` 判定是否落在 PRUNABLE 段：

```
13 / 13 个悬空 VPB 单元位于 PRUNABLE 段
 0 / 13 个悬空 VPB 单元位于 KEPT 段
```

明细（x 统一为 6.900，全部位于行首第 15 列附近）：

| 网络 | 单元类 | x | y | 段宽 | 判定 |
|---|---|---:|---:|---:|---|
| FILLER_51_9/VPB | decap_3 | 6.900 | 141.440 | 10.58 | PRUNABLE |
| FILLER_53_9/VPB | decap_3 | 6.900 | 146.880 | 10.58 | PRUNABLE |
| FILLER_55_9/VPB | decap_3 | 6.900 | 152.320 | 10.58 | PRUNABLE |
| FILLER_57_9/VPB | decap_3 | 6.900 | 157.760 | 10.58 | PRUNABLE |
| FILLER_59_9/VPB | decap_3 | 6.900 | 163.200 | 10.58 | PRUNABLE |
| FILLER_67_189/VPB | fill_2 | 89.700 | 184.960 | 7.82 | PRUNABLE |
| FILLER_69_189/VPB | fill_2 | 89.700 | 190.400 | 7.82 | PRUNABLE |
| FILLER_70_189/VPB | fill_2 | 89.700 | 193.120 | 7.82 | PRUNABLE |
| FILLER_73_9/VPB | decap_3 | 6.900 | 201.280 | 11.04 | PRUNABLE |
| FILLER_75_9/VPB | decap_3 | 6.900 | 206.720 | 11.04 | PRUNABLE |
| FILLER_77_9/VPB | decap_3 | 6.900 | 212.160 | 11.04 | PRUNABLE |
| FILLER_79_9/VPB | decap_3 | 6.900 | 217.600 | 11.04 | PRUNABLE |
| FILLER_80_9/VPB | decap_3 | 6.900 | 220.320 | 11.04 | PRUNABLE |

**所以 R2 确实对 tap/row 改造敏感**，这一点成立。

### 1.6 但必须明确区分「区域被删掉」与「根因被修掉」

这是本轮最重要的一条方法论约束，我上一轮已在 `P5_CLOSEOUT_A_PRUNE.md` §4 用 3 个 `conb_1` 反例说明过。对 R2 同样成立：

- **MEASURED**：13/13 悬空 VPB 单元都在将被删除的段里。
- **PREDICTED**：删掉这些段后，这 13 个网络不再存在，因此那 21 个器件组差异**会**消失。

但这是「把出问题的单元整体搬走」，不是「让 VPB 正确连上电源」。若 OPT-A 只做后者不做前者，同样的问题会在别的窄段继续出现。**这条因果链只能标记为 PREDICTED，本轮不得写成已修复。**

### 1.7 R2 涉及功能单元，不只是 dummy —— 但它不进 `device_difference`

**MEASURED**：`FILLER_79_9/VPB` 和 `FILLER_80_9/VPB` 上除 decap 外还挂着 **`conb_1/VPB`** 端口。`conb_1` 是驱动 `uio_oe[5..7]` 的常量单元，不是 dummy。

但这里有一个**必须精确区分**的地方，它决定 OPT-A 的损失该怎么算：

```
sky130_fd_sc_hd__conb_1 (12)   |   sky130_fd_sc_hd__conb_1 (12)     <- 无 -> 无 **Mismatch**
但：  conb_1/VPB = 9          |   conb_1/VPB = 12
```

**MEASURED**（`tools/v2_ci_diagnostics/b_conb_vpb.py`）：

| 实例 | 输出网络 | VPB 节点 | 所在段 |
|---|---|---|---|
| `Xtt_um_jiahao_plus_counter_32` | `uio_oe[5]` | `FILLER_80_9/VPB` | PRUNABLE w=11.04 |
| `Xtt_um_jiahao_plus_counter_33` | `uio_oe[6]` | `FILLER_80_9/VPB` | PRUNABLE w=11.04 |
| `Xtt_um_jiahao_plus_counter_34` | `uio_oe[7]` | `FILLER_79_9/VPB` | PRUNABLE w=11.04 |

（其余 9 个 `conb_1` 的 VPB 都在 `VPWR` 上。）

**为什么这 3 个 VPB 悬空却不产生 `device_difference`：** 每个 `conb_1` 驱动一个**互不相同**的输出网络，所以这 12 个器件在两侧都无法归并；净表中两侧都是 12 个器件，`|diff| = 0`。悬空 VPB 在这里只改变**内部连接**，不改变**器件组数**。

**结论：** `conb_1` 的 VPB 悬空是一个 **MEASURED 的真实异常**，但它**既不进 `device_difference` 也不额外进 `net_difference`**（那 2 个悬空网络已计入 §1.4 的 13 个 FILLER 网络中）。它是第三个独立问题，本轮不解决，但要如实记录。

---

## 2. R1 — `pwm_out` 被切成 4 个网络

### 2.1 结论先行

**R1 的根因是 Magic 的 LEF 抽象视图没有使用 ORIGIN 偏移，导致宏端口几何落在空白处；由此产生的 3 个单引脚残段加上 `_214_/X` 一个残段，构成 `net_difference` 中的 4。R1 是「提取视角的端口位置错误」，不是开路，不是短路，不是缺标签。**

### 2.2 DEF 侧只有 1 个网络

**MEASURED**：

```
final/def/tt_um_jiahao_plus_counter.def:
    - pwm_out ( u_rs_via2 net ) ( u_rs_via1 net ) ( u_rs_branch net )
              ( _218_ B1 ) ( _214_ X ) + USE SIGNAL
```

五个引脚、一个网络。`53-odb-cellfrequencytables` 的 DEF 与最终 DEF 的该条记录逐字节相同（上一轮已验），所以**不存在「读了过期 DEF」这一解释**。

### 2.3 Magic 提取出 4 个网络，其中 3 个是单引脚残段

**MEASURED**（`.rpt` NET mismatch 段）：

```
Net: _214_/X          | (no matching net)     pins: a22o_2/B1, a22o_2/X
Net: u_rs_branch/net  | (no matching net)     pins: research_branch/net
Net: u_rs_via1/net    | (no matching net)     pins: research_via1/net
Net: u_rs_via2/net    | (no matching net)     pins: research_via2/net
```

后三个**各自只有 1 个引脚**。单引脚网络在提取语义里是「这个引脚所在的几何图形没有连到任何别的东西」——是**孤岛残段**，不是悬空长线，也不是两个网络被短接。

### 2.4 三个坐标框架，逐一实测

对每个宏，把 LEF 的 PORT 矩形放到三个候选框架下，看最终 GDS 在该位置有没有铜：

| 框架 | 定义 |
|---|---|
| A | `abs = place + LEF_RECT`（忽略 ORIGIN） |
| B | `abs = place + ORIGIN + LEF_RECT`（应用 ORIGIN） |
| C | `abs = place − ORIGIN + LEF_RECT`（反向 ORIGIN） |

**MEASURED**（`tools/v2_ci_diagnostics/b_r1_origin_scope.py`，全部 8 个端口矩形）：

| 宏 | 端口数 | 框架 A 命中铜面积 | 框架 B 命中铜面积 | 框架 C 命中铜面积 |
|---|---:|---|---|---|
| research_branch | 4 | 全部 **0.0000 µm²** | 2.2166 / 0.3392 / 0.4092 / 0.6786 µm² | 全部 **0.0000 µm²** |
| research_via1 | 2 | 全部 **0.0000 µm²** | 1.0392 / 0.6058 µm² | 全部 **0.0000 µm²** |
| research_via2 | 2 | 全部 **0.0000 µm²** | 1.6988 / 1.8198 µm² | 全部 **0.0000 µm²** |

**只有框架 B 在每一处都落在真实铜皮上；A 和 C 在全部 8 处都是零。** 这是 8/8 的二值判别，不是拟合。

### 2.5 互补等式：`GDS_local = LEF_RECT + ORIGIN`

**MEASURED**（`tools/v2_ci_diagnostics/b_r1_frame.py` 第 4 节）：把每个 LEF PORT 矩形加上 ORIGIN 作为 cell-local 探针，在宏单元自身的 GDS 里测覆盖率：

```
research_branch  met1 (0.930,4.930)-(1.070,5.070)  100.0%
                 met2 (1.930,6.930)-(2.070,7.070)  100.0%
                 met2 (5.930,7.430)-(6.070,7.570)  100.0%
                 met2 (9.930,7.930)-(10.070,8.070) 100.0%
research_via1    met1 (0.930,1.930)-(1.070,2.070)  100.0%
                 met2 (8.930,3.930)-(9.070,4.070)  100.0%
research_via2    met2 (0.930,1.930)-(1.070,2.070)  100.0%
                 met3 (10.850,4.850)-(11.150,5.150) 100.0%
```

**8/8 精确 100.0%**。也就是说 LEF 的 PORT 矩形**是用宏内部坐标写的，而这套坐标已经把 ORIGIN 减掉了**；还原时必须加回来。这不是「ORIGIN 有偏差」，而是「LEF 的 PORT 坐标系原点 = 硬宏内部原点 − ORIGIN」，严格成立。

### 2.6 路由器用的是框架 B

**MEASURED**（`tools/v2_ci_diagnostics/b_r1_frame.py` 第 3 节）：DEF `pwm_out` 有 21 段布线、7 个悬空端点。把悬空端点与各框架的端口矩形比对：

```
u_rs_branch  met1 端点 (80.270,213.000) 落在 B 框 x[80.250..80.390] y[212.930..213.070]
u_rs_branch  met2 端点 (89.320,216.000) 落在 B 框 x[89.250..89.390] y[215.930..216.070]
u_rs_via1    met2 端点 (42.550,212.000) 落在 B 框 x[42.430..42.570] y[211.930..212.070]
u_rs_via2    met2 端点 (65.000,210.000) 落在 B 框 x[64.930..65.070] y[209.930..210.070]
u_rs_via2    met3 端点 (75.000,213.000) 落在 B 框 x[74.850..75.150] y[212.850..213.150]
```

**5/5 全部落在框架 B，A/C 命中 0 个。** 路由器、GDS、LEF 三者一致。

### 2.7 三方一致，Magic 是唯一的例外

| 观察对象 | 使用的框架 | 证据 |
|---|---|---|
| OpenROAD 绕线器 | **B** | 5/5 悬空端点落在 B 框（§2.6） |
| 最终 GDS 几何 | **B** | 8/8 端口处覆盖率 100%（§2.5） |
| Magic 提取结果 | **A** | 4 个网络而非 1 个（§2.3）；A 框下 8/8 端口命中 0 µm²（§2.4） |

**MEASURED**：Magic 读入的就是**带 ORIGIN 的授权 LEF**（`magic-spiceextraction.log` 第 58–85 行，`lef read .../macros/out/struct_C1.lef` 等 7 个）。所以不是「读错了 LEF 文件」，而是 Magic 对这些 LEF 里的 `PORT` 坐标采用了框架 A 解释。

> 关于 Magic 内部为何这样处理：**UNVERIFIED**。本地无 Magic 二进制、无 Magic 源码、无网络，不能读其 LEF reader 实现来确认。§2.4 的 8/8 二值证据只证明**结果等价于框架 A**，不证明内部机制。本报告只主张前者。

### 2.8 `struct_C1` 的 ORIGIN 是合法的，R1 与 ORIGIN 取值无关

> **本节是 2026-10-29 的更正。** 早前版本写「`struct_C1` 的 ORIGIN y=4.830 落在 SIZE 高度
> 3.240 之外，是非法 LEF」，并把「修正 ORIGIN」列为可选修复。**那个判断是错的**，
> 错在把两个不同坐标系的量直接比大小。以下为更正后的结论与依据。

**LEF 5.8 §"MACRO" 的语义（标准依据）：**

| 关键字 | 所在坐标系 | 含义 |
|---|---|---|
| `SIZE w BY h` | **宏局部** | 宏边框的宽高，局部坐标恒为 `[0,w] × [0,h]` |
| `ORIGIN x y` | **父（实例）坐标** | 宏局部原点 `(0,0)` 在父坐标系中的位置 |

`ORIGIN` 与 `SIZE` **没有可比性**——前者是父系的平移量，后者是局部的尺寸。
LEF 也**不要求** `ORIGIN` 落在 `[0,SIZE]` 内；只要布局合法，`ORIGIN` 取任何值都不违规。

**MEASURED（本轮实测，KLayout 0.30.12 读 `macros/out/struct_C1.gds`）：**

```
top cell : research_branch
bbox dbu : (930,4830 ; 11070,8070)
bbox um  : 0.930 4.830 .. 11.070 8.070      size = 10.140 x 3.240
LEF      : ORIGIN 0.930 4.830 ;  SIZE 10.140 BY 3.240
=> ORIGIN == GDS bbox 原点（左右上下四项精确相等）
```

生成器 [macros/gen_lef.py:349](macros/gen_lef.py#L349) 写的是
`'  ORIGIN %.3f %.3f ;' % (bbox[0], bbox[1])`，即 **ORIGIN 恒等于 GDS 边框左下角**，
而 `SIZE` 取自同一个 bbox 的宽高。两者由同一 bbox 导出，结构上不可能冲突。
所以七个宏的 ORIGIN 全部合法，`struct_C1` 不是例外。

**这条更正对 R1 意味着什么：**

- 早前「修正 `struct_C1` ORIGIN 可消掉约 1/4 残段」的建议 **作废**。ORIGIN 不需要改，
  改了也不会有任何效果——三份 LEF 的 ORIGIN 本来就都是 bbox 原点。
- R1 的原因回到 §2.4/§2.7 的**框架不一致**：Magic 建抽象视图时不应用 ORIGIN
  （实测等价于框架 A），而路由器与最终 GDS 都应用（框架 B）。这是解释器的行为差异，
  不是输入文件的取值错误。**所以修 LEF 的数值没有意义。**
- 仍成立的结论：仅改 ORIGIN 不可能修复 R1。

**MEASURED（三个宏各自的 ORIGIN 与 GDS bbox 一致性）：**

```
research_branch  ORIGIN=(0.930,4.830)  SIZE=(10.140,3.240)  = GDS bbox 原点  ✔
research_via1    ORIGIN=(0.930,1.930)  SIZE=( 8.140,4.940)  = GDS bbox 原点  ✔
research_via2    ORIGIN=(0.930,1.930)  SIZE=(10.220,3.265)  = GDS bbox 原点  ✔
```

### 2.9 最终 GDS 是物理连通的

上一轮已用 via-aware BFS 验证：从 `_214_` 的输出出发，经 li1/mcon/met1/via1/met2/via2/met3 逐层扩张，**11 次迭代后可达 30.700 µm² 铜面积，覆盖全部 8 个 research 宏引脚**。

配合 §2.4（每个引脚处确有铜）、§2.6（绕线端点正落在这些铜上），结论是：

> **最终版图里 `pwm_out` 是一条真实连通的网络。R1 是提取视图的端口定位失败，不是制造缺陷。**

这一条必须与「Netgen 左右配对显示」严格区分：netgen 把 `VGND` 配到 `pwm_out`、把 `VPWR` 配到 `VGND`，是**端口匹配失败后的错位排列**，不是任何电气短路。netgen 自己也打印了 `Port matching may fail to disambiguate symmetries.`

---

## 3. R3 — `uio_out[7]` / `uio_oe[2]` 交换

### 3.1 结论先行

**R3 是两个电气同构网络的对称性歧义，属于匹配假象，不是缺陷，也不是短路。**

### 3.2 两侧的驱动与负载

**MEASURED**（`tools/v2_ci_diagnostics/b_r3_and_sensitivity.py`）：

```
C1（提取 SPICE）:
  Xtt_um_jiahao_plus_counter_40  VGND VGND VPWR VPWR tt_um_jiahao_plus_counter/HI
                                 uio_out[7]  sky130_fd_sc_hd__conb_1
  Xtt_um_jiahao_plus_counter     VGND VGND VPWR VPWR tt_um_jiahao_plus_counter/HI
                                 uio_oe[2]   sky130_fd_sc_hd__conb_1

C2（参考 pnl.v）:
  assign uio_out[7] = net40;
  assign uio_oe[2]  = net;
```

两个网络都由**同一类** `conb_1` 常量单元驱动，输出同一个 `HI` 常量，**没有任何其他负载**。两个网络在拓扑上完全同构，netgen 无法区分，交换不影响任何可观测行为。

### 3.3 位置与 tap/row 敏感性

**MEASURED**：

```
R3  conb_1 驱动 uio_out[7]   位于 KEPT 段（w = 51.06）
R3  conb_1 驱动 uio_oe[2]    位于 KEPT 段（w = 51.06）
```

两个单元都在**保留段**，OPT-A 不移动它们。

### 3.4 R3 与 OPT-A 的关系：R3 的驱动单元不受 OPT-A 影响

**MEASURED**（`b_conb_vpb.py`）：驱动 R3 两个网络的两颗 `conb_1`：

| 实例 | 输出 | VPB | 位置 | 段 |
|---|---|---|---|---|
| `Xtt_um_jiahao_plus_counter_40` | `uio_out[7]` | `VPWR`（正常） | (46.000, 193.120) | **kept** |
| `Xtt_um_jiahao_plus_counter` | `uio_oe[2]` | `VPWR`（正常） | (44.620, 193.120) | **kept** |

两个都在保留段，且 VPB 正常接 `VPWR`。

而 OPT-A 会删除的 3 个 `conb_1`（`_32` / `_33` / `_34`）驱动的是 `uio_oe[5..7]`，**与 R3 无关**。

**所以：R3 的驱动网络本身不会因 OPT-A 改变。** 但 §3.2 的对称性歧义取决于 netgen 在这 12 个同构 `conb_1` 网络之间如何配对——`_32`/`_33`/`_34` 被删除后，剩下的 9 个仍然同构，歧义**很可能换一对网络出现**。

**PREDICTED，且不作承诺**：R3 在 OPT-A 后是否仍然表现为 `uio_out[7] ↔ uio_oe[2]` 交换，无法静态判定。上一轮的约束「不能预先认定 R1/R3 一定不受任何上游连接修复影响」在此同样适用——也不能反向承诺它一定会消失。

---

## 4. 三个根因的最小合法修复方向

**这一节只给方向，不落地。** 本轮不修改 `src/config.json`，不改 V1。

### 4.1 R2

问题本质：窄 row segment 里没有 tap，dummy 单元的 VPB 在提取时成为孤立节点。

| 方案 | 内容 | 代价 / 风险 |
|---|---|---|
| **R2-a** | 保留 OPT-A 的 row 修剪（阈值建议 **26.22**，即 `2·O+1`，而非 25.76） | 删除 26 段 / 572 sites / 1.06% 面积；需接受 3 个 `conb_1` 重放。**只搬走问题，不修根因** |
| **R2-b** | 降低 `FP_TAPCELL_DIST` 或强制窄段插 tap | 需验证 magic 提取是否仍会孤立 VPB；可能引入 tap 密度 DRC |
| **R2-c** | 接受 R2 为「已知的提取口径差异」，在 LVS 里显式豁免 decap/fill 的 VPB | **属于关闭检查**，按本课题约束**不允许** |

**建议方向**：R2-a 与 R2-b 组合，且 R2-a 用 26.22。但必须承认这只是 **PREDICTED**。

### 4.2 R1

问题本质：LEF PORT 坐标与 ORIGIN 的约定在 Magic 侧不一致。

| 方案 | 内容 | 代价 / 风险 |
|---|---|---|
| **R1-a** | 重写宏 LEF：把 PORT 矩形**预先加上 ORIGIN**，即写成宏内部绝对坐标 | 需同步重生成全部 7 个宏的 LEF；可能影响 OpenROAD 绕线（当前绕线基于旧约定且是正确的），**必须先做小规模验证** |
| **R1-b** | 在 GDS 流片时把宏单元内容整体平移 +ORIGIN，使 GDS 与 LEF 框架 A 一致 | 会让 GDS 与当前绕线错位，**危险** |
| **R1-c** | 修正 `struct_C1` 的非法 ORIGIN 使 `y ≤ SIZE` | 只解决 3 个残段中的 1 个，**不够** |

**建议方向**：R1-a，但必须先证明 OpenROAD 在新 LEF 下仍把端点放在同一位置（否则会从「提取错位」变成「真实开路」）。这是**高风险改动**，本轮不实施。

> 补充：如果第四轮 CI 的首要目标只是把 `net_difference` 降下来，R1-a 的收益是 4 个网络，但风险远高于 R2-a。**建议第四轮先做 R2，R1 单独一轮验证。**

### 4.3 R3

**不需要修复。** 这是匹配假象。若一定要消除，只能在参考网表里人为打破两个 `conb_1` 网络的对称性（例如插入一个无意义的 buffer），那属于**为通过检查而人为制造电路**，被本轮约束明确禁止。

**建议：接受 R3，在报告中如实记录为「netgen 对称性匹配假象」，而不是记为 PASS 或记为缺陷。**

---

## 5. MAGIC_DEF_LABELS 评估（Task C）

### 5.1 事实

**MEASURED**：`set ::env(MAGIC_DEF_LABELS) 0` 出现在全部 4 个 Magic 阶段：

```
57-magic-streamout
60-magic-writelef
62-magic-drc
64-magic-spiceextraction
```

### 5.2 机制：UNVERIFIED

本地**没有** `librelane`、`magic`、`netgen` 可执行文件，也**没有网络**（`raw.githubusercontent.com` 连接被拒）。因此无法读 LibreLane 3.0.14 里该变量的实现，也无法跑对照实验。

**本轮不修改该变量，不把它写入任何配置。**

### 5.3 必要性：已被证据否定

上一轮的待验证问题是「R1/R3 是否因为缺少合法网络标签而无法匹配」。

本轮证据给出否定答案：

- R1 的 4 个残段来自**端口几何落空**（§2.4：框架 A 下 8/8 端口命中 0 µm²）。即使给 DEF 加上标签，Magic 建抽象视图时端口仍在空白处，**残段照样产生**。
- R3 是两个**完全同构**网络的对称性歧义（§3.2）。标签改变的是名字，不改变同构性，**歧义照样存在**。

所以：

> **MAGIC_DEF_LABELS 对 R1/R3 都不是必要的修复手段。**
> 机制层面保持 **UNVERIFIED**；必要性层面结论为 **不需要**。

并且必须强调本轮约束的原话：**不得把人为标签当成真实电气连通性的替代品。** §2.9 已经用几何证据证明连通性是真的，不需要标签来「补」。

---

## 6. 已验证 / 预测 / 未知 的分界

### 6.1 已验证（MEASURED / DERIVED）

| 编号 | 结论 |
|---|---|
| V1 | `44 = 21 + 16 + 0 + 1 + 1 + 5`，且 `.rpt` 的 `(no matching net)` 行数恰为 16 |
| V2 | C1 提取 SPICE 恰有 405 个不同节点，等于 netgen 的 `Number of nets: 405` |
| V3 | 两侧 `decap_3` / `fill_2` / `fill_1` / `tapvpwrvgnd_1` / `conb_1` 实例数**完全相等** |
| V4 | `device_difference = 21 = 13 + 8`，由组数（14、9）、扇出（14:1、9:1）、实例差（+13、+8）三重闭合 |
| V5 | 13/13 悬空 VPB 单元位于 PRUNABLE 段，0/13 位于 KEPT 段 |
| V6 | 最终 DEF 中 `pwm_out` 是**一个**网络，含 5 个引脚 |
| V7 | Magic 提取出 4 个网络，其中 3 个是**单引脚残段** |
| V8 | 框架 B（应用 ORIGIN）在 **8/8** 端口上命中真实铜；框架 A、C 在 8/8 上命中 0 |
| V9 | `GDS_local = LEF_RECT + ORIGIN` 在 **8/8** 端口上覆盖率精确 100.0% |
| V10 | 路由器 5/5 悬空端点落在框架 B |
| V11 | 最终 GDS 物理连通：via-aware BFS 11 次迭代，30.700 µm²，覆盖全部 8 个宏引脚 |
| V12 | **（已更正）** 七份 LEF 的 `ORIGIN` 全部等于其 GDS bbox 左下角，`struct_C1` 亦然；`ORIGIN` 与 `SIZE` 分属父/局部两个坐标系，不可直接比大小。早前的「`struct_C1` ORIGIN 非法」判断**作废**，见 §2.8 |
| V13 | R3 两个网络由同类 `conb_1` 驱动同一常量、无其他负载，完全同构 |
| V14 | R3 两个驱动单元位于 KEPT 段（w = 51.06），VPB 正常接 `VPWR` |
| V15 | 93 个 enclosure 违规 93/93 落在宏实例 bbox 内（branch 62 / via1 23 / via2 8） |
| V16 | 3 个 `conb_1`（驱动 `uio_oe[5..7]`）的 VPB 悬空，且都位于 PRUNABLE 段；该异常**不进** `device_difference`（两侧均 12 个器件） |

### 6.2 预测（PREDICTED，未在任何真实运行中观察）

| 编号 | 预测 | 依据 | 不做的承诺 |
|---|---|---|---|
| P1 | OPT-A（阈值 25.76）执行后 `device_difference` 从 21 降到 0 | 13/13 单元在删除段内 | **不等于已修复根因** |
| P2 | OPT-A 同时使 `net_difference` 减少 12 | 12 个 FILLER 网络消失 | 4 个 R1 残段不受影响 |
| P3 | OPT-A 后至少 3 个 `conb_1` 需要重放 | `P5_CLOSEOUT_A_PRUNE.md` §4 的反例 | 不计入「零损失」 |
| P4 | ~~仅修 `struct_C1` ORIGIN 可降 `net_difference` ~2~~ **已撤回** | §2.8 更正：ORIGIN 本就合法，无值可改，此预测不成立 | — |
| P5 | 用 26.22 替代 25.76 可获得物理依据 | `2·O+1 = 2×round(13/0.46)+1 = 57 sites` | 26.22 是结构性阈值，非实测最优 |
| P6 | R3 在 OPT-A 后的表现不可预测 | §3.4 | **既不承诺消失，也不承诺保留** |

### 6.3 未知（UNVERIFIED）

| 编号 | 未知项 | 原因 |
|---|---|---|
| U1 | Magic LEF reader 为何采用框架 A | 无 Magic 二进制 / 源码 / 网络 |
| U2 | `MAGIC_DEF_LABELS` 在 LibreLane 3.0.14 内的精确作用 | 同上 |
| U3 | 重写 LEF 后 OpenROAD 是否仍把端点放在原位 | 需真实跑一次 P&R |
| U4 | 26.22 是否能在真实运行中消除 R2 | 需真实跑一次 |
| U5 | 93 个 enclosure 违规是否会阻断流片 | 取决于 Magic DRC 在 TT 流程中的门限 |

---

## 7. 第四轮 CI 候选修改清单（**仅清单，本轮不执行**）

按 **风险从低到高** 排列，建议分轮次而不是一次全上：

| 序 | 修改 | 预期收益 | 风险 | 是否建议进第四轮 |
|---|---|---|---|---|
| 1 | `FP_PRUNE_THRESHOLD` 由未设置改为 **26.22** | R2：`device_difference` 21 → 0（P1）；`net_difference` 16 → 4（P2，仅 R2 部分） | 中：3 个 `conb_1` 重放 | **建议** |
| 2 | ~~修正 `struct_C1` 的 `ORIGIN y`~~ **已撤回：ORIGIN 本就合法，无值可改**（§2.8） | 无 | — | **不做** |
| 3 | 重写 7 个宏 LEF 的 PORT 坐标（R1-a） | R1：4 个残段消失 | **高**：可能改变绕线端点 | **不建议**同轮 |
| 4 | `MAGIC_DEF_LABELS: true` | 无（§5.3 已否定必要性） | 未知 + 违反「不得用人造标签替代真实连通性」 | **不建议** |
| 5 | 关闭 / 豁免任何 LVS 或 DRC 检查 | — | 违反本轮硬约束 | **禁止** |

**关键提醒：** 序号 1 是唯一能显著改善指标的改动，但它是「删除问题区域」而不是「修复根因」。如果第四轮 CI 通过而根因未修，必须在报告中如实说明，**不能把 21 → 0 写成 LVS 根因已解决**。

---

## 8. 复现方式

所有脚本位于 `tools/v2_ci_diagnostics/`，均在仓库根目录以 `wsl -e bash -lc "python3 tools/v2_ci_diagnostics/<script>.py"` 运行：

| 脚本 | 作用 | 关键输出 |
|---|---|---|
| `b_final_decomp.py` | 44 的完整分解、13 个 VPB 的段归属 | `12 + 4 = 16`、`13 + 8 = 21`、`13/13 PRUNABLE` |
| `b_reduction_proof.py` | 器件归并证明 | 两侧实例数相等；`13+1=14`、`8+1=9` 均 `MATCH: True` |
| `b_net_count.py` | 独立节点计数 | C1 = 405 节点；`(no matching net)` = 16 行 |
| `b_r1_frame.py` | 三个工具各用哪个框架 | 路由器 5/5 框架 B；GDS 覆盖率 8/8 = 100% |
| `b_r1_origin_scope.py` | ORIGIN 合法性 + 三框架铜命中 | 框架 B 8/8 有铜；A、C 8/8 为零 |
| `b_r3_and_sensitivity.py` | R3 同构性 + tap/row 敏感性 | `conb_1` 同构；R3 单元在 KEPT 段 |
| `b_conb_vpb.py` | `conb_1` 的 VPB 归属与段位置 | 3 个悬空 VPB 全在 PRUNABLE；R3 的两颗在 kept 且 VPB 正常 |
| `b_macro_shapes.py` | 流片后宏几何完整性 | 14/14、8/8、7/7 形状数一致 |
| `b_enc_attrib.py` | 93 个 enclosure 归属 | ORIGIN 口径下 93/93 在宏内 |

---

## 9. 本轮停止点

本文档完成即停止。以下动作**全部未执行**，等待下一次批准：

- 未修改 `src/config.json`（`FP_PRUNE_THRESHOLD` 仍未设置）
- 未启用 `MAGIC_DEF_LABELS`
- 未 Commit、未 Push、未创建 PR
- 未触发第四轮 CI
- 未修改 V1 黄金版本
- 未关闭或豁免任何物理验证

**下一步需要用户决定的是：第四轮 CI 只上清单序号 1（26.22 阈值，低风险），还是同时上序号 2（修 struct_C1 ORIGIN）。**
