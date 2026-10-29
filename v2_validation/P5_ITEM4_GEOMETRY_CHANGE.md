# Item 4 — GDS 几何变更清单与科研真值影响

编写日期：2026-10-29
对应交付物 (5)：**GDS 几何变更清单与科研真值影响**

本轮我修改了 `macros/gen_v2_macros.py` 的 via landing pad 尺寸（Item 2）。
这是**有意的 GDS 变更**。因此：

> **"与旧 HEAD 逐字节相同"不再可以作为通过条件。**
> 本节建立替代判据，并用可复算的证据证明科研真值未被破坏。

---

## 0. 为什么逐字节相同这个判据从一开始就是错的

这件事不只是"本轮改了所以不能用了"——它是**任何一次重新生成 GDS 都会失效**的。
证据来自本轮实测：

| 宏 | 本轮几何是否改变 | 文件长度变化 | 不同字节数 | 不同字节的位置 |
|---|---|---|---|---|
| C3 | **完全未变** | 0 | 16 | **全部在 BGNLIB/BGNSTR 日期记录内** |
| C4 | **完全未变** | 0 | 16 | **全部在 BGNLIB/BGNSTR 日期记录内** |
| D  | **完全未变** | 0 | 16 | **全部在 BGNLIB/BGNSTR 日期记录内** |
| E  | **完全未变** | 0 | 16 | **全部在 BGNLIB/BGNSTR 日期记录内** |

**四个宏的几何一个 dbu 都没动，文件却各不相同** —— 差异恰好 16 字节，全部落在
GDS 的 `BGNLIB`(0x0102) 与 `BGNSTR`(0x0502) 时间戳记录里（每处 6 个 16-bit 时间字段，
重新生成一次就换一次写入时刻）。

`_neg_gds_identity.py` 里有一条更直接的对照：把一个**未被任何扰动**的文件用
`pya` 读进来再写出去，立即产生 8 个字节差异，且全部在日期记录内：

```
pya roundtrip      diffbytes=8 outside_dates=NONE  OK
```

**结论：用文件 SHA256 判断"几何是否被改动"是不可靠的。** 它会把任何一次重新
生成都报成"几何改变"。反过来说，若用它当通过条件，唯一能通过的办法是
**永远不再生成 GDS**，这不是签核，这是把工具锁死。

---

## 1. 替代判据（三件套）

| 判据 | 内容 | 工具 | 结果 |
|---|---|---|---|
| **A. 旧几何 SHA256 冻结** | 修复前的 17 个文件全部记录 SHA256 + 字节数 | `tools/v2_ci_diagnostics/geometry_sha_pre_fix.json` | 已冻结 |
| **B. 规范化几何摘要** | 逐层、逐图形的 `(层, datatype, 形状类别, 绝对坐标)` 排序后 SHA256；多边形按缠绕/起始顶点规范化；**不读时间戳** | `macros/p5_geometry_record.py` | 见 §2 |
| **C. 声明的变更类别** | 每个宏必须落在 `GEOM_IDENTICAL` / `PAD_ONLY` 之一，且 `PAD_ONLY` 还要过两条附加条件 | `macros/p3_gds_identity.py` | PASS |

`PAD_ONLY` 的两条附加条件（这是防止"PAD_ONLY 变成随便改"的闸门）：

1. **via cut 指纹不变** —— `(层, 中心 x, 中心 y, 宽, 高)` 的有序表必须与 HEAD 完全相同。
   via cut 是这批结构的物理定义，它一变就不是"修包围"了。
2. **HEAD 旧几何必须被新几何完全包含** —— `old_region − new_region` 必须为空。
   这条把"只增不减"变成可判定命题：任何平移、缩短、删除都会留下非空差集。

（判据 C 由 `p3_gds_identity.py` 实现，但**分类本身不写在它里面**，
而是从 `tools/v2_ci_diagnostics/geometry_change_record.json` 读 —— 否则"改了什么"和
"允许改什么"就由同一个程序说了算。）

---

## 2. 逐宏变更清单

数据源：`tools/v2_ci_diagnostics/geometry_change_record.json`（脚本生成，非手写）。

