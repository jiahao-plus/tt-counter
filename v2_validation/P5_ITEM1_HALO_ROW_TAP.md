# Item 1 — CutRows / Tap 配置：官方入口、失效机理与覆盖收敛

编写日期：2026-10-29
依据：第三轮官方 CI（Commit `7135c54311a68b62b998002e8f396f06725882e9`，Run `40726887237`）的真实
`runs/wokwi/` 产物 + librelane 3.0.9 wheel（SHA256 `c18474eaeb409d7eff27ff6d5e5eaab4eb849616894d0c082ed7eb315dc23d28`）。

---

## 0. 先纠正我此前的两处错误

| 我此前的说法 | 事实 | 证据 |
|---|---|---|
| "没有控制 cut_rows halo 的配置入口" | **错**。LibreLane 有 `FP_MACRO_HORIZONTAL_HALO` / `FP_MACRO_VERTICAL_HALO`，且 `cut_rows.tcl` 直接把它们作为 `-halo_width_x/-halo_width_y` 传入 | `librelane/scripts/openroad/cut_rows.tcl` |
| "`FP_PRUNE_THRESHOLD` 在当前版本没有接线" | **错**。3.0.9 的 `cut_rows.tcl` 有 `append_if_exists_argument arg_list FP_PRUNE_THRESHOLD -row_min_width`；只是本次运行该值为 `None` | 同上 + `resolved.json` |
| "LU.2/LU.3/nwell.4 共 576 个" | **错**。576 = 562 (LU.2+LU.3) + 14 (nwell.4)。另 93 个是 via enclosure，不属于这一类 | `magic_tally.py`，见 §4 |

---

## 1. 本轮实际生效的配置（从 `resolved.json` 读出，不是文档推测）

| 变量 | 值 | 来源 | 是否用户可覆盖 |
|---|---|---|---|
| `FP_MACRO_HORIZONTAL_HALO` | `10` µm | PDK 默认 | **是**（`Decimal`，无 `pdk` 标记） |
| `FP_MACRO_VERTICAL_HALO` | `10` µm | PDK 默认 | **是**（同上） |
| `FP_PRUNE_THRESHOLD` | `None` | PDK 默认 | **是**（`Optional[Decimal]`，`pdk=True` → 可覆盖） |
| `FP_TAPCELL_DIST` | `13` µm | PDK 默认 | **是**（`Optional[Decimal]`，`pdk=True` → 可覆盖） |
| `FP_SIZING` | `absolute` | 仓库 `src/config.json` | — |
| `FP_OBSTRUCTIONS` | `None` | 默认 | — |

结论：**四个变量全部可覆盖**。`pdk=True` 的含义是"有 PDK 默认值"，不是"锁定不可改"。

`src/config.json` 里**没有任何** halo / prune / tapcell 设置 —— 全部沿用 PDK 默认。

---

## 2. `cut_rows` 的真实行为（已对着真实 DEF 逐行验证）

### 2.1 已验证模型

```
keep-out  = [px, px + SIZE_w] × [py, py + SIZE_h]        ← LEF ORIGIN 被忽略
           再向外扩 (halo_x, halo_y)
row       = [2.720 + i*2.720, +2.720), i = 0..80
row 被阻挡 ⟺ 该行的 y 区间与 keep-out 的 y 区间相交
keep-out 的 x 向外取整到整站点（左 floor、右 ceil），站点宽 0.460，原点 x=2.760
被挡区间合并，在 [0, 716) 内取补 = 行段
最后剪掉 ≤ 4 站点（≤ 1.84 µm）的碎片
```

**验证结果**（`tools/v2_ci_diagnostics/halo_matrix.py`）：

```
model segments = 114,  real = 114
model sites    = 53872, real = 53872
PER-ROW EXACT MATCH: True
```

**逐行完全一致**，不是总量相符。这个模型可以当作 cut_rows 的代理来评估配置。

