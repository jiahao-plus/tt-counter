# R1 坐标关系链（LEF/DEF 5.8）与「为什么是 VGND/VPWR 而不是只有 research_branch/net」

**状态：R1 本轮不修复，只做诊断。** 用户明确要求：「若无法证明安全修正方法，本轮只保留 R1 的诊断，不强行修改，也不得声称 R1 已解决。」
本文件即该诊断。**R1 未解决。**

数据锚点：Compile `7135c543…`、Run `40726887237`、LibreLane 3.0.14、KLayout 0.30.12。

---

## 1. 用户要求的七个坐标系，逐个定位

| # | 对象 | 数据在哪里 | 本轮实测值（`research_branch`） |
|---|---|---|---|
| 1 | GDS 原始结构坐标 | `macros/out/struct_C1.gds` top cell `research_branch` | bbox `(0.930, 4.830) .. (11.070, 8.070)`，size `10.140 × 3.240` |
| 2 | LEF `ORIGIN` | `macros/out/struct_C1.lef:6` | `0.930 4.830` |
| 3 | LEF `FOREIGN` | 七份研究宏 LEF | **全部不存在**（`grep -c FOREIGN` = 0） |
| 4 | LEF PIN/PORT/OBS | `struct_C1.lef:9-38` | 仅 1 个 PIN `net`；met1 + 3×met2 端口矩形；OBS 覆盖全部金属 |
| 5 | OpenROAD ODB 实例变换 | `src/config.json:126-139` | `u_rs_branch` @ `(79.32, 208.0)` 朝向 `N` |
| 6 | DEF COMPONENT 放置点 | `final/def/…def` | `u_rs_branch 79320 208000`（即 79.320, 208.000 µm） |
| 7 | 最终 GDS 实际金属坐标 | `final/gds/…gds` | 框架 B 下 4/4 端口全命中铜（覆盖率见 §3） |
| 8 | Magic 抽象端口坐标 | 由 LEF 在放置点重建 | 等价于框架 A（不应用 ORIGIN），4/4 端口命中 0 µm² |

---

## 2. LEF/DEF 5.8 规定的精确变换

**标准语义（LEF 5.8 `MACRO` 段）：**

```
SIZE w BY h      -- 宏局部边框，局部坐标恒为 [0,w] × [0,h]
ORIGIN x y       -- 宏局部原点 (0,0) 在【父/实例坐标系】中的位置
                  （父系 = 放置点，而不是宏内部）
```

**由此推出，任何一个宏内部点 `(lx, ly)` 在芯片上的位置是：**

```
P_chip = P_place + M(orient) · (lx - ORIGIN_x, ly - ORIGIN_y)          (式 1)
```

其中 `M(orient)` 是朝向矩阵（本设计七个宏全为 `N`，即单位矩阵）。

**关键且容易被忽略的一点：** 当 `ORIGIN` 取宏的 GDS bbox 左下角时（本设计正是如此，
`macros/gen_lef.py:349` 就是 `ORIGIN = (bbox[0], bbox[1])`），式 1 中的
`(lx - ORIGIN_x, ly - ORIGIN_y)` 恰好把「GDS 绝对坐标」还原成「以 bbox 左下角为零点」，
于是：

```
P_chip = P_place + (P_gds - bbox_corner)                              (式 2)
```

**这正好就是框架 B。** 也就是说，**按标准正确实现，框架 B 是唯一答案**；
路由器与最终 GDS 都符合标准，Magic 的抽象视图不符合。

---

## 3. 当前实际工具行为（MEASURED）

同一个 8 端口集合，在三种候选框架下的铜命中（`tools/v2_ci_diagnostics/b_r1_origin_scope.py`）：

| 框架 | 定义 | research_branch | research_via1 | research_via2 | 总计 |
|---|---|---|---|---|---|
| **A** | `place + RECT`（忽略 ORIGIN） | 0.0000 µm² | 0.0000 µm² | 0.0000 µm² | **0/8** |
| **B** | `place + RECT + ORIGIN`（式 2） | 4 个端口全有铜 | 全有铜 | 全有铜 | **8/8** |
| **C** | `place − ORIGIN + RECT` | 0.0000 µm² | 0.0000 µm² | 0.0000 µm² | **0/8** |

对照路由器：5/5 悬空端点落在 **框架 B**。
对照最终 GDS：`GDS_local = LEF_RECT + ORIGIN` 在 8/8 端口覆盖率精确 **100.0%**。

> **结论 1：** 最终版图完全符合 LEF 5.8。Magic 的抽象视图等价于框架 A，是**唯一偏离标准的一方**。
> 关于 Magic 内部为何如此：**UNVERIFIED**（本地无二进制/源码/网络），本文件只主张「结果等价于 A」。

