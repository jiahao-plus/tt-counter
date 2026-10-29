# P5 第四轮前置：本地候选实施记录（OPT-A + R1 诊断）

编写日期：2026-10-29
对应授权：**「V2 P5：批准第四轮候选修复范围，但暂不授权 Git 提交」**

> **本轮只做本地实施。** 未 Commit、未 Push、未建 PR、未触发 CI、未付款、未提交正式 Revision。
> 未修改 V1 黄金版本，未关闭任何物理检查。

---

## 1. 本轮实际改了什么

### 1.1 本轮新增的设计改动：`src/config.json` 的 3 行

```diff
@@ -60,6 +60,9 @@

   "FP_PDN_VPITCH": 38.87,

+  "//": "CANDIDATE, NOT YET OFFICIAL-VERIFIED. CutRows prunes row segments narrower than this before tap/endcap insertion. 26.22 um = 57 sites = 2*round(FP_TAPCELL_DIST/0.46)+1, the narrowest segment that could legally host one tap. Historical evidence from run 40726887237: the 26 segments below this width hold 0 taps (0/997) and contain all 576 LU.2/LU.3/nwell.4 violations, while the 88 kept segments hold 0 such violations. NOT a guarantee that tap rules are satisfied -- that must be confirmed by the next CI run.",
+  "FP_PRUNE_THRESHOLD": 26.22,
+
   "//": "Clock",
   "RUN_CTS": 1,
```

### 1.2 工作区里**还压着上一轮未提交的** Via Pad 合规化修复

必须说清楚：HEAD `7135c54` 之后，工作区累积了**两轮**未提交的工作。
`git status` 显示 33 个已跟踪文件被修改，其中 `macros/out/struct_A|B|C1.gds/.lef`
是**真实几何变更**（焊盘放大），不是本轮 OPT-A 的产物，而是**上一轮已批准的**
Via Pad 合规化修复——它在上一轮做完了，但一直没有提交。

| 轮次 | 内容 | 文件 |
|---|---|---|
| 上一轮（未提交） | Via Pad 合规化 + 几何 DRC + GDS 身份比对工具 | `macros/gen_v2_macros.py`、`geom_drc.py`、`p3_gds_identity.py`、A/B/C1 的 GDS/LEF |
| **本轮** | **OPT-A 阈值** | **`src/config.json`（仅此一个设计文件）** |

所以准确的说法是：**本轮只往 `src/config.json` 加了 3 行，没有碰任何 GDS/LEF。**
A/B/C1 的几何变更是上一轮的，本轮只是**复核并确认它正确**（§4），
并重跑生成器使 C3/C4/D/E 的时间戳刷新（几何未变，§4.1）。

完整清单见 §9。

---

## 2. OPT-A：`FP_PRUNE_THRESHOLD = 26.22`

### 2.1 六条前置条件的逐条结论

| # | 前提 | 结论 | 证据 |
|---|---|---|---|
| 1 | LibreLane 真识别并传给 CutRows | **由推断满足，非直接实测** | 键已声明于 `resolved.json`；`_env.tcl` 通用过滤 null，37 个 null 全缺席 / 57 个非 null 全在场 → 写入值后必然出现 |
| 2 | 26.22 在制造网格上合法 | **满足** | `26.22 / 0.46 = 57.0000`；阈值比较连续段宽，不吸附网格；窗口 (11.04, 51.06] |
| 3 | 576/576 坐标归属可复现 | **满足（精确复现）** | bbox 重叠归属：DEL 576 / KEPT 0 / 跨界 0 / 无归属 0 |
| 4 | 丢 Tap 0、丢 Row 0 的准确含义 | **满足，但需分两层** | 段 26/114 删除；行 0/81 消失；tap 0/997；CutRows 时点标准单元 0 个 |
| 5 | 3 个 `conb_1` 仍能合法放置、逻辑不变 | **满足** | 3 个都是 `conb_1` 的常量 `HI` 输出，功能不依赖位置；它们在删除段内，由布局器重放 |
| 6 | 没有靠关 DRC/LVS/Tap 规则掩盖 | **满足** | 本轮 diff 未新增任何 skip/disable/ignore；`MAGIC_DEF_LABELS` 仍为 0；`RUN_KLAYOUT_DRC: 0` 是 HEAD 既有值，非本轮所改 |