| 宏 | 分类 | 文件 SHA256（HEAD → 新） | bbox 变化 (µm) | 内容变更层 | 派生变更层 |
|---|---|---|---|---|---|
| **A** | `PAD_ONLY` | `49b97b2f…` → `49e351c4…` | **无变化** [0.930,1.930,9.070,6.870] | M1, M2 | — |
| **B** | `PAD_ONLY` | `8a33381c…` → `fb2e563c…` | 上边 5.165 → **5.195** | M2, M3 | prB |
| **C1** | `PAD_ONLY` | `627b5273…` → `adf02be2…` | 下边 4.870 → **4.830** | M1, M2 | prB |
| **C3** | `GEOM_IDENTICAL` | `9e7fddd3…` → （几何同，字节仅时间戳） | **无变化** | — | — |
| **C4** | `GEOM_IDENTICAL` | `47d69188…` → （同上） | **无变化** | — | — |
| **D**  | `GEOM_IDENTICAL` | `210a694a…` → （同上） | **无变化** | — | — |
| **E**  | `GEOM_IDENTICAL` | `8d4fb6bb…` → （同上） | **无变化** | — | — |

`OTHER` 分类：**0 个**。没有任何一处变化是"无法归入声明类别"的。

### 2.1 面积增量（可核算）

| 宏 | 层 | 面积增量 (µm²) |
|---|---|---|
| A | M1 / M2 | 0.0480 / 0.0480 |
| B | M2 / M3 | 0.0737 / 0.0432 |
| C1 | M1 / M2 | 0.1440 / 0.1440 |
| C3/C4/D/E | — | 0 |

这些数字可以用手工算式核对。以 A 为例：Via1 cut 0.150，pad 从 0.260 增至 0.340，
单边增量 0.040，一层 pad 的面积增量 = 0.340² − 0.260² = 0.1156 − 0.0676 = **0.0480 µm²** ✓
M1 与 M2 各一块，故两层都是 0.0480。

B 的 Via2：pad 0.280 → 0.390，M2 侧增量 = 0.390² − 0.280² = 0.1521 − 0.0784 = **0.0737 µm²** ✓
M3 侧：0.330 → 0.390，增量 = 0.1521 − 0.1089 = **0.0432 µm²** ✓

C1 三个 Via1：3 × 0.0480 = **0.1440 µm²** ✓

**面积增量与 §3 的 pad 尺寸一一吻合，说明变化确实只来自 pad，没有夹带别的形状。**

### 2.2 prBoundary 为什么算"派生变更"

B 与 C1 的 prBoundary 变了，但这是**正确行为**，不是内容变更：

- `gen_v2_macros.py` 的 `main()` 在**所有几何绘制完之后**由 `b.top.bbox()` 推导 prBoundary；
- `gen_lef.py` 再从同一 bbox 生成 `ORIGIN` / `SIZE`。

所以链是 **几何 → prBoundary → LEF ORIGIN/SIZE**，单向、无手动同步点，
也就不存在"忘记同步"。分类里把 prB 单列为 `derived_changes`，是为了让读者
看到它**没有被忽略**，而不是把它当成实质变化。

---

## 3. 科研不变量：逐条复核

判据 C 只保证"变化属于 PAD_ONLY 类"，它**不保证**各结构的研究语义还在。
下面把每个结构的科研定义写成可执行断言并在新几何上重跑
（`p5_geometry_record.py` 的 `invariants()`）。

### 3.1 结构 A — 单 via 连接

| 不变量 | 值 | 判定 |
|---|---|---|
| Via1 数量 | 1 | ✓ |
| Via1 中心 | (6.000, 4.000) µm | ✓ 与 HEAD 完全相同 |
| Via1 cut | 0.150 × 0.150 µm | ✓ |
| M1 图形数 | 4 | ✓（含独立邻线） |

**独立邻线**：M1 在 y=6.8（宽 0.140，即 6.730–6.870）。主结构最高点是 Via1 pad 上边
4.000 + 0.170 = 4.170。间隙 = 6.730 − 4.170 = **2.560 µm**（旧值 2.600，减少 0.040，
即 pad 单边增量）。**2.560 µm ≫ 0.140 µm 的 M1 间距规则 → 邻线仍然独立。**
`geom_drc.py` 的 `M1.min_space` 在新几何上 0 违规。