> **LEF ORIGIN 被忽略**这一点很重要：`cut_rows` 用 `placement + [0, SIZE]`，
> 而实际 GDS 内容在 `placement + [ORIGIN, ORIGIN+extent]`。
> 两者是不同的坐标系，DRC 必须用后者（见 `geometry_change_record`）。

### 2.2 Tap 锚定规则（从 997 个真实 tap 反推）

```
O = round(FP_TAPCELL_DIST / 0.46) = round(13/0.46) = 28 站点 = 12.88 µm
段内锚点：left + O·(2k + p)，p ∈ {1,2}，相位逐行交替 → 相邻行错开 O
行内间距：25.76 µm (774 处) 与 12.88 µm (135 处)
```

**推论**：一个行段只有在 `width > 2·O` 时才可能获得 tap。
实测边界：`n ≤ 24 站点 → 0 个 tap`；`n = 111 站点 → 有 tap`。与 `2O = 56` 自洽。

### 2.3 26 个零 tap 行段的来源

三处宏 halo 造成的细长碎片：

| 行段 | x 范围 (µm) | 行数 | 宽 (µm) |
|---|---|---|---|
| 左碎片 A | 2.76 – 13.34 | 10 | 10.58 |
| 左碎片 B | 2.76 – 13.80 | 10 | 11.04 |
| 中碎片 | 84.18 – 92.00 | 6 | 7.82 |
| **合计** | | **26 行段 / 572 站点** | |

这三处都 `< 25.76 µm`，因此 tapcell 一个都放不进去。
**这就是 562 个 LU.2/LU.3 与 12 个真正悬空的 `FILLER_*/VPB` 的几何根因。**
（`.rpt` 里 `FILLER_*/VPB` 共 13 行，但其中 `FILLER_53_9/VPB` 是 R1 的命名问题，
不是悬空 —— 见 `P5_ITEM3_LVS_ROOTCAUSE.md` §1.4。）

---

## 3. 方案比较（全部用 §2.1 的已验证模型计算）

| 方案 | 配置 | 行段 | 可用站点 | 零 tap 行段 | 面积损失 | 宏是否移动 |
|---|---|---|---|---|---|---|
| **现状** | halo 10/10，prune None，dist 13 | 114 | 53872 | **26** | 0 % | — |
| **OPT-A（推荐）** | halo 10/10，**prune 25.76**，dist 13 | 88 | 53300 | **0** | **1.06 %** | 不移动 |
| OPT-B | **halo 19/10**，prune None，dist 13 | 88 | 52626 | **0** | 2.31 % | 不移动 |
| OPT-C | halo 10/10，prune None，**dist 3.5** | 114 | 53872 | **0** | 0 % | 不移动 |

### 为什么推荐 OPT-A

1. **零 tap 行段 → 0**，且结果在 `FP_PRUNE_THRESHOLD ∈ [11.05, 51.06]` 上是**平坦的**
   —— 取 25.76 还是 11.05 结果完全相同（88 段 / 53300 站点 / 0 零 tap）。
   我取 **25.76**，因为它等于 `2·FP_TAPCELL_DIST`，语义上直接表达"剪掉注定拿不到 tap 的段"。
2. 最小存活行段 **51.06 µm**，远大于 25.76，不会引入新的边缘碎片。
3. **宏坐标完全不动** → 满足"固定研究宏保留可追溯坐标"。
4. 容量代价 1.06 % 可忽略：核心面积 72564.6 µm²，实际 stdcell 只占 **5247.53 µm² = 7.28 %**；
   `cut_rows`（第 18 步）早于 placement（第 28/34 步），不会驱逐已放置单元。
5. 只有一个变量变化，回归面最小。

### 为什么不选 B / C

- **B（halo 19）**：同样能清零，但面积损失是 A 的 2.2 倍，且改动了会影响
  PDN/布线避让的 halo，副作用面更大。
- **C（dist 3.5）**：面积零损失，但 tap 数量从 997 涨到约 **3294**（+230 %）。
  这会给 tapcell 插入与后续布线带来新的 DRC 风险，而且不解决"Halo 碎片"这个根因，
  只是把 tap 塞进了本来就不该存在的窄条里。用增加 2300 个物理单元换取同样的覆盖，性价比最差。