---

## 4. 用户要求的重点：为什么是 VGND/VPWR，而不是只有 research_branch/net？

这是本节要回答的核心问题。答案是：**ORIGIN 偏移对两者没有任何区别，它们不是同一个故障。**
把两件事混为一谈是本轮之前最容易犯的错误，所以下面逐条拆开。

### 4.1 先看 `pwm_out` 到底是什么

**MEASURED（`final/def` 与 `pnl.v`）：**

```
DEF 里 pwm_out 是【一个 net，5 个引脚】：
    sky130_fd_sc_hd__a22o_2/X = 1
    sky130_fd_sc_hd__a22o_2/B1 = 1
    research_branch/net = 1
    research_via1/net   = 1
    research_via2/net   = 1
```

- `pwm_out` **不是顶层端口**（`64-magic-spiceextraction` 的 `.subckt` 端口表里没有它）。
- `pwm_out` **不是子电路**（两侧都不是；它只是一根内部网络）。
- 它**没有 VGND/VPWR 引脚**。

netgen 明细里的 `Net: FILLER_53_9/VPB | Net: pwm_out` 是**两侧网络配对失败后的错位排列**，
左边根本不是 `pwm_out` 的对应物。netgen 自己也打印了
`Port matching may fail to disambiguate symmetries.`

### 4.2 再看 VGND/VPWR 的差异是什么

**MEASURED（`66-netgen-lvs/reports/lvs.netgen.rpt` NET-mismatch 段，本次逐行复算）：**

```
Net: VGND   总扇出  circuit1 = 707   circuit2 = 665    差 = 42
     只有 4 行不同：
        decap_3/VGND   14 | 1        decap_3/VNB   14 | 1
        fill_2 /VGND    9 | 1        fill_2 /VNB    9 | 1
     差值和 = (14-1)×2 + (9-1)×2 = 26 + 16 = 42  ✔ 完全闭合

Net: VPWR   总扇出  circuit1 = 683   circuit2 = 665    差 = 18
     只有 3 行不同：
        decap_3/VPWR   14 | 1        fill_2/VPWR    9 | 1
        conb_1 /VPB     9 | 12
     差值和 = 13 + 8 - 3 = 18  ✔ 完全闭合
```

**这 42 和 18 里，没有一个比特与 ORIGIN、与 research 宏、与坐标框架有关。**

### 4.3 两个故障的结构对比

| | `pwm_out` 残段（R1 主体） | VGND/VPWR 差异 |
|---|---|---|
| 数量 | `net_difference` 中的 **4** 个 | 见 §4.2，是**扇出计数**差，不是独立网络 |
| 物理原因 | Magic 抽象端口错位（框架 A） | **dummy 单元 VPB/VNB 悬空**，串并联归并破裂 |
| 涉及单元 | `a22o_2` ×2 + 三个 research 宏 | `decap_3` 13 个 + `fill_2` 8 个 || 与 OPT-A 的关系 | **无关**（三个宏保留） | OPT-A 删除这些单元后，21 个悬空组消失 |
| 能否靠改 ORIGIN 消除 | **不能**（三宏 ALL 断，非单宏） | **不能**（ORIGIN 不进入器件归并） |

### 4.4 回答用户的原问题（逐字）

> 「为什么 `struct_C1` 的 ORIGIN 偏移会导致 R1 中 VGND/VPWR 的未匹配，而不是只影响 research_branch/net？」

**这个因果关系不存在，不能证明——因为它的前提本身是错的。** 三点：

1. **`struct_C1` 的 ORIGIN 并没有「偏移」。** 实测它与 GDS bbox 左下角精确相等（§1、§2），
   七份宏 LEF 全部如此。没有错误取值可供「修正」。
2. **ORT 也确实不只影响 `research_branch/net`。** 另外两个宏 `research_via1`、`research_via2`
   的 ORIGIN 同样取自各自 bbox（同样合法），**它们也各自被切成残段**（§3 表中 A 框架 8/8 全零）。
   R1 的比例是 4 个残段，正好对应「3 个研究宏引脚 + 1 个 a22o_2 引脚」都被切开，
   而不是只有 `research_branch`。
3. **VGND/VPWR 的未匹配有完全独立的来源**（§4.2）：dummy 单元的 bulk 悬空导致 netgen
   归并失败。它与 ORIGIN、与宏、与任何坐标都没有关系；它与 R1 只是恰好出现在同一份
   LVS 报告里，被 LibreLane 合并成 `design__lvs_error__count = 44` 一个数字。

