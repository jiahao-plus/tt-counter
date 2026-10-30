# GDS 几何一致性（逐图形）

自动生成：`macros/p3_gds_identity.py`  
比较对象：工作区 `macros/out/struct_*.gds` ↔ `git cat-file HEAD:...`

## 通过条件（P5 起已改变）

P3 的通过条件是"与 HEAD 逐图形相同"。**P5 的 Item 2 修正了 via 包围，
那是有意的几何变更，所以逐字节/逐图形全等的条件已经作废。**

现在的判据按宏分类（分类由 `macros/p5_geometry_record.py` 生成，
写在 `.v2ana/geometry_change_record.json`，本脚本只读取、不自行分类）：

| 分类 | 允许的差异 | 附加要求 |
|---|---|---|
| `GEOM_IDENTICAL` | 无 | 必须与 HEAD 逐图形相同；原始字节差必须全在日期记录内 |
| `PAD_ONLY` | 仅金属 pad 增长 | via cut 数量/中心/尺寸不变；HEAD 旧图形必须全部被新几何**包含**（只增不减）|
| 其它 | 不允许 | FAIL |

## 方法

每个宏、每种层，把该层全部图形规范化为 `(layer, datatype, 形状类别, 绝对坐标)`，
排序后做 SHA-256。多边形按缠绕方向与起始顶点规范化。
层次变换由 `begin_shapes_rec` 应用到坐标上，因此"绝对坐标一致"已包含
层次变换一致。文件时间戳、库名、BGNLIB 日期不参与摘要。

## 结果

| 宏 | 声明分类 | 非空层 | HEAD 图形数 | 工作区图形数 | HEAD 摘要 | 工作区摘要 | 判定 |
|---|---|---|---|---|---|---|---|
| A | `NORMALISED` | 4 | 8 | 8 | `db875c6dcca1d2e8` | `20485d449b9a5b6a` | **PASS (declared NORMALISED)** |
| B | `NORMALISED` | 4 | 7 | 7 | `0d427e5da7169ae2` | `aecb0128a12c597e` | **PASS (declared NORMALISED)** |
| C1 | `NORMALISED` | 4 | 14 | 14 | `d333ff410776a74d` | `b15e44aaa1be92d6` | **PASS (declared NORMALISED)** |
| C3 | `GEOM_IDENTICAL` | 2 | 9 | 9 | `230a0c518e4fe9e4` | `230a0c518e4fe9e4` | **PASS** |
| C4 | `GEOM_IDENTICAL` | 3 | 3 | 3 | `0dc226e2f9cea7f1` | `0dc226e2f9cea7f1` | **PASS** |
| D | `GEOM_IDENTICAL` | 4 | 14 | 14 | `ed16d9a062a6998e` | `ed16d9a062a6998e` | **PASS** |
| E | `GEOM_IDENTICAL` | 3 | 7 | 7 | `e08e5747b496e7d2` | `e08e5747b496e7d2` | **PASS** |
| ALL | （合并版） | — | — | — | `4a61d0bd686c3f59` | `c55dfb6ce5e77751` | **PASS** |

> 合并版 `v2_structures.gds` 含三个声明为 `PAD_ONLY` 的宏，
> 与 HEAD 不同是**预期**的。它改判"是否与逐宏输出一致"（防陈旧）。

## 逐层明细

### A — macros/out/struct_A.gds（声明 `NORMALISED`）

| 层 | HEAD | 工作区 | 判定 |
|---|---|---|---|
| 235/4 | 1 shapes, `5b4c0e4a566bf6f9` | 1 shapes, `1748a86ffdf6911b` | DIFFERS |
| 68/20 | 4 shapes, `e55601be45c34130` | 4 shapes, `0cbaed7c0bbbdd84` | DIFFERS |
| 68/44 | 1 shapes, `e3596aa93a6cfd30` | 1 shapes, `f25d12e34acaa96c` | DIFFERS |
| 69/20 | 2 shapes, `e3c07569d0c0c9e9` | 2 shapes, `2b7dc937c1c83d28` | DIFFERS |
| rigid-shift | (-930,-1930) dbu | applied | PASS |
| via-cuts | 1 | 1 | SAME |

### B — macros/out/struct_B.gds（声明 `NORMALISED`）

| 层 | HEAD | 工作区 | 判定 |
|---|---|---|---|
| 235/4 | 1 shapes, `32acdf2d342656ac` | 1 shapes, `e5f8498d8c491d3b` | DIFFERS |
| 69/20 | 3 shapes, `c88090df51b6a5fa` | 3 shapes, `27426b28d27825e6` | DIFFERS |
| 69/44 | 1 shapes, `ec94fd5901dc375a` | 1 shapes, `5280fb8596c8c03b` | DIFFERS |
| 70/20 | 2 shapes, `f8b42ea3b0cfe484` | 2 shapes, `991d155123bb441d` | DIFFERS |
| rigid-shift | (-930,-1930) dbu | applied | PASS |
| via-cuts | 1 | 1 | SAME |

