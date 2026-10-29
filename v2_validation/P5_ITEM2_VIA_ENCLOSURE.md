# Item 2 — 按完整 Via 包围规则修正 GDS，并验证所有连带影响

编写日期：2026-10-29
依据：使用中的 SKY130 Magic DRC Deck（`tools/v2_ci_diagnostics/sky130.tech`，blob `2fdf72416c5f5384415269436878940b27112409`）原文，
不是厂商文档摘要，也不是我对文档的复述。

---

## 0. 我此前建议的 0.280 µm 为什么不够

我上一轮提出的"Via1 pad 0.260 → 0.280"只满足了 `via.1a + 2*via.4a`（0.150 + 2×0.055）这一类
**基础包围**。Deck 里还有三条 `surround ... directional` 规则，它们的阈值比基础包围更严，
而且作用于**相邻的一对相对边**，不是一个方向。所以：

| 规则（Deck 原文） | 打印值 | 真实阈值 | 对 0.150 Via1 的含义 |
|---|---|---|---|
| `width v1/m1 260` | 260 | 0.260 µm（基础宽度） | pad ≥ 0.260 |
| `surround v1/m1 *m1,rm1 30 directional` | 6 | **0.085 µm** | 某一对相对边各 ≥ 0.085 |
| `surround v1/m2 *m2,rm2 30 directional` | 6 | **0.085 µm** | 同上 |
| `width v2/m2 280` | 280 | 0.280 µm | Via2 pad ≥ 0.280 |
| `surround v2/m2 *m2,rm2 45 directional` | 9 | **0.085 µm** | 某一对相对边各 ≥ 0.085 |
| `surround v2/m3 *m3,rm3 25 absence_illegal` | 5 | **0.065 µm** | 四边都需满足（更严的语义，但阈值更低） |

**对称方形 pad 的最小值**（取最严的那条，0.085）：
- Via1：0.150 + 2×0.085 = **0.320 µm**
- Via2 → M2：0.200 + 2×0.085 = **0.370 µm**

**0.280 < 0.320，所以 0.280 仍然违规。** 你的更正成立。我接受这个更正，并把
0.280 明确记为**错误方案**，不再作为候选。

---

## 1. 本轮采用的取值与依据

```python
ENCL   = 0.095      # 三条 0.085 规则 + 10 nm 余量
ENCL_M3 = 0.095     # met3.4 只需 0.065，但保持方形 pad 与一致余量
```

| Via | cut | 旧 pad | 新 pad | 新包围 | 规则 | 余量 |
|---|---|---|---|---|---|---|
| Via1 | 0.150 | 0.260 | **0.340** | 0.095 | 0.085 | +10 nm |
| Via2 → M2 | 0.200 | 0.280 | **0.390** | 0.095 | 0.085 | +10 nm |
| Via2 → M3 | 0.200 | 0.330 | **0.390** | 0.095 | 0.065 | +30 nm |

**为什么两个 landing 都取 0.390 而不是让 M3 侧只取 0.330**：
`met3.4` 的 `absence_illegal` 语义要求四边都达标，而 `directional` 只要求一对相对边。
若 M3 侧只做 0.330（正好 0.065），一旦我对 `absence_illegal` 的理解有偏差就没有余量；
做成与 M2 侧相同的对称正方形后，**四边等深 0.095，按任何一种语义解释都通过** ——
修复不再依赖我对 directional 语义的解读。这与 OpenROAD 自己在最终 GDS 里给 1018 个
via1 用的 0.320（正好 0.085 包围、DRC 干净）同量级，并额外留了加工余量。

**不变的量（科研真值前提）——已逐字节核对**：

| 结构 | via 层 | 中心 (µm) | cut (µm) | 数量 | 旧 → 新 |
|---|---|---|---|---|---|
| A | Via1 | (6.0, 4.0) | 0.150 | 1 | **完全相同** |
| B | Via2 | (6.0, 5.0) | 0.200 | 1 | **完全相同** |
| C1 | Via1 | (2.0, 5.0) (6.0, 5.0) (10.0, 5.0) | 0.150 | 3 | **完全相同** |

**只有 landing pad 变大，via cut 的尺寸、中心、数量一个都没动。**
这是"最小合规修正"的准确含义。

---

## 2. 逐条完整规则验证（含负向对照）

### 2.1 本地检查器覆盖的规则

见 `macros/geom_drc.py` 的 `RULES`：

```
m1_w/m1_s 0.140   m2_w/m2_s 0.140   m3_w/m3_s 0.300
via1_cut 0.150    via1_m1_encl 0.085   via1_m2_encl 0.085   via1_space 0.060
via2_cut 0.200    via2_m2_encl 0.085   via2_m3_encl 0.065   via2_space 0.120
via3_* 未使用且未重测 -> 间距检查显式跳过（None），不编造数字
```

### 2.2 directional 语义已修正为本轮的关键发现

旧实现把阈值转成 dbu（65）却与 µm（0.065）比较，导致**每个 via 都无条件报违规**。
计数上碰巧对了，但 B 的 legal met3.4 被误报成违规。修正后：