### 2.2 最关键的一条新证据：182/182

要让阈值真的消掉 `device_difference = 21`，仅有「存在窄段」不够，
必须保证**所有 bulk 悬空的单元都在被删段内**。`tools/v2_ci_diagnostics/c_floating_bulk_census.py`：

```
class            floating  inPRUNE  outside unmapped
decap_3               164      164        0        0
fill_2                 15       15        0        0
conb_1                  3        3        0        0
fill_1 / tap            0        0        0        0
------------------------------------------------------
TOTAL                 182      182        0        0
```

**182 个悬空 bulk 单元全部在可删段内，0 个在保留段。**
netgen 组数交叉核对：`decap_3` 13 个悬空网络 → 14 组（netgen 报 `->14` ✔）；
`fill_2` 8 个 → 9 组（netgen 报 `->9` ✔）；`(14-1)+(9-1) = 21` ✔。

**这是必要条件，已满足。不是充分条件** —— 仍须真实跑一次 netgen。

### 2.3 本轮修正的两个测量错误

| 错误 | 影响 | 更正 |
|---|---|---|
| DEF `ROW` 前两个数字读成 Y、X | 所有几何判据交叉，伪造出「删掉 1 整行」 | 实为 **X 在前**。修正后 **丢 row = 0/81**；脚本已加 DIEAREA/网格自检，再读反会 assert 失败 |
| 违规归属用质心 | 576 中 552 条归入 DEL，24 条落空 | 改用 **bbox 重叠**：**576/576 全在 DEL，0 跨界** |

另有 `a_prune_physical.py` 中「保留段 51 条 15 µm 违规」的 PROXY 模型**已被否决**：
它量「段边缘到最近 tap 的距离」，而 LU.2/LU.3 针对**扩散区**，段尾空站点无扩散区。
Magic 实测保留段违规 = **0**。已在脚本内置醒目否决说明，防止被引用。

---

## 3. R1：诊断完成，**未修复**

用户条件：若无法证明安全修正方法，只保留诊断，不强行修改，不声称已解决。
**本轮即按此分支执行。**

完整分析见 [P5_R1_COORDINATE_CHAIN.md](P5_R1_COORDINATE_CHAIN.md)。核心结论：

1. **用户设问的前提不成立。** 「`struct_C1` 的 ORIGIN 偏移导致 VGND/VPWR 未匹配」——不存在这个因果链。
   - 实测 `struct_C1.gds` bbox = `0.930 4.830 .. 11.070 8.070`，LEF `ORIGIN (0.930, 4.830)`
     **精确等于该 bbox 左下角**；七份 LEF 全由同一个 bbox 导出（`macros/gen_lef.py:349`）。
     **没有非法 ORIGIN 可修。**（早前「ORIGIN y=4.830 > SIZE y=3.240 非法」的判断作废：
     前者在父坐标系、后者在局部坐标系，不可比。）
   - ORIGIN 也不只影响 `research_branch/net`：三个研究宏**全部**被切开。

2. **VGND/VPWR 的差异完全是另一件事（R2）。** 逐行复算：

```
Net: VGND  扇出 707 | 665  差 42 = (14-1)*2 + (9-1)*2
Net: VPWR  扇出 683 | 665  差 18 = 13 + 8 - 3
```
   只有 4 行 / 3 行不同，全部是 dummy 单元的 bulk 归并，**没有一比特与坐标有关**。

3. **`pwm_out` 的 5 引脚 → 4 网络可闭合：**

