# V2 最终验收报告（α′ 电气接口 + 无端口几何接口）

日期：2026-10-28
分支：`exp/v2-2x2-research`
基线：V1 黄金 commit `24fc6a5`（**未改动**）
结论：**本地 10 / 10 通过**。官方 CI 未运行，不得据此声称 Pin Access、布线或 LVS 通过。

---

## 0. 一句话结论

七类研究结构全部接入 2×2 芯片。其中 **A/B/C1 用 α′ 电气接口**（一个 PIN、
一个 PORT、多个跨层几何），**C3/C4/D/E 用无端口几何接口**（0 PIN）。
本地能验的 10 项全部实测通过；**官方 CI 是本轮之后仍必须做的事**，
本轮未提交、未 Push、未触发 CI、未付款。

> **口径更正**：早期表述"七宏全部使用 α′"是不准确的。α′ 只适用于有电气
> 端口的 A/B/C1；C3/C4/D/E 没有端口，适用的是几何接口（OBS 整块阻挡）。

---

## 1. 本轮做了什么

上一轮把分类判据改正为"同一 GDS 连通分量上的多个 PIN 若连到不同逻辑 Net
才是问题"之后，用户进一步指出 LEF/DEF 5.8 的 PORT 语义：

> 同一个 PIN 下，不同 PORT 之间视为**弱连接**；
> 同一个 PORT 内多个几何图形视为**强连接**。

因此最终接口定为 **α′**：一个逻辑 PIN → 一个 PORT → PORT 内含属于同一真实
GDS 连通分量的多个跨层金属接入图形。

改动清单（**GDS 几何零改动**）：

| 文件 | 改动 |
|---|---|
| [macros/gen_lef.py](macros/gen_lef.py) | A/B/C1 各 1 个 PIN `net`、1 个 PORT、2–4 个跨层 LAYER/RECT；C3 清空 PIN；方向统一 INOUT；新增 `clean()` 消除 `-0.000`；**新增 OBS 源规则（规则 E / 规则 G）与 O1/O3/O4 不变量断言**，见 §6.1 |
| [src/research_macros.v](src/research_macros.v) | A/B/C1 → `(* blackbox *) (* keep *) module … (inout wire net)`；C3/C4/D/E → 无端口 |
| [src/project.v](src/project.v) | 三个电气实例改为 `.net(pwm_out)`；四个几何实例无端口；删除 `_rs_obs` 折叠逻辑 |
| [src/config.json](src/config.json) | `IGNORE_DISCONNECTED_MODULES` 加入 `research_near` / `u_rs_near`（现 8 项），27 个 `"//"` 注释键完整保留 |
| [macros/p3_patch_config.py](macros/p3_patch_config.py) | `NON_ELECTRICAL` 同步为 C3/C4/D/E |
| [macros/p3_check_electrical_connectivity.py](macros/p3_check_electrical_connectivity.py) | `ELECTRICAL` = A/B/C1；`check_rtl_ports()` 断言"恰好 1 个端口且名为 net" |
| [macros/p3_verify_macro_views.py](macros/p3_verify_macro_views.py) | `NON_ELEC` 加入 C3 |
| [macros/p3_synth_netlist_check.py](macros/p3_synth_netlist_check.py) | `EXPECTED` 端口表改为 `['net']` / `[]` |
| **[macros/p3_assert_pin_port_contract.py](macros/p3_assert_pin_port_contract.py)** | **新增**，五视图链断言（C1–C11） |
| **[macros/_run_all_checks.sh](macros/_run_all_checks.sh)** | **新增**，一键跑完全部 22 项本地检查（含 SKIP≠PASS 语义）|

### 1.1 GDS 几何零改动（逐图形实测）

七个宏的 GDS 在 `git status` 里显示为 modified，那只是 GDS 写入时间戳。

**上一轮只比较了每层图形数量，这不够**：数量相同不等于几何相同 —— 一条线
可以从 y=1 平移到 y=2、一个矩形可以翻转、一个多边形可以改形状，数量都不变。
本轮改为**逐图形摘要**：

对每个宏、每种层，把该层全部图形规范化为
`(layer, datatype, 形状类别, 绝对坐标)`，排序后做 SHA-256：

- **形状类别**参与比较（`box` / `polygon` / `path`），视觉相同但记录类型
  不同也算不同；
- **绝对坐标**由 `begin_shapes_rec` 施加层次变换得到，所以"坐标一致"
  已经蕴含"层次变换一致"，不需要单独检查；
- **多边形**按缠绕方向规范化并从最小顶点起始旋转，消除顶点起点/方向的
  人为差异；
- **时间戳、库名、BGNLIB 日期、记录顺序**都不进摘要 —— 这正是"排除文件
  时间戳差异"。