```python
T = threshold_um                      # µm，不是 dbu
lr = min(s['L'], s['R'])              # 这一对相对边必须都达标
bt = min(s['B'], s['T'])
bad = (lr < T - tol) and (bt < T - tol)     # 任一对达标即合法
```

**证据锚点**：第三轮 CI 的 93 个包围类盒子的规则分布是
`via.5a 49 + met2.5 36 + via2.4a 8`，**met3.4 为 0**；逐宏核对 A 23、B 8、C1 62。
B 的 Via2→M3 是 `L=0.065/R=2.000/B=0.065/T=0.065`，Magic 没报 met3.4 —— 说明
"一对相对边达标即合法"是正确语义，`max(L,R)` 和"四边都要"都不对。

### 2.3 负向对照（证明检查器确实会咬）

`macros/geom_drc.py` 的 9 条对照全部按规格表现：

| # | 构造 | 期望 | 结果 |
|---|---|---|---|
| N1 | 包围 0.055（旧值） | FAIL | PASS（正确报违规） |
| N2 | 对称 pad 0.280 | FAIL | PASS（正确报违规） |
| N3 | 对称 pad 0.320（刚好 0.085） | PASS | PASS（正确放行） |
| N4 | 对称 pad 0.310 | FAIL | PASS（正确报违规） |
| N5 | Via2→M2 包围 0.040 | FAIL | PASS |
| N6 | Via2→M3 包围 0.065（刚好） | PASS | PASS |
| N7 | Via2→M3 包围 0.060 | FAIL | PASS |
| N8 | 只有一对相对边达标（L/R=0.050，B/T=1.135） | PASS | PASS |
| N9 | 两边都不达标 | FAIL | PASS |

对照 N3 与 N4 一起确定了阈值就在 0.320，**不是我选的数字碰巧过**。

### 2.4 七个宏全部通过

```
A   PASS: 0 violations under the implemented rule subset
B   PASS: 0 violations under the implemented rule subset
C1  PASS: 0 violations under the implemented rule subset
C3  PASS: 0 violations under the implemented rule subset
C4  PASS: 0 violations under the implemented rule subset
D   PASS: 0 violations under the implemented rule subset
E   PASS: 0 violations under the implemented rule subset
```

**旧几何作为反向对照**（证明检查器不是永远 PASS）：

```
A   VIOLATIONS: 2      B   VIOLATIONS: 1      C1  VIOLATIONS: 6
```

---

## 3. 连带影响逐项核查

### 3.1 pad 放大会不会撞上既有金属？（`macros/p5_pad_impact.py`）

**必须只看"增长量"，不能看整块金属。** 整块金属与 `pwm_out` 的间隙本来就是 0，
因为 `pwm_out` 本来就接在 PIN 上 —— 那是设计意图，不是新问题。

**只取 `新几何 − 旧几何` 的差集与外来金属比较**：

| 宏 | 层 | 增长量 (µm²) | 增长 vs 外来重叠 | 最小间隙 |
|---|---|---|---|---|
| C1 | M1 | 0.1104 | **0** | 0.901 µm |
| C1 | M2 | 0.1272 | **0** | 0.991 µm |
| A | M1 | 0.0424 | **0** | 3.000 µm |
| A | M2 | 0.0424 | **0** | 2.901 µm |
| B | M2 | 0.0660 | **0** | 3.000 µm |
| B | M3 | 0.0342 | **0** | 3.000 µm |

**结论：增长部分与任何外来金属都不接触，最小间隙 0.901 µm，远大于 M1/M2 的 0.140 µm 间距规则。**
C3/C4/D/E 几何完全未变，外来金属量为 0。

> `p5_pad_impact.py` 的 `PASS` 判据是"没有**新增**短接、没有**新增**间距违规"
> （与旧几何对比），这才是"pad 放大是否引入新问题"的正确问法。

### 3.2 C1 的三个 via 会不会互相影响？

C1 三个 via 在 x=2/6/10，同一条 M1 主干（y=5）上。pad 从 0.260 增至 0.340 后：
- 相邻 pad 中心距 4.0 µm，pad 边缘间距 = 4.0 − 0.340 = **3.66 µm**
- `via1_space` 规则 0.060 µm → 余量 3.60 µm
- M2 stub 在 x=2/6/10 竖直向上，**三个 pad 之间没有任何重叠或接近**
- `via1_space` 检查：0 违规

**三个 via 互不影响。**

### 3.3 B 的 M2/M3 面积与间距是否合法？

- M3 走线宽 0.30（规则 0.30，**恰好等于，不是小于**；`width_check` 以 `< rule` 判违规，故合规）
- M3 pad 0.390 × 0.390，最窄边 = 0.390 > 0.30 ✓
- M2 走线宽 0.14（规则 0.14，同样恰等）✓
- M2↔M3 不同层，无同层间距问题
- B 的 M3 段与 M2 段在投影上重叠，但中间只有 Via2 一处落点，**无第二个连接** → 拓扑正确