```
_214_/X          2 引脚 (a22o_2/X + a22o_2/B1)
u_rs_branch/net  1 引脚
u_rs_via1/net    1 引脚
u_rs_via2/net    1 引脚
合计             5 引脚（= 参考侧 pwm_out 的 5 个引脚）
```

4. **为什么不实施方案 3（重写 LEF PORT）：** 用户已禁止；且实测也独立支持该决定——
   若把 ORIGIN 预加进 PORT，路由器会再加一次，端点整体平移，把「提取错位」变成
   **真实开路**。现行 GDS 在框架 B 下 8/8 端口覆盖率 100.0%、via-aware BFS 11 次
   迭代可达 30.700 µm²。**现在的版图是对的。**

5. **`MAGIC_DEF_LABELS` 保持 0，不启用。**

---

## 4. A/B/C1 的 Via Pad 合规化修复：已保留且已证明无副作用

用户要求补充检查新几何是否引入新的间距/面积/enclosure 问题。**做完了，结果如下。**

### 4.1 几何变更摘要（layer-by-layer 与 HEAD 对比）

| 宏 | 变更层 | 变更内容 | C3/C4/D/E |
|---|---|---|---|
| `research_via1` (A) | met1 68/20, met2 69/20 | via1 焊盘 260 → 340 nm（±40 nm）；prB 未变 | **几何完全未变** |
| `research_via2` (B) | met2 69/20, met3 70/20, prB 235/4 | via2 焊盘 280 → 390 nm（±55 nm）；**prB 上沿** 5.165 → 5.195（+30 nm，随焊盘扩展） | **几何完全未变** |
| `research_branch` (C1) | met1 68/20, met2 69/20, prB 235/4 | 3 个 via1 焊盘 260 → 340 nm（±40 nm）；**prB 下沿** 4.870 → 4.830（−40 nm，随焊盘扩展） | **几何完全未变** |

形状计数：A 2/2·1/1、B 1/1·1/1·1/1、C1 1/1·3/3 —— **数量一致，只有坐标变化**。

**逐框验证「中心不动、只放大焊盘」（MEASURED）：**

```
struct_A   met1 (68/20) 4->4   center (6.000,4.000) SAME   260x260 -> 340x340 nm
           met2 (69/20) 2->2   center (6.000,4.000) SAME   260x260 -> 340x340 nm
struct_B   met2 (69/20) 3->3   center (6.000,5.000) SAME   280x280 -> 390x390 nm
           met3 (70/20) 2->2   center (6.000,5.000) SAME   330x330 -> 390x390 nm
struct_C1  met1 (68/20) 4->4   3 centers (2,5)(6,5)(10,5)   260x260 -> 340x340 nm  SAME
           met2 (69/20) 6->6   同上 3 组                   260x260 -> 340x340 nm  SAME
```

**没有任何一个 via 的中心移动，也没有任何 via 被增删。**
两条 prBoundary（235/4）是唯一「移动」的框，因为要包住放大后的焊盘。
其余层（`68/44` contact、`69/44`、prB 以外的结构）**逐框 identical**。
这独立证实了 `gen_v2_macros.py:49` 的注释「所有 via 的中心坐标与数量完全未动」。

C3/C4/D/E 的 `.gds` **文件字节变了，但几何一元未变** —— 差异只有 12 个字节，
全部落在 `BGNLIB` / `BGNSTR` 的修改/访问时间字段（偏移 18/20/22/30/32/34 与
74/76/78/86/88/90），解码后 `2026/10/29 00:29:02` → `13:45:01`。
按 layer 逐框比对（bbox 集合完全相等）确认：**C3/C4/D/E 的几何 identical to HEAD**。

### 4.2 副作用检查：9 个违规 → 0，无新增