| 宏 | 非空层 | HEAD 图形数 | 工作区图形数 | HEAD 摘要 | 工作区摘要 | 判定 |
|---|---|---|---|---|---|---|
| A | 4 | 8 | 8 | `21405b27113172ce` | `21405b27113172ce` | **PASS** |
| B | 4 | 7 | 7 | `9d784e867e841b1a` | `9d784e867e841b1a` | **PASS** |
| C1 | 4 | 14 | 14 | `4930cd8678abf3f5` | `4930cd8678abf3f5` | **PASS** |
| C3 | 2 | 9 | 9 | `230a0c518e4fe9e4` | `230a0c518e4fe9e4` | **PASS** |
| C4 | 3 | 3 | 3 | `0dc226e2f9cea7f1` | `0dc226e2f9cea7f1` | **PASS** |
| D | 4 | 14 | 14 | `ed16d9a062a6998e` | `ed16d9a062a6998e` | **PASS** |
| E | 3 | 7 | 7 | `e08e5747b496e7d2` | `e08e5747b496e7d2` | **PASS** |
| ALL | — | — | — | `4a61d0bd686c3f59` | `4a61d0bd686c3f59` | **PASS** |

合并版 `v2_structures.gds` 同样 PASS。**研究结构的物理几何一个图形都没动。**

#### 第二层证据：逐字节对照

摘要**不读**时间戳，所以单靠摘要证明不了"两个文件只差时间戳"——它只证明
"几何只差时间戳之外的东西不存在"。为把这一点也变成实测，脚本另外做了一次
逐字节比较，并要求**每一个**不同的字节都落在 `BGNLIB`(0x0102) 或
`BGNSTR`(0x0502) 日期记录内部：

| 文件 | 字节数 | 不同字节 | 命中的日期记录 | 日期记录之外 |
|---|---|---|---|---|
| A | 628 | 12 | BGNLIB, BGNSTR | NONE |
| B | 564 | 12 | BGNLIB, BGNSTR | NONE |
| C1 | 1014 | 12 | BGNLIB, BGNSTR | NONE |
| C3 | 692 | 12 | BGNLIB, BGNSTR | NONE |
| C4 | 308 | 12 | BGNLIB, BGNSTR | NONE |
| D | 1012 | 12 | BGNLIB, BGNSTR | NONE |
| E | 568 | 12 | BGNLIB, BGNSTR | NONE |
| ALL | 4390 | 48 | BGNLIB, BGNSTR | NONE |

两份文件长度完全相同、不同字节数恰好等于 2×6（`BGNLIB` 与 `BGNSTR` 各 6 个
日期字段），且**没有一个不同字节落在日期记录之外**。这把"只是时间戳"从
一句推断变成了可复核的测量。

#### 第三层：负向对照

**摘要本身的判别力也做了对照**（`macros/_neg_gds_identity.py`）：对 A 的
GDS 施加三种**不改变图形数**的扰动，摘要必须变化；同时逐字节检查也必须
在日期记录之外报出差异（否则"日期之外 = NONE"可能只是检查从未触发）。

```
baseline digest: 21405b27113172ce  shapes: 8
  pya roundtrip      diffbytes=8 outside_dates=NONE  OK
  translate_1dbu     shapes=8 (base 8)  digest=907b593300c0eace  CAUGHT=True  bytes_outside_dates=5
  widen_1dbu         shapes=8 (base 8)  digest=875a463886bb79a9  CAUGHT=True  bytes_outside_dates=2
  mirror_x           shapes=8 (base 8)  digest=cf47a627c5ec2112  CAUGHT=True  bytes_outside_dates=20
NEGATIVE CONTROL: PASS (all perturbations detected)
```

`pya roundtrip` 那一行是**反向对照**：把未扰动的原文件读进来再写出去，逐字节
只差日期记录 —— 证明"日期记录之外为 NONE"是检查真的在跑并且判对了，而不是
这个条件恒真。三种扰动图形数都是 8，旧的数量比较会全部漏掉；摘要与字节检查
都抓到。

完整的逐层明细与逐字节明细见 `v2_validation/P4_GDS_IDENTITY.md`。

---

## 2. 本地验收结果

一键脚本 `macros/_run_all_checks.sh` 顺序执行 **22 个**检查，全部 PASS 才返回 0。