### 3.2 结构 B — Via1→Via2 串联

| 不变量 | 值 | 判定 |
|---|---|---|
| Via1 数量 | 0 | ✓（B 是纯 Via2 结构） |
| Via2 数量 | 1 | ✓ |
| Via2 中心 | (6.000, 5.000) µm | ✓ |
| Via2 cut | 0.200 × 0.200 µm | ✓ |
| M2 图形数 / M3 图形数 | 3 / 2 | ✓ 与 HEAD 相同 |

### 3.3 结构 C1 — 分支（一个源三个负载）

| 不变量 | 值 | 判定 |
|---|---|---|
| Via1 数量 | 3 | ✓ |
| Via1 中心 | (2.000, 5.000) (6.000, 5.000) (10.000, 5.000) µm | ✓ 与 HEAD 完全相同 |
| Via1 cut | 3 × 0.150 × 0.150 µm | ✓ |
| M1 图形数 / M2 图形数 | 4 / 6 | ✓ |

三个 via 同处 y=5 的 M1 主干；pad 增至 0.340 后相邻 pad 边缘间距
= 4.000 − 0.340 = **3.660 µm** ≫ `via1_space` 0.060 µm。**互不影响。**

### 3.4 结构 C3 — 八条独立导体（**必须完全保留**）

| 不变量 | 值 | 判定 |
|---|---|---|
| M1 导体数 | **8** | ✓ |
| Via1 / Via2 数量 | 0 / 0 | ✓（八条导体彼此不连通） |
| 导体中心 y (µm) | 1.000, 1.280, 3.420, 3.760, 5.900, 6.320, 8.460, 9.100 | ✓ |
| 间距阶梯 (µm) | 0.140, 2.000, 0.200, 2.000, 0.280, 2.000, 0.500 | ✓ |

`eight_independent = True`。**C3 几何分类为 `GEOM_IDENTICAL`，逐图形摘要与 HEAD 相同。**
这是最强的可能结论 —— 不是"我觉得没变"，是"逐图形摘要相等"。

### 3.5 结构 C4 — 无 via 交叉（**必须完全保留**）

| 不变量 | 值 | 判定 |
|---|---|---|
| M1 图形数 | 1 | ✓ |
| M2 图形数 | 1 | ✓ |
| Via1 + Via2 数量 | **0** | ✓ **`crossing_has_no_via = True`** |

分类 `GEOM_IDENTICAL`。交叉处无任何 via，M1 与 M2 在交叉点**不连通** —— 这正是
该结构要演示的"同点不同层、无连接"。

### 3.6 结构 D — 五级线宽阶梯（**必须完全保留**）

| 不变量 | 值 | 判定 |
|---|---|---|
| M1 线宽档位 (µm) | **0.140, 0.200, 0.300, 0.500, 1.000** | ✓ **5 档** |
| `five_steps` | True | ✓ |
| M1/M2/M3 图形数 | 5 / 5 / 3 | ✓ |
| via 数量 | 0 | ✓ |

分类 `GEOM_IDENTICAL`。

### 3.7 结构 E — 对准标记（**必须完全保留**）

| 不变量 | 值 | 判定 |
|---|---|---|
| M1 图形数 / M2 图形数 | 3 / 3 | ✓ |
| M1 与 M2 的矩形集合 | **完全相同** | ✓ **`m1_equals_m2 = True`** |
| via 数量 | 0 | ✓ |

分类 `GEOM_IDENTICAL`。M1 与 M2 图形重合但无 via → 两层对准标记，
可用于量测层间套刻误差，且**不产生电气连接**。

---

## 4. 外部路由侵入检测（独立进行，不依赖 `route__drc_errors`）

任务明确要求：**"最终 GDS 的外部路由侵入检测必须独立进行，不能只依据
`route__drc_errors=0` 判断没有外来 wire/via。"**

### 4.1 为什么 `route__drc_errors=0` 不够

该数值只回答"有没有违反间距规则"。路由器完全可以在宏 OBS 之外、或以**合法间距**
在宏足迹内放图形 —— 这不产生任何 DRC 错误，却可能改变研究结构的电气含义。
所以必须直接比对几何。

### 4.2 检测器怎么做到"独立"

`macros/p5_intrusion_check.py`：