面积核算：M3 面积 1.6386 µm²，与旧值一致（pad 增量在 M3 侧只体现在 prBoundary 高度 +0.030）。
`geom_drc.py` 的 `m3_w`/`m3_s` 检查 0 违规。

### 3.4 prBoundary / LEF SIZE / PIN / OBS / ORIGIN 是否同步？

| 结构 | prBoundary (µm) 旧 → 新 | SIZE 旧 → 新 | ORIGIN | LEF 已重生成 | 一致性 |
|---|---|---|---|---|---|
| A | x[0.930..9.070] y[1.930..6.870] | 8.140×4.940 | 0.930,1.930 | 是 | **未变** |
| B | y[1.930..**5.165**] → y[1.930..**5.195**] | 10.220×3.235 → **10.220×3.265** | 0.930,1.930 | 是 | **已同步** |
| C1 | y[**4.870**..8.070] → y[**4.830**..8.070] | 10.140×3.200 → **10.140×3.240** | 0.930,**4.870 → 4.830** | 是 | **已同步** |
| C3/C4/D/E | 不变 | 不变 | 不变 | 是（内容相同） | 未变 |

`gen_v2_macros.py` 的 `main()` 在**所有几何之后**由 `b.top.bbox()` 推导 prBoundary，
所以 prBoundary 自动跟随 pad 增长；`gen_lef.py` 再从同一 bbox 生成 ORIGIN/SIZE。
**这是一条单向链：几何 → prBoundary → LEF ORIGIN/SIZE。不存在手动同步，也就不存在不同步。**

**OBS 同步**：`gen_lef.py` 的规则 E 是"绘制金属 − PIN"，几何变了 OBS 会重算；
`verify_obs` 的 O1/O3/O4 + 规则 E 全部判据每次生成时重跑。

**PIN 同步**：PIN 是 access point（wire centreline）而非 pad 尺寸，所以 PIN RECT 的
0.140 尺寸不变；但因为 ORIGIN 变了（C1 的 y 从 4.870 变 4.830），
**PIN 的 LEF RECT 数值会相应平移 0.040，绝对坐标保持不变** —— 这正是正确的。

### 3.5 新 GDS 是否保留原有 via 位置与数量？

见 §1 表格：A 1 个 (6.0,4.0)、B 1 个 (6.0,5.0)、C1 3 个 (2/6/10, 5.0)，
**中心与 cut 尺寸逐字节相同**。

### 3.6 A 的独立邻线是否仍独立？

A 的邻线是 M1 在 y=6.8（宽 0.14，即 y 6.73–6.87），主结构最高到 y=4.0 的 Via1 pad 顶边 4.17。
- 邻线到主结构垂直间隙 = 6.73 − 4.17 = **2.56 µm**
- 旧值 6.73 − 4.13 = 2.60 µm
- **减少了 0.040 µm，仍远大于 0.14 的 M1 间距规则 → 独立性完好**

`geom_drc.py` 的 `M1.min_space` 检查 0 违规，`p5_intrusion_negative.py` 的 N2/N3 对照
证明"共存但分开"与"接触"能被区分开。

---

## 4. 这个修复**没有**证明什么

1. **本地 geom_drc 不是官方 deck。** 它覆盖 BEOL 宽度/间距/via 尺寸/via 包围/网格，
   **不覆盖** FEOL、密度、天线、pin、max-width/slotting。结论标记为 `LOCAL_GEOM_DRC`。
2. **本机没有 Magic 与 Netgen。** 93 个包围类错误是否全部消失，只能由第四轮 CI 判定。
3. **本轮没有触发 CI**（用户明确不授权）。
4. 七类结构的研究语义未变，但**"与旧 HEAD 逐字节相同"这个通过条件已经作废** ——
   见 Item 4 文档与 `tools/v2_ci_diagnostics/geometry_change_record.json`。

---

## 5. 复现

```bash
python3 macros/gen_v2_macros.py          # 生成 7 个新宏 GDS + manifest
python3 macros/gen_lef.py                # 重新生成 LEF（含 OBS 不变式校验）
for t in A B C1 C3 C4 D E; do python3 macros/geom_drc.py macros/out/struct_$t.gds; done
for t in A B C1; do python3 macros/geom_drc.py tools/v2_ci_diagnostics/head/struct_$t.gds; done   # 反向对照
python3 macros/p5_pad_impact.py <final.gds> <final.def> tools/v2_ci_diagnostics/head tools/v2_ci_diagnostics/pad_impact.json
python3 macros/p5_intrusion_negative.py  # 侵入检测器负向对照 12/12
```

> **基准目录是 `tools/v2_ci_diagnostics/head/`，不是 `tools/v2_ci_diagnostics/old/`。**
> `tools/v2_ci_diagnostics/old/` 是修复后用旧规则重新生成的副本（几何与 HEAD 等价、字节不同）；
> `tools/v2_ci_diagnostics/head/` 才是 `git cat-file HEAD:` 取出的原始字节。用错基准会让
> §3.1 的最小间隙与 §2.4 的反向对照全部失真。见 Item 4 文档 §6.5。