| # | 检查 | 脚本 | 结果 | 实测输出 |
|---|---|---|---|---|
| 1 | GDS 生成 | `gen_v2_macros.py` | **PASS** | 七宏 + 合并版重新生成，摘要不变 |
| 2 | LEF + OBS 生成 | `gen_lef.py` | **PASS** | 七宏 LEF 重生成**字节一致**；O1/O3/O4 + 规则 E/G 断言全过 |
| 3 | 放置规划 | `p3_placement_plan.py` | **PASS** | 5.00 µm 最小间距被断言 |
| 4 | config 文本注入 | `p3_patch_config.py` | **PASS** | 8 项豁免 + 27 个 `"//"` 注释键保留 |
| 5 | 综合网表七实例 + 端口名 | `p3_synth_netlist_check.py` | **PASS** | 7/7 存活；A/B/C1 `net=pwm_out` |
| 6 | 五视图链契约 | `p3_assert_pin_port_contract.py` | **PASS** | 7/7 宏 C1–C11 全过 |
| 7 | 四源一致 + 5 µm | `p3_assert_consistency.py` | **PASS** | 7 结构 × 4 源一致；最小间距 5.10 µm ≥ 5.00 |
| 8 | prB = LEF = GDS | `p3_verify_macro_views.py` | **PASS** | 7/7 三个 bbox 完全相等，ORIGIN 匹配 |
| 9 | 电气连通 + 分量数 | `p3_check_electrical_connectivity.py` | **PASS** | A:2(期望2) B:1(1) C1:1(1) C3:8(8) C4:2 D:13 E:4 |
| 10 | 七宏集成矩阵 | `p3_integration_matrix.py` | **PASS** | 七行 × 五视图 |
| 11 | 放置图渲染 | `p3_render_placement.py` | **PASS** | `P3_MACRO_PLACEMENT.png` |
| 12 | PDN 冲突估算 | `p3_pdn_conflict_check.py` | **PASS** | 最坏 D：LOW |
| 13 | 文档同步 | `p3_sync_docs.py` | **PASS** | 文档数值与派生数据一致 |
| 14 | 拓扑 | `verify_topology.py` | **PASS** | 7/7（A 分量=2 via1=1；C3 分量=8；C4 无 via；D 五档线宽；E 跨层同坐标）|
| 15 | 几何 DRC | `run_all_drc.py` | **PASS** | 7/7 零违规 |
| 16 | DRC 负向对照 | `_negative_control.py` | **PASS** | 3/3 违规被抓（too_narrow / too_close / bad_enclosure）|
| 17 | **LEF OBS 独立复核** | `p3_verify_lef_obs.py` | **PASS** | O1–O6 + 规则 E/G；ODB 三方一致；见 §2.4 |
| 18 | **OBS 负向对照** | `_neg_obs.py` | **PASS** | 4/4 扰动被抓；见 §2.4 |
| 19 | **V1 官方 LEF 取证** | `p3_v1_lef_evidence.py` | **PASS** | V1–V5 全过；见 §2.5 |
| 20 | **GDS 几何逐图形一致** | `p3_gds_identity.py` | **PASS** | 7 宏 + 合并版摘要与 HEAD 完全相同 |
| 21 | **几何摘要判别力对照** | `_neg_gds_identity.py` | **PASS** | 3/3 扰动被抓（图形数不变）|
| 22 | 源文件一致 | `tools/check_source_files.py` | **PASS** | info.yaml / src / test-Makefile 一致 |

外加 `cd test && make` 的 **13 / 13** cocotb。

> 第 19 项依赖仓库之外的 V1 CI 产物。该产物不在本机时脚本返回 2，一键脚本
> 会把它标成 **SKIP（NOT a pass）** 并单独计数，绝不混进 PASS。

### 2.1 第 1 项：五视图链的实际输出

```
tag  cell                 pins   vs     ports    comps    verdict
A    research_via1        1      1      2        1        OK
B    research_via2        1      1      1        0        OK
C1   research_branch      1      1      1        0        OK
C3   research_near        0      0      8        8        OK
C4   research_cross       0      0      2        2        OK
D    research_dense       0      0      13       13       OK
E    research_fiducial    0      0      4        4        OK
```

列含义：`pins` = LEF PIN 数；`vs` = Verilog 端口数；`ports` = GDS 连通分量总数；
`comps` = 其中**不含 PIN** 的分量数。

C1–C11 逐项：

| 编号 | 断言 | 结果 |
|---|---|---|
| C1 | LEF PIN 名 == Verilog 端口名（逐字符） | ✅ 全部 `net` |
| C2 | LEF PIN 数 == Verilog 端口数 | ✅ 1==1 / 0==0 |
| C3 | 一个 PIN 恰好一个 PORT（强连接） | ✅ 全部 1 |
| C4 | 同一 PIN 的全部 PORT 几何在同一 GDS 分量 | ✅ A/B/C1 各 1 个 root |
| C5 | 该分量含 ≥1 个 via cut | ✅ A:1 B:1 C1:3 |
| C6 | LEF DIRECTION == Verilog 方向 | ✅ INOUT == inout |
| C7 | 无端口宏的 LEF PIN 数 == 0 | ✅ C3/C4/D/E 全 0 |
| C8 | 无 PIN 分量数符合物理预期 | ✅ A=1（netC 邻居线），B/C1=0 |
| C9 | 综合网表端口名 == LEF PIN 名 | ✅ 7/7 |
| C10 | 每个端口接且仅接一个非常量 net | ✅ A/B/C1 全 `pwm_out` |
| C11 | A/B/C1 落在同一 net | ✅ 全部 `pwm_out` |

### 2.2 第 5 项：综合后网表

```
instance         cell               exists ports  connections
u_rs_via1        research_via1      YES    OK     net=pwm_out
u_rs_via2        research_via2      YES    OK     net=pwm_out
u_rs_branch      research_branch    YES    OK     net=pwm_out
u_rs_near        research_near      YES    OK     -
u_rs_cross       research_cross     YES    OK     -
u_rs_dense       research_dense     YES    OK     -
u_rs_fiducial    research_fiducial  YES    OK     -
```