- **不读** `route__drc_errors`
- **不读** 路由器报告
- **不读** LEF OBS
- 只读两份几何：最终 GDS，以及**每个宏自己的 GDS**（足迹取自宏自己的
  `prBoundary` 235/4，不用 LEF —— 这样对旧几何与新几何都成立）

判据分三层，互不混淆：

1. `foreign` — 足迹内最终 GDS 有、而宏自身没有的图形（"有别人在这里画了东西"）
2. `gap` — 该层 foreign 与宏自身同层金属的最小距离（> 0 = 物理不接触）
3. `contact` — gap ≈ 0（≤ 5 nm）即电气接触，再分：
   - 接触点落在 **LEF PIN 内** = 设计意图内的网络连接（如 `pwm_out` 接 A/B/C1）
   - 接触点落在 **非 PIN 金属** = 结构被外来网线改接 = **污染**

**通过判据只看第 3 层的污染项。**

### 4.3 结果（对第三轮最终 GDS，以 HEAD 几何为基准）

```
research_branch  [C1] x[ 80.250..  90.390] y[212.870..216.070] COEXIST
     M1     foreign 0.7098 um2  gap=2.871 um
     M2     foreign 0.4914 um2  gap=0.000 um  CONTACT on PIN x1 (intended net)
     M3     foreign 0.5476 um2  gap=n/a  (macro has no M3 shape)
     M4     foreign 2.8464 um2  gap=n/a
     Via3   foreign 0.0400 um2  gap=n/a
research_cross   [C4] CLEAN
research_dense   [D ] COEXIST (只有 M4 = PDN stripe 经过)
research_fiducial[E ] CLEAN
research_near    [C3] CLEAN
research_via1    [A ] COEXIST (只有 M4 经过)
research_via2    [B ] COEXIST (M2 foreign 0.0324 um2, gap=5.001 um)

layers with foreign geometry: 8
layers polluting structures:  0
VERDICT: PASS - no off-PIN contact
```

**关键点：**

- **0 个污染。** 唯一的电气接触是 C1 的 M2 pad ↔ `pwm_out`，落在 PIN 上 —— 这是设计意图。
- C4/C3/E **完全没有外来图形**（CLEAN）—— 三个最需要纯净的结构（交叉、八导体、对准标记）
  在真实最终版图里一个外来图形都没有。
- A/D 只有 M4（PDN 竖条）经过，宏本身没有 M4，属"纯共存"。
- B 的 M2 foreign 距宏金属 **5.001 µm** —— 注意这个值：检测器的搜索上限是 20 µm，
  所以 5.001 是真实间隙，不是"≥5 饱和"。

### 4.4 另外两个独立确认

| 检查 | 工具 | 结果 |
|---|---|---|
| 哪个网络碰到哪个 PIN | `tools/v2_ci_diagnostics/verify_pin_contact.py` | `total_shorted_pins = 0` —— 没有任何 PIN 被多于一个网络覆盖 |
| 外来图形归属哪个单元 | `intrusion_attrib.py` | 8 个外来层全部是 `TOP_LEVEL_DIRECT`（18537 个层次节点里 0 个覆盖它们）|

`pwm_out` 是**唯一**接触到任一 PIN 的网络。也就是说 C1 的"一源三负载"没有被外来网络
改动：三个分支仍然只由 `pwm_out` 驱动。

### 4.5 检测器自身的有效性验证

一个只会说 PASS 的检测器毫无价值。两条独立验证：

**(a) 12 条合成负向对照**（`macros/p5_intrusion_negative.py`）

| 用例 | 构造 | 期望 | 结果 |
|---|---|---|---|
| N1 | 足迹内只有宏自己 | clean | PASS |
| N2 | 足迹内有远处的合法外来线 | 共存，gap ∈ (0.5, 2.5) | PASS（gap = 1.401）|
| N3 | 外来线接到宏的非 PIN 金属 | **POLLUTED** | PASS（正确报污染）|
| N4 | 外来线接到宏的 PIN | 合法连接 | PASS |
| N5 | 最终 GDS 少了宏的一段金属 | missing | PASS |