```
A   HEAD  VIOLATIONS: 2   ->  NOW  PASS: 0 violations
B   HEAD  VIOLATIONS: 1   ->  NOW  PASS: 0 violations
C1  HEAD  VIOLATIONS: 6   ->  NOW  PASS: 0 violations
```

**这项修复消除了全部 9 个本地几何违规，且没有引入任何新违规。**
C3/C4/D/E 几何未变，`geom_drc` 原样通过。

### 4.3 全局位置一致性

```
all 21 pairwise gaps (closest first)
   5.10 um  B-C1      <-- 最小间距，仍 > 5.00 um
   5.50 um  E-A
   ...
ALL CONSTRAINTS PASS: inside core, no overlap, min gap >= 5.00 um, all N
```

七个宏的固定位置未变（`research_branch` 79.32/208.00、`via1` 33.5/208、
`via2` 64/208、`fiducial` 24/208、`near` 64/191.57、`cross` 102/188、`dense` 23.5/150）。
七宏视图一致性：prB = 金属 bbox = LEF SIZE，ORIGIN 全部正确。

---

## 5. 本地验证结果

| 检查 | 结果 |
|---|---|
| 本地验收检查（`macros/_run_all_checks.sh`） | **26/26 PASS，0 非 PASS**（含负向对照，负向对照必须失败才算通过） |
| cocotb（`test/Makefile`） | **13/13 PASS, FAIL=0, SKIP=0** |
| 宏视图一致性 | 7/7 OK（prB = metal bbox = LEF SIZE，ORIGIN OK） |
| 放置一致性 | PASS — plan / config.json / CSV / MD 四源一致 |
| 几何 DRC（A/B/C1/C3/C4/D/E） | **7/7 PASS，0 violations**（本轮重跑确认） |
| 最小宏间距 | **5.10 µm > 5.00 µm** |
| V1 黄金版本 | **未改动** —— `v1_pages_backup/tinytapeout.gds/.oas` mtime 仍为 10-28 16:17；`src/*.v` 无变更 |
| 诊断脚本 manifest | **33/33 SHA-256 校验通过** |

> 说明：`test/tb.fst` 在每次 cocotb 运行后都会被重写（本轮最后一次运行后 mtime 13:58），
> 这是仿真波形转储的固有行为，与设计状态无关。见 §9.3。

---

## 6. 预期影响（全部为 PREDICTED，不是 PASS）

### 6.1 两个修复各管各的，不得混算

第三轮 Magic DRC 的 669 条，按**致因**分成互不相交的两组：

| 组 | 条数 | 致因 | 由哪个修复处理 |
|---|---|---|---|
| LU.2 + LU.3 + nwell.4 | **576** | 窄行段内无 tap，扩散区距 tap 过远 | **OPT-A**（`FP_PRUNE_THRESHOLD`） |
| via.5a + met2.5 + via2.4a | **93** | 三个 via 宏的焊盘 enclosure 不足 | **Via Pad 合规化（A/B/C1）** |
| 合计 | 669 | | |

**OPT-A 对那 93 条 enclosure 违规没有任何影响**，反之亦然。
两者是独立的物理修复，作用在完全不同的几何上。

### 6.2 93 条 enclosure 违规的精确归属（本轮重新测定，修正旧说法）

旧报告写「93 条在宏 bbox 内」——**方向对，但归属对象说错了**。
本轮用**到最近 via 中心的一维距离**重新归属（旧法用 bbox 重叠，对 30 nm 的小框会失效）：

```
rule      n    maxdist   nearest via centre        unattributed
via.5a   49    0.1914    branch×38 / via1×11              0
met2.5   36    0.1930    branch×24 / via1×12              0
via2.4a   8    0.2005    via2×8                           0
------------------------------------------------------------
within 0.5 um of a frame-A via centre : 93 / 93
```