### 明确不做

- 不把 halo 设为 0（用户明确禁止；且会让宏紧贴标准单元行，PDN/布线风险不可控）
- 不移动任何宏、不把宏移出 Core
- 不改 `FP_TAPCELL_DIST` 与 halo（OPT-A 的前提下都不需要）

---

## 4. `FP_PRUNE_THRESHOLD` 的语义确认

`librelane 3.0.9` 的 `cut_rows.tcl`：

```tcl
append_if_exists_argument arg_list FP_PRUNE_THRESHOLD -row_min_width
```

`steps/openroad.py` 中该变量的文档字符串：

> "If specified, all rows smaller in width than this value will be removed.
>  This helps avoid 'islets' of cells that are hard to route and connect to PDNs."

所以 `-row_min_width` 是"**小于**该宽度就删"。我用 `>=` 保留、`<` 删除实现，与之相符。

**注意**：本轮 `FP_PRUNE_THRESHOLD = None`，但 DEF 里确实出现了"≤4 站点被剪掉"的现象
—— 那是 `cut_rows` 自身的内部行为，与 `FP_PRUNE_THRESHOLD` 无关。
设置该变量会在内部剪枝之后**再**按宽度剪一次，两者不冲突。

---

## 5. 与 Item 2（pad 修复）的交互

**已验证：零交互。** pad 变大后 B 高 3.235→3.265、C1 下沿 4.870→4.830，
但 `cut_rows` 用的是**整站点取整**后的边界：

```
旧几何 (halo 10/10)：segs=114  sites=53872  zero-tap=26
新几何 (halo 10/10)：segs=114  sites=53872  zero-tap=26
新几何 (prune 25.76)：segs=88  sites=53300  zero-tap=0
```

行段集合**逐段完全相同**（`set(old) ^ set(new) = ∅`）。
0.03/0.04 µm 的增长在 0.46 µm 站点栅格上没有跨越任何边界。

---

## 6. 残余风险（必须随结果声明）

1. **OPT-A 把零 tap 行段清零，但不等价于 LVS 必然通过。**
   tap/row 类 Magic DRC（`LU.3` 342 + `LU.2` 220 + `nwell.4` 14 = **576**）
   与 12 个真正悬空的 `FILLER_*/VPB` 应当消失；
   但 LVS 还有**两类与 tap 无关的根因**（见 `P5_ITEM3_LVS_ROOTCAUSE.md`），
   它们不受 OPT-A 影响：
   - **R1** `MAGIC_DEF_LABELS = False` 导致 DEF 网名未写进 Magic
     （对应 `unmatched_net` 1 项、`unmatched_pin` 5 项中的 3 项）
   - **R3** `uio_out[7]` / `uio_oe[2]` 对称性歧义
     （对应 `unmatched_pin` 5 项中的 2 项）

   反过来，**R2（`device_difference = 21`、`unmatched_device = 1`）确实受 OPT-A 影响**
   —— 它就是 VPB 悬空拆碎物理单元的直接结果，零 tap 行段清零后应当归零。
2. **模型是代理，不是官方实现。** 虽然 114/53872 逐行精确复现，但若 LibreLane
   版本或 PDK 的 `cut_rows` 实现变化，需要重新验证。
3. **未在本地实际运行过带新配置的流程**（本地 openroad 是 headless 精简版，
   不含 `cut_rows`/`tapcell`）。OPT-A 的效果必须在第四轮官方 CI 上确认。
4. **`FP_PRUNE_THRESHOLD` 从未在本次运行中被显式设置过**，其行为依据是源码与文档，
   不是实测。平坦区 `[11.05, 51.06]` 的结论来自模型，对取值不敏感这一点降低了该风险。

---

## 7. 待批准的配置改动（**尚未写入 `src/config.json`**）

```json
{
  "FP_PRUNE_THRESHOLD": 25.76
}
```

仅此一项。不改 halo、不改 tapcell_dist、不移动任何宏。