12 条断言全部通过。N2 的 gap 必须落在开区间内 —— 这条专门防"搜索上限太低导致
所有 gap 都饱和成同一个值"（本轮确实修过这个 bug：上限曾是 5.0 µm，
而 B 的真实间隙正好也是 5.000 µm，无法区分"真 5 µm"与"≥5 µm"）。

**(b) 几何锁定的交叉验证** —— 用旧几何去比新几何

把检测器的基准换成"旧宏几何"，再对同一份最终 GDS 运行（该最终 GDS 是用旧几何生成的）：

- 仍然 **0 污染**
- 但出现 6 个 `missing` 层，且数值**恰好等于 pad 增长量**：
  C1 M1 0.1104、C1 M2 0.1272、A M1/M2 各 0.0424、B M2 0.0660、B M3 0.0342

这证明检测器**不是**恒真：它精确量到了两边几何的差，而且差值可解析核对。
`missing` = **完整 pad 矩形增量 − pad 环与宏自身导线重叠的边条**。
下面每个数字都先由 `tools/v2_ci_diagnostics/measure_ring.py` 从几何直接量出，再与闭式算式对照：

| 宏/层 | 完整 pad 环 (µm²) | 被导线吃掉的边条 | 单 via 净增量 | via 数 | 净增长 | 记录值 |
|---|---|---|---|---|---|---|
| A M1 | 0.0480 | 0.140×0.040 = 0.0056（底边） | 0.0424 | 1 | **0.0424** | 0.0424 ✓ |
| A M2 | 0.0480 | 0.040×0.140 = 0.0056（右边） | 0.0424 | 1 | **0.0424** | 0.0424 ✓ |
| C1 M1 | 0.0480 | 2×0.0056 = 0.0112（左右两边） | 0.0368 | 3 | **0.1104** | 0.1104 ✓ |
| C1 M2 | 0.0480 | 0.0056（**只有**顶边一条） | 0.0424 | 3 | **0.1272** | 0.1272 ✓ |
| B M2 | 0.0737 | 0.140×0.055 = 0.0077（底边） | 0.0660 | 1 | **0.0660** | 0.0660 ✓ |
| B M3 | 0.0432 | 0.030×0.300 = 0.0090（右边） | 0.0342 | 1 | **0.0342** | 0.0342 ✓ |

为什么 C1 的 M1 与 M2 单 via 数不同：两者用同一个 Via1 pad，但宏自身导线走向不同。
M1 是**水平主干** (0.93,4.93)-(11.07,5.07)，同时压住 pad 环的左右边条；
M2 是**竖直 stub** (5.93,4.93)-(6.07,7.07)，只压住顶边条。
所以 M1 每个 via 净 0.0368、M2 每个 via 净 0.0424。

**六个数全部与闭式算式吻合到 1e-4 µm²。** 这同时证明了两件事：
变化确实只来自 pad（没有夹带别的形状），以及检测器量的是真实几何。

（注意与 §2.1 的 `area_delta_um2` 不同：那里是**矩形面积和**的差，这里是**合并后区域**的差，
后者会扣掉与既有多边形的重叠，所以略小。两个口径都给出，是因为它们回答不同的问题：
前者"pad 放大了多少"，后者"净新增了多少金属"。）

---

## 5. pad 放大是否引入新的短接或间距问题

判据：**只能看"增长量"，不能看整块金属。** 整块金属与 `pwm_out` 的间隙本来就是 0，
因为 `pwm_out` 本来就接在 PIN 上 —— 那是设计意图，不是新问题。

`macros/p5_pad_impact.py` 现在把"增长量"作为独立字段固化进输出：

| 宏 | 层 | 增长量 (µm²) | 增长 vs 外来金属重叠 | 增长 vs 外来最小间隙 |
|---|---|---|---|---|
| C1 | M1 | 0.1104 | **0.00000** | **0.901 µm** |
| C1 | M2 | 0.1272 | **0.00000** | **0.991 µm** |
| A | M1 | 0.0424 | 0.00000 | 3.000 µm |
| A | M2 | 0.0424 | 0.00000 | 2.901 µm |
| B | M2 | 0.0660 | 0.00000 | 3.000 µm |
| B | M3 | 0.0342 | 0.00000 | 3.000 µm |

```
new shorts:            0
new spacing violations: 0
growth regions touching foreign metal: 0
VERDICT: PASS
```