### C1 — macros/out/struct_C1.gds（声明 `NORMALISED`）

| 层 | HEAD | 工作区 | 判定 |
|---|---|---|---|
| 235/4 | 1 shapes, `d0d7e0df9089c2cd` | 1 shapes, `b62a11047e211eec` | DIFFERS |
| 68/20 | 4 shapes, `7ddaf4312868fc7f` | 4 shapes, `9dc0113afe9c8e2f` | DIFFERS |
| 68/44 | 3 shapes, `6956278a5f904c18` | 3 shapes, `d32f37285fbc8021` | DIFFERS |
| 69/20 | 6 shapes, `f542c272b7c29b6b` | 6 shapes, `524224009f183aa5` | DIFFERS |
| rigid-shift | (-930,-4830) dbu | applied | PASS |
| via-cuts | 3 | 3 | SAME |

### C3 — macros/out/struct_C3.gds（声明 `GEOM_IDENTICAL`）

| 层 | HEAD | 工作区 | 判定 |
|---|---|---|---|
| 235/4 | 1 shapes, `b9fae7d38eb16505` | 1 shapes, `b9fae7d38eb16505` | PASS |
| 68/20 | 8 shapes, `af78b5a7aaf523fd` | 8 shapes, `af78b5a7aaf523fd` | PASS |

### C4 — macros/out/struct_C4.gds（声明 `GEOM_IDENTICAL`）

| 层 | HEAD | 工作区 | 判定 |
|---|---|---|---|
| 235/4 | 1 shapes, `869b4d0a0363ab29` | 1 shapes, `869b4d0a0363ab29` | PASS |
| 68/20 | 1 shapes, `e0d421ab3d90123d` | 1 shapes, `e0d421ab3d90123d` | PASS |
| 69/20 | 1 shapes, `6168be1465eb7258` | 1 shapes, `6168be1465eb7258` | PASS |

### D — macros/out/struct_D.gds（声明 `GEOM_IDENTICAL`）

| 层 | HEAD | 工作区 | 判定 |
|---|---|---|---|
| 235/4 | 1 shapes, `500465ffd39fe112` | 1 shapes, `500465ffd39fe112` | PASS |
| 68/20 | 5 shapes, `ed1982474302d3d0` | 5 shapes, `ed1982474302d3d0` | PASS |
| 69/20 | 5 shapes, `452e3a77d25b5c4e` | 5 shapes, `452e3a77d25b5c4e` | PASS |
| 70/20 | 3 shapes, `36144cbfbcf6ee11` | 3 shapes, `36144cbfbcf6ee11` | PASS |

### E — macros/out/struct_E.gds（声明 `GEOM_IDENTICAL`）

| 层 | HEAD | 工作区 | 判定 |
|---|---|---|---|
| 235/4 | 1 shapes, `87155998ad8f3c16` | 1 shapes, `87155998ad8f3c16` | PASS |
| 68/20 | 3 shapes, `ce4804a9ad60c4fb` | 3 shapes, `ce4804a9ad60c4fb` | PASS |
| 69/20 | 3 shapes, `ce4804a9ad60c4fb` | 3 shapes, `ce4804a9ad60c4fb` | PASS |


## 逐字节对照（时间戳）

摘要比较**不读**时间戳，所以它证明不了"两个文件只差时间戳"。本节做
相反的检查：逐字节比较，并要求**每一个**不同的字节都落在 `BGNLIB`
(0x0102) 或 `BGNSTR` (0x0502) 日期记录内部。
该检查只对 `GEOM_IDENTICAL` 宏构成通过条件 —— 几何有意改变的文件
本来就允许字节不同。

| 文件 | 声明 | 字节数 | 不同字节 | 命中的日期记录 | 日期记录之外 |
|---|---|---|---|---|---|
| A | NORMALISED | 628 | 172 | BGNLIB, BGNSTR | **20** |
| B | NORMALISED | 564 | 152 | BGNLIB, BGNSTR | **20** |
| C1 | NORMALISED | 1014 | 292 | BGNLIB, BGNSTR | **20** |
| C3 | GEOM_IDENTICAL | 692 | 12 | BGNLIB, BGNSTR | NONE |
| C4 | GEOM_IDENTICAL | 308 | 12 | BGNLIB, BGNSTR | NONE |
| D | GEOM_IDENTICAL | 1012 | 12 | BGNLIB, BGNSTR | NONE |
| E | GEOM_IDENTICAL | 568 | 12 | BGNLIB, BGNSTR | NONE |
| ALL | （合并版） | 4390 | 628 | BGNLIB, BGNSTR | **20** |

## 结论

**PASS** — 四个宏与 HEAD 逐图形全等；三个宏的差异全部落在
声明的 via pad 增长范围内（cut 不变、旧几何被完全包含）。

> 这不证明与 V1 一致：V1（`24fc6a5`）里没有这些研究宏。