流程：`synth -top` → `flatten` → `opt` → `write_verilog -noattr`。
本地 yosys **0.69**，官方是 **0.62** —— 见 §5.2 的口径限制。

### 2.3 一键重跑

`macros/_run_all_checks.sh` 顺序执行全部 **22** 个本地脚本，任何一步失败即打印
末尾日志并计入失败数：

```
gen_v2_macros.py                           PASS
gen_lef.py                                 PASS
p3_placement_plan.py                       PASS
p3_patch_config.py                         PASS
p3_synth_netlist_check.py                  PASS
p3_assert_pin_port_contract.py             PASS
p3_assert_consistency.py                   PASS
p3_verify_macro_views.py                   PASS
p3_check_electrical_connectivity.py        PASS
p3_integration_matrix.py                   PASS
p3_render_placement.py                     PASS
p3_pdn_conflict_check.py                   PASS
p3_sync_docs.py                            PASS
verify_topology.py                         PASS
run_all_drc.py                             PASS
_negative_control.py                       PASS
p3_verify_lef_obs.py                       PASS
_neg_obs.py                                PASS
p3_v1_lef_evidence.py                      PASS
p3_gds_identity.py                         PASS
_neg_gds_identity.py                       PASS
check_source_files.py                      PASS

ALL LOCAL CHECKS PASS
```

加上 `cd test && make` 的 13/13，共 **22 脚本 + 13 测试** 全通过。

### 2.4 第 17–18 项：OBS 的独立复核与负向对照

`gen_lef.py` 写 LEF 前的自检用的是**它构造 OBS 时同一批 Region**：如果它的
金属提取或坐标平移本身有 bug，自检会跟着一起错。`p3_verify_lef_obs.py`
因此**不 import `gen_lef.py`**：

- LEF 文本由本脚本自己的解析器读回；
- GDS 金属由本脚本自己从 prBoundary 锚定重建；
- 再用 **OpenROAD ODB**（第三方读取器）对照 —— 不只对总数，还**逐层对
  OBS 矩形数**。只对总数是弱检查：一个把全部 OBS 都挂到错误层上的读取器，
  总数仍然完全正确。

```
tag  cell                 rule  pins  ports  obs_rect free_sides   verdict
A    research_via1        E     1     1      7        min 3        PASS
B    research_via2        E     1     1      6        min 3        PASS
C1   research_branch      E     1     1      13       min 3        PASS
C3   research_near        G     0     0      1        -            PASS
C4   research_cross       G     0     0      2        -            PASS
D    research_dense       G     0     0      3        -            PASS
E    research_fiducial    G     0     0      2        -            PASS

ODB cross-check: RUN
  research_via1        ODB pins=1 ports=1 obs=7  | text pins=1 ports=1 obs=7   PASS
  research_via2        ODB pins=1 ports=1 obs=6  | text pins=1 ports=1 obs=6   PASS
  research_branch      ODB pins=1 ports=1 obs=13 | text pins=1 ports=1 obs=13  PASS
  research_near        ODB pins=0 ports=0 obs=1  | text pins=0 ports=0 obs=1   PASS
  research_cross       ODB pins=0 ports=0 obs=2  | text pins=0 ports=0 obs=2   PASS
  research_dense       ODB pins=0 ports=0 obs=3  | text pins=0 ports=0 obs=3   PASS
  research_fiducial    ODB pins=0 ports=0 obs=2  | text pins=0 ports=0 obs=2   PASS
```

逐层 OBS 矩形数（ODB 与文本解析逐层相等）：

| cell | ODB 逐层 | 文本逐层 |
|---|---|---|
| `research_via1` | met1=4, met2=3 | met1=4, met2=3 |
| `research_via2` | met2=3, met3=3 | met2=3, met3=3 |
| `research_branch` | met1=7, met2=6 | met1=7, met2=6 |
| `research_near` | met1=1 | met1=1 |
| `research_cross` | met1=1, met2=1 | met1=1, met2=1 |
| `research_dense` | met1=1, met2=1, met3=1 | met1=1, met2=1, met3=1 |
| `research_fiducial` | met1=1, met2=1 | met1=1, met2=1 |

> 这一列是本轮**新发现并修掉的检查缺陷**。最初的 ODB 模板用
> `lsearch` 收集层名、只打印层名字表，Python 侧又只读第一个字段，结果
> 每个宏都被记成"单层"。总数仍然对得上，所以检查一直是 PASS —— 但那时的
> PASS 比现在弱。改为逐层直方图后，先暴露出 Tcl `array set` 不清空旧数组
> 导致计数跨宏累加的 bug（B 的 met1 被算成 4），修掉后七个宏逐层完全吻合。