**93/93 全部落在三个 via 宏的焊盘上，0 条未归属，最大偏差 0.20 µm。**
坐标与 frame A 精确吻合（Magic 忽略 ORIGIN 的证据，见 `P5_R1_COORDINATE_CHAIN.md`）：
`u_rs_via1` 在 (39.50, 212.00)、`u_rs_via2` 在 (70.00, 213.00)、
`u_rs_branch` 在 81.32/85.32/89.32 @ y=213.00。

### 6.3 为什么 Via Pad 修复应当消除这 93 条（MEASURED 几何）

sky130A 的 enclosure 下限与实际焊盘余量：

| via | cut | 规则要求 | HEAD 焊盘 | HEAD 余量 | 本轮焊盘 | 本轮余量 | 结论 |
|---|---|---|---|---|---|---|---|
| via1 @ `u_rs_via1` | 0.150 | 0.060 | 0.260 | **0.055** | 0.340 | **0.095** | FAIL → PASS |
| via1 @ `u_rs_branch` | 0.150 | 0.060 | 0.260 | **0.055** | 0.340 | **0.095** | FAIL → PASS |
| via2 @ `u_rs_via2` | 0.200 | 0.065 | 0.280 | **0.040** | 0.390 | **0.095** | FAIL → PASS |

HEAD 的 via2 余量 0.040 比规则 0.065 **少 25 nm**——这是 8 条 `via2.4a` 的直接成因。
via1 少 5 nm——对应 49 条 `via.5a` + 36 条 `met2.5`。
放大后三类余量统一为 0.095 µm，**结构上不再违反**。

> **但仍是 PREDICTED。** 这是按规则算出的几何余量，不是 Magic 实际复跑结果。
> 只有第四轮 CI 的 `62-magic-drc` 才能确认 93 → 0。

### 6.4 汇总预期

| 指标 | 第三轮实测 | 预期 | 状态 |
|---|---|---|---|
| `design__lvs_error__count` | **44** | 显著下降 | PREDICTED |
| `device_difference` | 21 | → 0 | PREDICTED（必要条件已满足） |
| `net_difference` | 16 | → 4 | PREDICTED（12 个 FILLER 网络消失，4 个 R1 残段不动） |
| `property_fail` | 0 | 0 | — |
| `unmatched_device` | 1 | 不确定 | PREDICTED |
| `unmatched_net` | 1 | 不确定 | PREDICTED |
| `unmatched_pin` | 5 | 仍为 5（R3 的 2 个对称性 + 3 个 R1 相关） | PREDICTED |
| Magic DRC 576 条 LU/Nwell | 576 | → 0（**OPT-A 负责**） | PREDICTED，方向确定但数值未验证 |
| Magic DRC 93 条 Via enclosure | 93 | → 0（**Via Pad 修复负责，与 OPT-A 无关**） | PREDICTED，几何余量已满足 |

**不做任何承诺：** 上述数字均为模型预测。用户明确要求
「不要预先宣称修改 OPT-A 后哪一项必然清零」——本文件严格遵守。
**特别是：不得因为 576 和 93 都预期归零，就把它们说成「OPT-A 修好了 669」。**

---

## 7. 仍未验证的风险

| # | 风险 | 为什么无法本地验证 |
|---|---|---|
| 1 | `FP_PRUNE_THRESHOLD` 在真实 CutRows 中生效 | 无 LibreLane 3.0.14（`/nix` 不存在，`pip show librelane` 未找到） |
| 2 | 21 → 0 是否真的发生 | 无 netgen，无法复跑 LVS |
| 3 | 3 个 `conb_1` 重放后 VPB 是否仍悬空 | 取决于布局器新位置，无法预测 |
| 4 | Magic LEF reader 为何采用框架 A | 无 Magic 二进制/源码/网络 |
| 5 | 93 条 enclosure 违规是否阻断流片 | 取决于 TT 流程 Magic DRC 门限 |

---

## 8. 第四轮 CI 的本地前置条件是否具备

**具备，但有明确边界。**