**增长部分与任何外来金属都不接触，最小间隙 0.901 µm** —— 是 M1/M2 间距规则
（0.140 µm）的 6.4 倍。**pad 放大没有引入新的短接或间距问题。**

---

## 6. 本轮**没有**证明什么（明确边界）

1. **本机没有 Magic 与 Netgen。** 93 个包围类 DRC 错误是否全部消失，只能由第四轮 CI 判定。
   本地 `geom_drc.py` 只是"实现了 Deck 里那几条 BEOL 规则"的检查器，**不是官方 deck**。
2. **没有触发 CI。** 本轮不授权。
3. **`GEOM_IDENTICAL` 只说明几何相同**，不说明这七个结构在最终版图里的电气行为 ——
   那属于 LVS 的范围（见 Item 3 文档，LVS 仍有 3 个独立根因未解决）。
4. **侵入检测的足迹口径是 `prBoundary`。** prBoundary 之外的邻近区域未纳入；
   本检测回答的是"结构内部有没有被改"，不是"结构周围有没有别的线"。
5. **`tools/v2_ci_diagnostics/old/` 快照与 HEAD 并非同一批字节**（快照是修复后重新生成的副本，
   几何与 HEAD 完全一致但时间戳不同）。为此本轮的基准已改用 **`git cat-file HEAD:`
   提取的原始字节**（`tools/v2_ci_diagnostics/head/`），并用规范化摘要证明快照与 HEAD 几何等价
   （7/7 相同）。这条记下来，是因为"拿错基准"会让上面所有结论失效。

---

## 7. 新的通过条件（供第四轮 CI 使用）

替代"逐字节相同"的判据，完整表述：

> **P5 几何通过条件**
> 1. 每个宏必须被分类为 `GEOM_IDENTICAL` 或 `PAD_ONLY`；任何 `OTHER` → FAIL。
> 2. `GEOM_IDENTICAL` 宏：与 HEAD 的逐图形规范化摘要必须相等，
>    且原始字节差必须全部落在 `BGNLIB`/`BGNSTR` 日期记录内。
> 3. `PAD_ONLY` 宏：
>    a. via cut 的 `(层, 中心, 尺寸)` 有序表与 HEAD 完全相同；
>    b. `HEAD 几何 − 新几何 = ∅`（只增不减）；
>    c. 研究不变量全部成立（§3）。
> 4. 最终 GDS 的外部侵入检测：`layers_polluting == 0`，
>    且 `total_shorted_pins == 0`。
> 5. pad 增长部分对外来金属：重叠 = 0。

以上五条由 `bash macros/_run_all_checks.sh` 中的
`p5_geometry_record.py` / `p3_gds_identity.py` / `p5_intrusion_check.py` /
`p5_pad_impact.py` 四条自动判定，并配 `_neg_gds_identity.py` 与
`p5_intrusion_negative.py` 两组负向对照。

---

## 8. 复现

```bash
# 1. 从 HEAD 提取权威旧几何（Windows 侧 git，WSL 下 git 读不到此 worktree）
cd <repo> && for t in A B C1 C3 C4 D E; do
  git cat-file -p HEAD:macros/out/struct_$t.gds > tools/v2_ci_diagnostics/head/struct_$t.gds
done

# 2. 生成新宏 + LEF
python3 macros/gen_v2_macros.py
python3 macros/gen_lef.py

# 3. 几何变更记录（含研究不变量）
python3 macros/p5_geometry_record.py

# 4. 按声明类别判定（含 PAD_ONLY 的包含性与 via 指纹）
python3 macros/p3_gds_identity.py
python3 macros/_neg_gds_identity.py     # 负向对照

# 5. 独立侵入检测（需要第三轮最终 GDS/DEF）
python3 macros/p5_intrusion_check.py <final.gds> <final.def> \
        tools/v2_ci_diagnostics/intrusion_check.json tools/v2_ci_diagnostics/head
python3 macros/p5_intrusion_negative.py # 12 条负向对照
python3 macros/p5_pad_impact.py <final.gds> <final.def> \
        tools/v2_ci_diagnostics/head tools/v2_ci_diagnostics/pad_impact.json

# 6. 一键全量
bash macros/_run_all_checks.sh
```