**Pin Access 的本地证据**（这是 §5.1 第 1 项唯一能在本地靠近的部分）：
对每个 PIN 矩形，在同层四边各取 **1.0 µm 走廊**，要求走廊**完全**不被 OBS
占据（被咬掉一半的走廊不算通道）。

```
A  met1 3 个自由方向: left, below, above
A  met2 3 个自由方向: right, below, above
B  met2 3 个自由方向: left, below, above
B  met3 3 个自由方向: right, below, above
C1 met1 3 个自由方向: left, below, above
C1 met2 ×3 各 3 个自由方向: left, right, above
```

OBS 的不变量（全部逐层断言）：

| 编号 | 断言 | 结果 |
|---|---|---|
| O1 | OBS ∩ PIN = ∅ | ✅ 七宏全部 0 |
| O2 | 每个 PIN ≥3 个完全自由的接近方向 | ✅ 最少 3 |
| O3 | OBS 矩形互不重叠（平铺而非叠加） | ✅ 全部 0 |
| O4 | OBS 全在 footprint 内 | ✅ 全部 0 |
| O5 | 不在没有金属的层上放 OBS | ✅ |
| O6 | **met4 / met5 上零 OBS**（PDN 层） | ✅ |
| E1/E2 | `金属 ⊆ OBS∪PIN` 且 `OBS ⊆ 金属` | ✅ A/B/C1 |
| G1/G2 | `金属 ⊆ OBS`，且 OBS 面积 == footprint、恰好 1 矩形 | ✅ C3/C4/D/E |

**判别力对照**（`_neg_obs.py`，四种扰动各触发一条被检查的不变量）：

```
case               expects   hits        caught problems
obs_covers_pin     O1        O1          True   O1 A met1: OBS overlaps a PIN by 19600 dbu^2
obs_blocks_pin     O2        E2,O2,O3,O4 True   O3 A met1: OBS rects overlap by 280000 dbu^2
obs_missing        E1        E1          True   E1 A met1: 700000 dbu^2 of drawn metal is neither OBS nor PIN
obs_on_met4        O6        O5,O6       True   O5 C3: OBS on met4, which draws no metal

unperturbed originals: PASS
OBS NEGATIVE CONTROL: PASS (all four perturbations detected, originals clean)
```

扰动只施加在 `macros/_tmp_neg_obs/` 的**副本**上，`macros/out/struct_*.lef`
始终是 `gen_lef.py` 源规则的产物；对照结束后该目录被删除。

### 2.5 第 19 项：OBS 规则所依据的 V1 官方事实（可复跑）

规则 E / 规则 G 声称是 V1 官方 LEF 的推广。这个前提必须可复跑，否则规则
就是猜测。`p3_v1_lef_evidence.py` 重新测量 V1 CI 产物：

```
V1 official LEF: .../runs/wokwi/final/lef/tt_um_jiahao_plus_counter.lef
layer          #pin     #obs   pin∩obs um^2  pin-less single rect
------------------------------------------------------------------
li1               0        1       0.000000  True
met1              0        1       0.000000  True
met2              0        1       0.000000  True
met3              0        1       0.000000  True
met4             51       50       0.000000  n/a (has pins)
nwell             0        1       0.000000  True
  totals: 51 pins, 55 OBS rects

V1 flow.log:
  PDN_OBSTRUCTIONS         appears=True  assigned=False skipped_step=Odb.AddPDNObstructions
  ROUTING_OBSTRUCTIONS     appears=True  assigned=False skipped_step=Odb.AddRoutingObstructions
  FP_OBSTRUCTIONS          appears=False assigned=False skipped_step=-
  cut_rows step: 18   PDN step: 21   has halo: True
  cmd: cut_rows -halo_width_x 10.0 -halo_width_y 10.0 -endcap_master sky130_fd_sc_hd__decap_3
```

两条推论：

1. **规则 E/G 有实证基础**：V1 里没有 pin 的层各得一个整层矩形；有 pin 的层
   pin 与 OBS 同层重叠为 0。这正是 `OBS = 金属 − PIN`。
2. **OBS 是唯一的逐宏保护**：`PDN_OBSTRUCTIONS` / `ROUTING_OBSTRUCTIONS`
   在本流程里被显式报告为未定义、对应注入步骤被跳过；`FP_OBSTRUCTIONS`
   根本没有消费者。所以不留 OBS 就等于不做任何逐宏布线保护。

`cut_rows` 的命令行不在 `flow.log` 里（那里只有 `Running 'OpenROAD.CutRows'
at 'runs/wokwi/18-openroad-cutrows'`），必须去该步自己的日志读。只看
`flow.log` 会误报"没有 cut_rows"——脚本按这个事实读两个文件。

---

## 3. 独立工具链验证（ODB）

自己写的 LEF 解析器可能"自己验自己"。用 OpenROAD 的 ODB 独立复核了一遍：

```
research_via1        PINs=1 | net dir=INOUT PORTs=1 geomPerAllPorts=2 layers=met1,met2
research_via2        PINs=1 | net dir=INOUT PORTs=1 geomPerAllPorts=2 layers=met2,met3
research_branch      PINs=1 | net dir=INOUT PORTs=1 geomPerAllPorts=4 layers=met1,met2
research_near        PINs=0
research_cross       PINs=0
research_dense       PINs=0
research_fiducial    PINs=0
```