- ✅ 唯一设计改动（`FP_PRUNE_THRESHOLD: 26.22`）已写入并通过 JSON 校验
- ✅ 六条前置条件全部满足（第 1 条为推断满足，已如实标注）
- ✅ 182/182 悬空 bulk 单元在删除段内的必要条件成立
- ✅ 26 项本地检查 + 13 项 cocotb + 跨视图断言全绿
- ✅ A/B/C1 的 Via Pad 修复保留，且证明消除 9 个违规、无新增
- ✅ C3/C4/D/E 原始几何未变；七宏位置、5 µm 间距、α′ 接口、LEF OBS、V1 均未变
- ⚠️ R1 **未解决**，只是诊断完成并被证明「不是 ORIGIN 问题」；第四轮 LVS 仍会有 R1 的 4 个残段
- ⚠️ 所有收益均为 PREDICTED，需要第四轮真实 CI 才能确认

---

## 9. 更新后的 Git Diff 与全部 untracked 文件

HEAD = `7135c54`（第三轮 CI 的 commit），分支 `exp/v2-2x2-research`。
**以下为工作区实况，未做任何 git add / commit / push。**

### 9.1 已跟踪文件被修改：33 个

按修改时间可以清楚地分成两批：

**第一批（08:12–08:57，P5 早期本地检查工具）—— 不是本轮 OPT-A 的产物**

| 文件 | 变更 |
|---|---|
| `macros/geom_drc.py` | +158/−? 增加几何 DRC 规则与负向对照 |
| `macros/gen_v2_macros.py` | +41/−? Via Pad 合规化（260→340 / 280→390 nm） |
| `macros/p3_gds_identity.py` | +373/−? 重写为 GT-id 栅格身份比对 |
| `macros/_run_all_checks.sh` | +20 接入新增检查 |
| `macros/_neg_gds_identity.py` | +59 新增负向对照 |
| `v2_spec/P3_MACRO_PLACEMENT_PLAN.md` | 4 行 |

**第二批（13:45–13:46，本轮重跑 `gen_v2_macros.py` 后的再生成产物）**

| 文件 | 性质 |
|---|---|
| `macros/out/struct_A.gds` / `.lef` | **真实几何变更**（via1 焊盘） |
| `macros/out/struct_B.gds` / `.lef` | **真实几何变更**（via2 焊盘 + prB 上沿） |
| `macros/out/struct_C1.gds` / `.lef` | **真实几何变更**（3× via1 焊盘 + prB 下沿） |
| `macros/out/struct_C3/C4/D/E.gds` | **仅时间戳**，几何 identical |
| `macros/out/v2_structures.gds` | 合并版，随上述更新 |
| `macros/out/v2_structures_manifest.json` | 哈希表更新 |
| `macros/out/macro_index.json` | 索引更新 |
| `macros/out/neg_bad_enclosure/too_close/too_narrow.gds` | 负向对照重新生成（仅时间戳） |
| `src/config.json` | **OPT-A 的 3 行** |
| `v2_validation/P4_PIN_PORT_CONTRACT.json` | PIN 矩形随 LEF 更新（0.06→0.10 等） |
| `v2_validation/P4_GDS_IDENTITY.json` / `.md` | 身份比对结果更新 |
| `v2_validation/P5_LEF_OBS.json` | OBS 面积随焊盘增大（全部 `obs_pin_overlap: 0`） |
| `v2_validation/P3_MACRO_BBOX.csv` | B/C1 高度 +0.030 / +0.040 |
| `v2_validation/P3_MACRO_VIEW_CONSISTENCY.json` / `.md` | 视图一致性复核 |
| `v2_validation/p3_placement.json` | 放置一致性复核 |
| `v2_validation/synth_full.log` | **仅时间/内存尾行**（`time: 0.21s → 0.19s`，hash 未变 `732736a214`） |
| `test/tb.fst` | **cocotb 波形，每次仿真都变**。HEAD 里已跟踪（`24fc6a5`），但它是派生产物 |

