# LEF OBS 独立复核

自动生成：`macros/p3_verify_lef_obs.py`  
方法：**不 import `gen_lef.py`**。LEF 文本由本脚本自己的解析器读，GDS 金属由本脚本自己重建，再用 OpenROAD ODB（第三方读取器）对照。

> 之所以要独立写一遍：`gen_lef.py` 写文件前的自检用的是它构造 OBS 时同一批 Region，若金属提取或坐标平移有 bug，自检会跟着一起错。

## 规则

- **规则 E**（A/B/C1 电气宏）：`OBS = 绘制金属 − PIN 图形`
- **规则 G**（C3/C4/D/E 几何宏）：整个 prBoundary 一个 OBS 矩形，只加在该宏真正绘制了图形的层上

met4/met5 一律不加 OBS：这两层是 PDN 层，`ERROR_ON_PDN_VIOLATIONS = True`。

## 结果

| 宏 | cell | 规则 | PIN | PORT | OBS 矩形 | 最少自由接近方向 | 判定 |
|---|---|---|---|---|---|---|---|
| A | `research_via1` | E | 1 | 1 | 7 | 3 | **PASS** |
| B | `research_via2` | E | 1 | 1 | 6 | 3 | **PASS** |
| C1 | `research_branch` | E | 1 | 1 | 13 | 3 | **PASS** |
| C3 | `research_near` | G | 0 | 0 | 1 | — | **PASS** |
| C4 | `research_cross` | G | 0 | 0 | 2 | — | **PASS** |
| D | `research_dense` | G | 0 | 0 | 3 | — | **PASS** |
| E | `research_fiducial` | G | 0 | 0 | 2 | — | **PASS** |

## 逐宏逐层明细

### A — `research_via1`（规则 E）

| 层 | OBS | PIN | OBS∩PIN | OBS 自重叠 | 金属未覆盖 | 判定 |
|---|---|---|---|---|---|---|
| met1 | 4 | 1 | 0 | 0 | 0 | PASS |
| met2 | 3 | 1 | 0 | 0 | 0 | PASS |

PIN 接近方向：A/met1 → 3 个自由方向 (left, below, above)；A/met2 → 3 个自由方向 (right, below, above)

### B — `research_via2`（规则 E）

| 层 | OBS | PIN | OBS∩PIN | OBS 自重叠 | 金属未覆盖 | 判定 |
|---|---|---|---|---|---|---|
| met2 | 3 | 1 | 0 | 0 | 0 | PASS |
| met3 | 3 | 1 | 0 | 0 | 0 | PASS |

PIN 接近方向：B/met2 → 3 个自由方向 (left, below, above)；B/met3 → 3 个自由方向 (right, below, above)

### C1 — `research_branch`（规则 E）

| 层 | OBS | PIN | OBS∩PIN | OBS 自重叠 | 金属未覆盖 | 判定 |
|---|---|---|---|---|---|---|
| met1 | 7 | 1 | 0 | 0 | 0 | PASS |
| met2 | 6 | 3 | 0 | 0 | 0 | PASS |

PIN 接近方向：C1/met1 → 3 个自由方向 (left, below, above)；C1/met2 → 3 个自由方向 (left, right, above)；C1/met2 → 3 个自由方向 (left, right, above)；C1/met2 → 3 个自由方向 (left, right, above)

### C3 — `research_near`（规则 G）

| 层 | OBS | PIN | OBS∩PIN | OBS 自重叠 | 金属未覆盖 | 判定 |
|---|---|---|---|---|---|---|
| met1 | 1 | 0 | 0 | 0 | 0 | PASS |

### C4 — `research_cross`（规则 G）

| 层 | OBS | PIN | OBS∩PIN | OBS 自重叠 | 金属未覆盖 | 判定 |
|---|---|---|---|---|---|---|
| met1 | 1 | 0 | 0 | 0 | 0 | PASS |
| met2 | 1 | 0 | 0 | 0 | 0 | PASS |

### D — `research_dense`（规则 G）

| 层 | OBS | PIN | OBS∩PIN | OBS 自重叠 | 金属未覆盖 | 判定 |
|---|---|---|---|---|---|---|
| met1 | 1 | 0 | 0 | 0 | 0 | PASS |
| met2 | 1 | 0 | 0 | 0 | 0 | PASS |
| met3 | 1 | 0 | 0 | 0 | 0 | PASS |

### E — `research_fiducial`（规则 G）

| 层 | OBS | PIN | OBS∩PIN | OBS 自重叠 | 金属未覆盖 | 判定 |
|---|---|---|---|---|---|---|
| met1 | 1 | 0 | 0 | 0 | 0 | PASS |
| met2 | 1 | 0 | 0 | 0 | 0 | PASS |

## ODB 第三方对照

| cell | ODB PIN | ODB PORT | ODB OBS | ODB 逐层 | 文本 PIN | 文本 PORT | 文本 OBS | 文本逐层 | 判定 |
|---|---|---|---|---|---|---|---|---|---|
| `research_via1` | 1 | 1 | 7 | met1=4, met2=3 | 1 | 1 | 7 | met1=4, met2=3 | PASS |
| `research_via2` | 1 | 1 | 6 | met2=3, met3=3 | 1 | 1 | 6 | met2=3, met3=3 | PASS |
| `research_branch` | 1 | 1 | 13 | met1=7, met2=6 | 1 | 1 | 13 | met1=7, met2=6 | PASS |
| `research_near` | 0 | 0 | 1 | met1=1 | 0 | 0 | 1 | met1=1 | PASS |
| `research_cross` | 0 | 0 | 2 | met1=1, met2=1 | 0 | 0 | 2 | met1=1, met2=1 | PASS |
| `research_dense` | 0 | 0 | 3 | met1=1, met2=1, met3=1 | 0 | 0 | 3 | met1=1, met2=1, met3=1 | PASS |
| `research_fiducial` | 0 | 0 | 2 | met1=1, met2=1 | 0 | 0 | 2 | met1=1, met2=1 | PASS |

> 逐层列是比较的关键。只对总数是弱检查：一个把全部 OBS 都挂到
> 错误层上的读取器，总数仍然完全正确。

## 结论

**PASS** — 七个 LEF 的 OBS 满足 O1–O6 与规则 E/G；A/B/C1 的每个 PIN 至少保留 3 个完全自由的接近方向。

> 本检查只覆盖 LEF/GDS 的一致性。它**不**证明路由器会遵守 OBS，也不证明 pin access、DRC 或 LVS 通过——那三项需要官方 CI。
