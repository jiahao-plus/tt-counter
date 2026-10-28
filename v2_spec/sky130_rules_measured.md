# SKY130 精确设计规则（从真实 PDK 文件实测提取）

来源（**非记忆、非文档猜测**）：
- `/root/openroad-flow-scripts/flow/platforms/sky130hd/drc/sky130hd.lydrc`
- `/root/openroad-flow-scripts/flow/platforms/sky130hd/lef/sky130_fd_sc_hd.tlef`

提取脚本：`macros/_extract_rules.py`、`_extract_drc.py`、`_extract_drc2.py`、`_extract_drc3.py`
日期：2026-10-28

> 这些是所有研究宏的**合法取值依据**。密度对照结构只能用这里列出的值，
> 不得使用虚构参数。

---

## 1. 金属最小宽度（LEF + DRC 双确认）

| 层 | min width | 来源行 |
|---|---|---|
| li1 | 0.17 µm | tlef `LAYER li1 WIDTH 0.17` |
| **met1** | **0.14 µm** | tlef + lydrc:470 `m1.1` |
| **met2** | **0.14 µm** | tlef + lydrc:527 `m2.1` |
| **met3** | **0.30 µm** | tlef + lydrc:575 `m3.1` |
| met4 | 0.30 µm | tlef |
| met5 | 1.60 µm | tlef |

## 2. 金属最小间距

| 规则 | 值 | 出处 |
|---|---|---|
| **m1 min spacing** | **0.14 µm** | lydrc:475 `m1.2` |
| m1 spacing to wide m1 (>3 µm) | 0.28 µm | lydrc:477 `m1.3ab` |
| **m2 min spacing** | **0.14 µm** | lydrc:532 `m2.2` |
| m3 min spacing | 0.30 µm（同 width 规则族） | lydrc 邻域 |

> ⚠️ **注意 `huge_m1` 例外**：宽度 > 3 µm 的 M1 与普通 M1 需要 **0.28 µm** 间距。
> 密度对照结构若做宽线，必须用 0.28 而非 0.14。

## 3. Via 规则（精确值）

### Via1（M1–M2）
| 规则 | 值 | 出处 |
|---|---|---|
| via 尺寸 | **0.15 µm**（正方形） | lydrc:507 `via.4a` 的 `edges.without_length(0.15)` |
| m1 enclosure of 0.15 via | **0.055 µm** | lydrc:507 |
| m1 enclosure of 0.23 via | 0.03 µm | lydrc:508 |
| m1 enclosure（两对边） | 0.085 µm（projection） | lydrc:509 |
| m1 enclosure（projection 通用） | 0.04 µm | lydrc:520 |

### Via2（M2–M3）
| 规则 | 值 | 出处 |
|---|---|---|
| via2 尺寸 | **0.20 µm**（未在 areaid 内）/ 0.21 µm 通用 | lydrc:557 / 567 |
| **via2 min spacing** | **0.20 µm** | lydrc:559 `via2.2` |
| via2 spacing（替代） | 0.18 µm | lydrc:568 `via2.12` |
| **m2 enclosure of via2** | **0.04 µm** | lydrc:560 `via2.4` |
| m2 enclosure of 1.5µm via2 | 0.14 µm | lydrc:561 `via2.4a` |
| m2 enclosure（两对边） | 0.085 µm | lydrc:564 `via2.5` |
| m2 enclosure（替代） | 0.035 µm | lydrc:570 `via2.14` |
| **m3 enclosure of via2** | **0.065 µm** | lydrc:588 `m3.4` |

### Via3（M3–M4）
| 规则 | 值 | 出处 |
|---|---|---|
| via3 尺寸 | 0.20 / 0.21 µm | lydrc:606 / 615 |
| **via3 min spacing** | **0.20 µm** | lydrc:608 `via3.2` |
| via3 spacing（替代） | 0.18 µm | lydrc:616 `via3.12` |
| **m3 enclosure of via3** | **0.06 µm** | lydrc:609 `m3.4` |
| m3 enclosure（替代） | 0.055 µm | lydrc:617 `via3.13` |
| m3 enclosure（两对边） | 0.09 µm | lydrc:610 |
| **m4 enclosure of via3** | **0.065 µm** | lydrc:635 `m4.3` |
| m4 enclosure（替代） | 0.06 µm | lydrc:647 `m4.15` |

## 4. 其他相关约束

| 规则 | 值 | 出处 |
|---|---|---|
| m1 min area | 0.083 µm² | lydrc:485 `m1.6` |
| m1 min hole area | 0.14 µm² | lydrc:486 `m1.7` |
| m1 max width after slotting | 4.0 µm | lydrc:495 `m1.11` |
| mcon enclosure by m1 | 0.03 µm | lydrc:481 `m1.4` |
| 所有 via 必须 on-grid 0.005 | — | lydrc:887/891 |
| 所有 via 必须 90° 角 | — | lydrc:888/892 |

---

## 5. 由这些规则推导出的合法研究结构参数

### 5.1 单 cut Via（M1–Via1–M2）
```
via1 cut:      0.150 × 0.150 µm
M1 landing:    cut + 2×0.055 = 0.260 × 0.260 µm  （最坏情况用 0.085 两对边 → 0.320）
M2 landing:    需查 m2 enclosure of via（在 m2 规则段，同样适用）
最小 pitch:    landing + 0.14 spacing
```

### 5.2 近邻不同 Net 对照（同层）
```
最小合法间距: 0.14 µm（普通线）
             0.28 µm（若任一侧宽度 > 3 µm）
合法取样点:   0.14, 0.20, 0.28, 0.50, 1.00 µm
```

### 5.3 线宽对照
```
M1/M2 合法宽度: 0.14, 0.20, 0.30, 0.50, 1.00, 3.00 µm
M3 合法宽度:    0.30, 0.50, 1.00, 3.00 µm
```

### 5.4 跨层投影交叉但不连接（负样本）
```
M1 与 M2 平面投影重叠，但无 via1 cut
→ 最小层间距（M1 顶到 M2 底）由 IMD 决定，几何上只需不重叠即可
→ 但必须确保没有 DRC 违规（各自层内在规则内）
→ 这是合法的 "crossing without connection" 负样本
```

---

## 6. 尚未提取、P1 需补的规则

| 项 | 原因 |
|---|---|
| m2/m3 对 via1/via2 的 enclosure | 规则分散在 m2/m3 段，需单独解析 |
| met2/met3 min area / max width | 同上 |
| 密度规则（density check） | `sky130hd.lydrc` 可能不含，需查 `drc/` 其他文件 |
| 天线规则 | 需查 `sky130hd` 平台天线定义 |

---

## 7. 复算命令

```bash
cd toposem_lesson8/tt-v2
python3 macros/_extract_rules.py    # LEF width
python3 macros/_extract_drc.py      # enclosure rules
python3 macros/_extract_drc2.py     # width + via rules
python3 macros/_extract_drc3.py     # m1 spacing + via1
```

（需 WSL，因为 PDK 在 WSL 的 `/root/openroad-flow-scripts/` 下）