### 9.2 Untracked：61 个（不含 `tools/v2_ci_diagnostics/`）

**建议提交：**

| 路径 | 内容 | 大小 |
|---|---|---|
| `tools/v2_ci_diagnostics/` | 33 个脚本 + README + MANIFEST + `magic_violations.json` | 348 K |
| `v2_validation/P5_CLOSEOUT_A_PRUNE.md` | OPT-A 物理有效性 | 19 K |
| `v2_validation/P5_CLOSEOUT_B_LVS_CAUSAL.md` | LVS 因果隔离 | 29 K |
| `v2_validation/P5_DECISION_REPORT.md` | 决策报告 | 11 K |
| `v2_validation/P5_R1_COORDINATE_CHAIN.md` | **R1 八坐标链证明** | 12 K |
| `v2_validation/P5_PRECOMMIT_REPORT.md` | 本文件 | 11 K |
| `v2_validation/P5_ITEM1..7_*.md` | P5 分项报告（6 个） | 93 K |
| `macros/p5_geometry_record.py` | 几何变更记录工具 | — |
| `macros/p5_intrusion_check.py` | Via 侵入检查 | — |
| `macros/p5_intrusion_negative.py` | 侵入检查负向对照 | — |
| `macros/p5_pad_impact.py` | 焊盘影响评估 | — |
| `macros/out/intrusion_neg_controls.json` | 负向对照结果 | 748 B |
| `macros/out/neg_controls.json` | 负向对照清单 | 2.2 K |
| `macros/out/neg_*.gds`（11 个） | 负向对照版图（每个 ≤ 430 B） | — |

**建议**不**提交（遵守用户的交付约束）：**

| 路径 | 内容 | 理由 |
|---|---|---|
| `tools/v2_ci_diagnostics/` | 131 个文件 / 1.3 M，含 `sky130.tech` 186 K、`tech.json` 257 K、`__pycache__/`、`head/`、`old/`、大量一次性调试脚本（`dbg.py`、`cmp.py`、`rows.py`…） | **缓存与 PDK 导出临时物**；用户明确不提交缓存。其中有复现价值的脚本已全部迁入 `tools/v2_ci_diagnostics/` |

> `tools/v2_ci_diagnostics/` 未列入 `.gitignore`（只有其下的 `__pycache__/` 被忽略）。
> **第四轮提交时必须显式排除**，否则 `git add -A` 会把 1.3 M 调试残留一起带进去。

### 9.3 一个需要用户裁决的项

`test/tb.fst` 是 cocotb 的 FST 波形转储，每次跑仿真都会重写（本轮 13/13 PASS 后由 3053 B 变为 3179 B）。
它在 `24fc6a5` 里已被跟踪，所以本轮无法避免它出现在 diff 中。
**它不是设计产物，也不携带任何电气信息。** 建议在第四轮提交前决定：要么连同本轮一起提交，要么单独 `git rm --cached test/tb.fst` 并加进 `.gitignore`。**本轮不改，留待用户决定。**

---

## 10. 与上一版报告的差异（自我更正）

本文件初稿在 §4.1 写 `struct_B` 的 prBoundary 变的是「下沿 5165 → 5195」。
**错误。** 实测解码：

```
struct_B HEAD prB  y 1.930 .. 5.165
struct_B NOW  prB  y 1.930 .. 5.195     <- 变的是上沿，且 ORIGIN 未动
struct_C1 HEAD prB  y 4.870 .. 8.070
struct_C1 NOW  prB  y 4.830 .. 8.070    <- 变的是下沿（ORIGIN 同步 4.870→4.830）
```

两者都随焊盘向外扩展，方向正确、无重叠风险；但方向描述已在本版更正。
`struct_A` 的 prBoundary **完全未变**（初稿表格暗示它变了，已改）。

**本轮到此停止，等待第四轮 Commit + Push 的独立授权。**