**这张表是 α′ 成立的直接证据**：1 PIN、1 PORT、2–4 个几何、跨 met1/met2 或 met2/met3。
若被拆成多个 PORT，`PORTs` 列会 > 1 —— 那就是弱连接。

> 说明：本地无 SKY130 PDK，ODB 默认不认识 met1/met2 会丢弃几何。上表用一个
> 7 层最小 tech LEF（仅声明层名/方向/间距/线宽，**不含任何宏定义**）注入后得到。
> 该 tech LEF 现在是 `p3_verify_lef_obs.py` 里的 `MIN_TECH_LEF` 常量，随检查
> 每次重新生成到临时目录并自动清理，不再是手工临时文件。

---

## 4. 七宏五视图归属（最终）

| ID | 宏 | ① GDS 分量 | ② LEF PIN | ③ Verilog | ④ 综合网表 Net | ⑤ 最终 GDS |
|---|---|---|---|---|---|---|
| **A** | `research_via1` | C0（M1+Via1+M2）+ 1 条无 PIN 邻居线 | `net`：1 PORT / 2 几何 | `inout net` | `pwm_out` | 待 CI |
| **B** | `research_via2` | 1 | `net`：1 PORT / 2 几何 | `inout net` | `pwm_out` | 待 CI |
| **C1** | `research_branch` | 1 | `net`：1 PORT / **4 几何** | `inout net` | `pwm_out` | 待 CI |
| **C3** | `research_near` | 8（互不相连） | 无 | 无 | 无 | 待 CI |
| **C4** | `research_cross` | 2（交叉不连） | 无 | 无 | 无 | 待 CI |
| **D** | `research_dense` | 13 | 无 | 无 | 无 | 待 CI |
| **E** | `research_fiducial` | 4 | 无 | 无 | 无 | 待 CI |

**规则 4（关键）**：A 的无 PIN 分量是 `y=6.73 µm` 的邻居线，必须永久保持无 PIN。
C8 断言它无 PIN，并且**不含任何 via cut**——若它意外拿到 via，就是一条跨层浮空节点。

---

## 5. 明确未验证的事项

### 5.1 本地做不到的（需官方 CI）

| # | 项 | 为什么本地做不到 |
|---|---|---|
| 1 | **Pin Access** | 需要完整 P&R |
| 2 | α′ 单 PORT 多几何是否被 router 正确使用 | 同上 |
| 3 | LVS 是否接受"内部短路的被动宏" | 需要 netgen + 真实 GDS |
| 4 | 宏是否被 fill / PDN 覆盖 | 需要最终 GDS |
| 5 | 最终 GDS 里七结构是否存在 | 同上 |
| 6 | C3 的 8 个分量是否仍独立 | 同上 |
| 7 | 真实 Core / PDN / 宏坐标 | 需要 DEF |
| 8 | 布线是否穿过研究图形 | **OBS 已加并本地复核（§6.1）**，但布线器是否真的遵守只能读 routed DEF |
| 9 | STA 对无 Liberty 宏的处理 | 需要 STA 报告 |

### 5.2 工具链差异

本地 yosys **0.69**（conda-forge），官方 LibreLane 3.0.14 用 **0.62**。
`blackbox` + `keep` 的行为已用两个控制实验复现一致（`_t3.v` / `_t4.v`），
但**这不是官方综合的逐字节复现**。

### 5.3 研究真值的三层区分

| 层级 | 含义 | 本地状态 | 需要什么才能确认 |
|---|---|---|---|
| **T1** | GDS 中确实存在 Via 连接 | ✅ **已实测**（宏内 C0 分量含真实 via cut，`P4_PIN_PORT_CONTRACT.json` 的 C5） | — |
| **T2** | 该 Via 连通域被分配到功能信号 Net | ✅ **本地跨视图映射已验证**：Verilog 端口 → 综合网表 net → LEF PIN 名，三段一致且都落在 `pwm_out`（C1/C9/C10/C11） | ⏳ **最终路由后的物理归属未验证**。需要官方 CI 的 routed DEF / final GDS，确认该宏实例的 PIN 在布线后仍连在 `pwm_out` 上、且未被短路到邻近导线 |
| **T3** | 功能电流必须经过该 Via | ❌ **未验证，不声称** | 电流路径分析 + 物理证据（IR drop、电迁移） |

**T2 的边界必须说清楚**：本地证明的是**设计意图在三个视图中一致** ——
Verilog 声明 `.net(pwm_out)`、综合后网表确实接在 `pwm_out`、LEF PIN 名与之一致。
它**不**证明布线器真的把 `pwm_out` 接到了那个宏 PIN 上。那要在官方 CI 的
routed DEF 里读 `NETS` 段才能确认。**T2 目前在"设计期"成立、"布局后"待验。**