> **结论 2：** ORIGIN 偏移**不会**导致 R1 中的 VGND/VPWR 未匹配；VGND/VPWR 未匹配
> 是 R2（OPT-A 的目标），不是 R1。把两者归因到同一个 ORIGIN 是本轮之前最大的错误前提。

### 4.5 `pwm_out` 的 5 个引脚 → 4 个网络的闭合证明

**MEASURED（`64-magic-spiceextraction/…spice` 逐行复算）：**

```
参考侧（DEF / 门级）             版图侧（Magic 提取）
pwm_out 一个 net，5 个引脚   ->   _214_/X           2 引脚  a22o_2/X + a22o_2/B1
                                 u_rs_branch/net   1 引脚  research_branch/net
                                 u_rs_via1/net     1 引脚  research_via1/net
                                 u_rs_via2/net     1 引脚  research_via2/net
                                 ------------------------------------------------
                                 合计               5 引脚  (= 参考侧 5 引脚)
```

`X_214_.X = _214_/X` 且 `X_218_.B1 = _214_/X`，两者本就是同一网络；
三个宏各自孤立成单引脚残段。**R1 的比例是 1/4**：只有 1 个残段属于标准单元
（`a22o_2` 对），**另外 3 个残段正好是三个研究宏各一个**。

> 这条闭合正好否证了「只影响 `research_branch`」的说法：三个研究宏**全部**被切开，
> 而 `research_branch` 只是其中之一，占 4 个残段里的 1 个。

### 4.6 三个研究宏为什么没有电源网络问题

**MEASURED（`grep '^  PIN '` 全部七份 LEF）：** 只有 3 份有 `PIN net`，其余 4 份（`near`/`cross`/`dense`/`fiducial`）**连 PIN 都没有**——纯几何宏，只有 OBS。

**MEASURED（`src/config.json:195`）：**

```json
"IGNORE_DISCONNECTED_MODULES": ["research_fiducial","u_rs_fiducial","research_near","u_rs_near",
                                "research_cross","u_rs_cross","research_dense","u_rs_dense"]
```

注意：**`research_branch` / `research_via1` / `research_via2` 及其实例不在这个豁免列表里。**
这与它们的 LEF 状态一致：有 `PIN net`，必须真连上。

> 所以三个宏根本没有 VGND/VPWR 引脚可供「未匹配」。用户问题里假设的「VGND/VPWR
> 未匹配源于 struct_C1」，在物理结构上就无从成立。

---

## 5. 缺陷归属（R1 / R2 / R3 分开记）

| 编号 | 内容 | 归属 | 本轮动作 |
|---|---|---|---|
| **R1** | `pwm_out` 被 Magic 切成 4 段（3 个单引脚残段） | Magic 抽象视图用框架 A；路由器与 GDS 用框架 B | **仅诊断，不修** |
| **R2** | `device_difference = 21`（13 decap_3 + 8 fill_2 的 VPB 悬空） | 窄段无 tap + 浮动 bulk | OPT-A 候选（**PREDICTED**，不是 PASS） |
| **R3** | `uio_out[7]` ↔ `uio_oe[2]` 对称性匹配假象 | 拓扑同构，非缺陷 | **不改**，如实记录 |

**三者不得合并为一个「LVS 错误」。** LibreLane 的 `design__lvs_error__count = 44`
是把它们加在一起的结果，分解已在 `v2_validation/P5_CLOSEOUT_B_LVS_CAUSAL.md` 完成。

---

## 6. 为什么不实施「重写 LEF PORT」（方案 3，已被禁止）

用户已明确禁止，本文件的实测也独立支持这个决定：

- 若把 PORT 矩形预先加上 ORIGIN 写死，路由器按式 1 会再加一次 ORIGIN，端点整体平移，
  **把「提取错位」变成真实的物理开路**。
- 现行 8/8 端口在框架 B 下覆盖率 100.0%、via-aware BFS 11 次迭代可达 30.700 µm²。
  **现在的版图是对的**，不应该为了让一个不遵循标准的读取器满意而去改它。

---

## 7. 本轮结论

1. **R1 没有找到可安全实施的修复，因此不修改，也不声称已解决。** ✔（符合用户条件分支）
2. `struct_C1` 的 ORIGIN **合法**，早前「非法 ORIGIN」的判断**作废并已更正**（见 `P5_CLOSEOUT_B_LVS_CAUSAL.md` §2.8）。
3. VGND/VPWR 的未匹配属于 **R2**，与 ORIGIN 无关；把两者归因到同一原因不成立。
4. `MAGIC_DEF_LABELS` **不启用**（用户禁止；且几何证据证明连通性是真的，不需要标签替代）。
5. 剩余未知：Magic LEF reader 为何采用框架 A —— **UNVERIFIED**，需真实 Magic 环境，本地不具备。