---

## 6. 已知遗留风险

| 风险 | 状态 | 处理 |
|---|---|---|
| **A 的无 PIN 邻居线** | 距主节点约 0.14 µm | 若 CI 报间距/短路，需看 netC 是否被误接。规则 E 的 OBS 已覆盖它（它属于"金属 − PIN"）|
| **C3 无 PIN** | 设计决定 | 技术上 8 个独立导体可以有 8 个 PIN；选择无端口是为了不让 router 在间距阶梯旁打 via 污染测量。规则 G 整块 OBS 进一步保证内部不可布 |
| **D 的 PDN 重叠** | 3.9% 宽度落在一个假设的 M4 strap 下 | `p3_pdn_conflict_check.py` 标为 LOW。真实 strap 模式需 CI 才知道。**故意不挡 met4**，避免 ERROR_ON_PDN_VIOLATIONS |
| **OBS 是否被遵守** | 本地无法验证 | 需要 routed DEF 才能确认路由器没有穿过 OBS。本地只能证明 LEF 里确实有 OBS、且没有挡住 PIN。见 §6.1 |

### 6.1 OBS 保护的实际边界（本轮新增）

**已证明的**（本地，可复跑）：

1. 七个 LEF 都有 OBS，且由 `gen_lef.py` 源规则生成，重跑后**字节一致**；
2. A/B/C1 的 PIN 没被任何 OBS 覆盖，每个 PIN 至少 3 个完全自由的接近方向；
3. C3/C4/D/E 的整个 footprint 在其绘制层上被一个矩形挡住；
4. met4/met5 上一个 OBS 都没有 —— 不会与 PDN stripe 冲突；
5. 以上结论由**独立实现**（不 import `gen_lef.py`）+ **OpenROAD ODB** 三方
   交叉确认，且 ODB 与文本解析**逐层**的 OBS 矩形数完全相等（不只是总数）。

**未证明的**：

- 路由器是否真的遵守 OBS。LEF 只是**声明**，遵守与否要读 routed DEF 里
  有没有 net 的 wire/via 落在宏的 footprint 内。
- 真实 2×2 的 M4 stripe 位置。若 2×2 改用不同的 `PDN_VERTICAL_LAYER` 或
  不同的 stripe 模式，"不挡 met4"这个决定要重新论证。
- Pin Access 是否成功。本地只能证明"几何上 PIN 有 ≥3 个自由接近方向"，
  不能证明工具真的接上了。

**为什么不用"覆盖整个宏"的一刀切规则**：用户的约束是"不允许使用覆盖整个
宏、导致 PIN 不可访问的粗暴阻挡规则"。规则 E 在 A/B/C1 上把 PIN 从 OBS 里
挖掉正是为了满足这一条；规则 G 只用在**没有 PIN** 的四个宏上，那里不存在
"PIN 不可访问"的问题。

---

## 7. 本轮未做的事

- ❌ 未 Commit、未 Push、未触发官方 CI
- ❌ 未付款、未提交制造 Revision
- ❌ 未改动 `main`，未改动 V1 黄金 commit `24fc6a5`
- ❌ 未改动任何宏的 GDS 几何
- ❌ 未关闭 DRC / LVS / STA / PDN 任何检查
- ❌ 未伪造 SPICE/CDL、Liberty 或任何电气连接
- ❌ 未修改 Windows/WSL hosts，未绕过学校网络策略

---

## 8. 下一步

```
① 用户审查本报告
      ↓
② 批准一次 Commit + 一次 Push（须另行明确批准）
      ↓
③ 观察官方 CI —— 重点看：
     · CheckMacroInstances      七宏是否全部识别
     · Pin Access                α′ 的单 PORT 多几何是否可用
     · LVS                       被动宏是否被接受
     · 最终 GDS                  七结构是否完好、C3 八分量是否仍独立
      ↓
④ 若 Pin Access 失败：
     接入图形太小/位置不当 → 改 LEF RECT（不改 GDS）→ 重验
     工具不支持跨层强连接 PORT → 转 β（两 PIN 同 net）
```

---

## 9. 证据文件索引

| 文件 | 内容 |
|---|---|
| `v2_validation/P4_PIN_PORT_CONTRACT.json` / `.md` | 五视图链断言完整数据（本轮新增）|
| `v2_validation/P3_SYNTH_INSTANCES.json` / `.md` | 综合网表七实例 |
| `v2_validation/synth_netlist.v` | 综合后网表 |
| `v2_validation/synth_full.log` | yosys 完整日志 |
| `v2_validation/P3_ELECTRICAL_CONNECTIVITY.json` / `.md` | 分量数与引脚落点 |
| `v2_validation/P3_MACRO_VIEW_CONSISTENCY.json` / `.md` | prB = LEF = GDS |
| `v2_validation/P3_MACRO_BBOX.csv` | 放置坐标与 21 组间距 |
| `v2_validation/p3_placement.json` | 放置唯一源 |
| `v2_validation/P3_PDN_CONFLICT.json` | PDN strap 冲突估算 |
| `v2_validation/P4_PIN_COMPONENT_AUDIT.json` | 各宏物理分量实测 |
| `v2_validation/P3_SEVEN_MACRO_INTEGRATION.csv` | 七宏集成矩阵 |
| `macros/out/struct_*.lef` | 七个 LEF（A/B/C1 为 α′ 单 PIN 单 PORT；C3/C4/D/E 无 PIN，OBS 整块阻挡）|
| `v2_validation/P4_GDS_IDENTITY.json` / `.md` | 逐图形几何摘要（本轮新增）|
| `v2_validation/P5_LEF_OBS.json` / `.md` | OBS 独立复核 + ODB 三方对照（本轮新增）|
| `v2_validation/P5_V1_LEF_EVIDENCE.json` | OBS 规则所依据的 V1 官方事实（本轮新增）|
| `macros/p3_gds_identity.py` | 几何摘要生成器 |
| `macros/_neg_gds_identity.py` | 摘要判别力负向对照 |
| `macros/p3_verify_lef_obs.py` | OBS 独立复核（不 import `gen_lef.py`）|
| `macros/_neg_obs.py` | OBS 检查判别力负向对照 |
| `macros/p3_v1_lef_evidence.py` | V1 官方 LEF / flow.log 取证复跑 |
| `macros/_prefetch_head_gds.py` | 从 HEAD 取 GDS blob（Windows 侧）|
| `macros/out/macro_index.json` | LEF 生成索引 + 引脚落点 + OBS 不变量报告 |
| `macros/_run_all_checks.sh` | 一次跑完全部本地检查 |

---

## 10. 重跑方法

```bash
# 从仓库根目录，WSL
bash macros/_run_all_checks.sh    # 22 个脚本，全部 PASS 才返回 0
cd test && make                   # cocotb 13/13
```

实测结果：22 / 22 脚本 PASS，cocotb 13 / 13 PASS。

其中 `p3_gds_identity.py` 需要 HEAD 版本的 GDS。WSL 的 git 读不到本 worktree
的 Windows `.git` 指针（实测 rc=128），因此脚本会先尝试调用 `python.exe`
跑 `_prefetch_head_gds.py`；两者都不可用时该项 FAIL 而不是静默跳过。

> 这条自动补取本轮**修过一次**：最初把 `_prefetch_head_gds.py` 的**绝对**
> 路径传给 `python.exe`，WSL 的 `/mnt/c/...` 被 Windows 侧读成 `C:\mnt\c\...`，
> 且路径里的 `课题/` 经 ANSI 代码页往返被替换成 `????`，于是补取必然失败。
> 现在改为**仓库相对路径 + `cwd=ROOT`**，两个问题都不再发生；失败时会把
> stderr 打到终端，不再静默。删除 `macros/_tmp_gds_identity*/` 后从零重跑
> 已实测可以通过。

`p3_v1_lef_evidence.py` 依赖仓库之外的 V1 CI 产物（默认路径见脚本头部）。
产物不在时返回 2，一键脚本记为 **SKIP（NOT a pass）**，不会混进 PASS。

### 10.1 整理后的项目结构

```
tt-v2/
├── README.md                     顶层说明（含 α′ 接口与复现命令）
├── src/                          设计源
│   ├── project.v                 顶层 + 七宏实例
│   ├── research_macros.v         七宏 Verilog 视图（全部 blackbox+keep）
│   ├── pwm.v / LFSR_Design.v     第三方 IP
│   └── config.json               LibreLane 配置（7 宏 + 8 项豁免）
├── macros/
│   ├── gen_v2_macros.py          GDS 几何唯一源
│   ├── gen_lef.py                LEF/PIN/OBS 唯一源
│   ├── p3_*.py                   14 个断言/派生/取证脚本
│   ├── verify_topology.py / geom_drc.py / run_all_drc.py
│   ├── _negative_control.py      DRC 判别力对照
│   ├── _neg_obs.py               OBS 检查判别力对照
│   ├── _neg_gds_identity.py      几何摘要判别力对照
│   ├── _prefetch_head_gds.py     从 HEAD 取 GDS blob
│   ├── _run_all_checks.sh        一键全跑（22 项，SKIP≠PASS）
│   └── out/                      7 个 GDS + 7 个 LEF + 索引
├── v2_docs/                       6 份文档
│   ├── V2_FINAL_ACCEPTANCE.md    ← 本报告
│   ├── V2_FINAL_INTERFACE_DECISION.md
│   ├── V2_INTEGRATION_CONTRACT.md
│   ├── V2_ARCHITECTURE_DECISION.md
│   ├── V2_OFFICIAL_RULES_EVIDENCE.md
│   └── V2_HISTORY.md
├── v2_spec/                       规则与面积预算
├── v2_validation/                 验收证据（JSON/MD/CSV/PNG）
└── test/                          cocotb 13 项
```

已删除的过渡产物及理由见 [V2_HISTORY.md](V2_HISTORY.md) §7。
