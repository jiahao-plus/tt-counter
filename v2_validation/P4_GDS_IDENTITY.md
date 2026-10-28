# GDS 几何一致性（逐图形）

自动生成：`macros/p3_gds_identity.py`  
比较对象：工作区 `macros/out/struct_*.gds` ↔ `git show HEAD:...`

## 方法

每个宏、每种层，把该层全部图形规范化为 `(layer, datatype, 形状类别, 绝对坐标)`，
排序后做 SHA-256。多边形按缠绕方向与起始顶点规范化。
层次变换由 `begin_shapes_rec` 应用到坐标上，因此"绝对坐标一致"已包含
层次变换一致。文件时间戳、库名、BGNLIB 日期不参与摘要。

> 上一轮只比较了每层图形**数量**。数量相同不等于几何相同——一条线平移、
> 一个矩形翻转、一个多边形改形状，数量都不变。本轮改为逐图形比较。

## 结果

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

## 逐层明细

### A — macros/out/struct_A.gds

| 层 | HEAD 图形 | 工作区图形 | HEAD 摘要 | 工作区摘要 | 判定 |
|---|---|---|---|---|---|
| 235/4 | 1 | 1 | `5b4c0e4a566bf6f9` | `5b4c0e4a566bf6f9` | PASS |
| 68/20 | 4 | 4 | `f42b28d8b439331d` | `f42b28d8b439331d` | PASS |
| 68/44 | 1 | 1 | `e3596aa93a6cfd30` | `e3596aa93a6cfd30` | PASS |
| 69/20 | 2 | 2 | `4bb88383dc2ba3f2` | `4bb88383dc2ba3f2` | PASS |

### B — macros/out/struct_B.gds

| 层 | HEAD 图形 | 工作区图形 | HEAD 摘要 | 工作区摘要 | 判定 |
|---|---|---|---|---|---|
| 235/4 | 1 | 1 | `d9d7f5254f298156` | `d9d7f5254f298156` | PASS |
| 69/20 | 3 | 3 | `bc3c4abbdc80d7a7` | `bc3c4abbdc80d7a7` | PASS |
| 69/44 | 1 | 1 | `ec94fd5901dc375a` | `ec94fd5901dc375a` | PASS |
| 70/20 | 2 | 2 | `be9905234f62cd33` | `be9905234f62cd33` | PASS |

### C1 — macros/out/struct_C1.gds

| 层 | HEAD 图形 | 工作区图形 | HEAD 摘要 | 工作区摘要 | 判定 |
|---|---|---|---|---|---|
| 235/4 | 1 | 1 | `87dc88b1b67c5bb6` | `87dc88b1b67c5bb6` | PASS |
| 68/20 | 4 | 4 | `664877bf1d4f9054` | `664877bf1d4f9054` | PASS |
| 68/44 | 3 | 3 | `6956278a5f904c18` | `6956278a5f904c18` | PASS |
| 69/20 | 6 | 6 | `b7f33d186426ebae` | `b7f33d186426ebae` | PASS |

### C3 — macros/out/struct_C3.gds

| 层 | HEAD 图形 | 工作区图形 | HEAD 摘要 | 工作区摘要 | 判定 |
|---|---|---|---|---|---|
| 235/4 | 1 | 1 | `b9fae7d38eb16505` | `b9fae7d38eb16505` | PASS |
| 68/20 | 8 | 8 | `af78b5a7aaf523fd` | `af78b5a7aaf523fd` | PASS |

### C4 — macros/out/struct_C4.gds

| 层 | HEAD 图形 | 工作区图形 | HEAD 摘要 | 工作区摘要 | 判定 |
|---|---|---|---|---|---|
| 235/4 | 1 | 1 | `869b4d0a0363ab29` | `869b4d0a0363ab29` | PASS |
| 68/20 | 1 | 1 | `e0d421ab3d90123d` | `e0d421ab3d90123d` | PASS |
| 69/20 | 1 | 1 | `6168be1465eb7258` | `6168be1465eb7258` | PASS |

### D — macros/out/struct_D.gds

| 层 | HEAD 图形 | 工作区图形 | HEAD 摘要 | 工作区摘要 | 判定 |
|---|---|---|---|---|---|
| 235/4 | 1 | 1 | `500465ffd39fe112` | `500465ffd39fe112` | PASS |
| 68/20 | 5 | 5 | `ed1982474302d3d0` | `ed1982474302d3d0` | PASS |
| 69/20 | 5 | 5 | `452e3a77d25b5c4e` | `452e3a77d25b5c4e` | PASS |
| 70/20 | 3 | 3 | `36144cbfbcf6ee11` | `36144cbfbcf6ee11` | PASS |

### E — macros/out/struct_E.gds

| 层 | HEAD 图形 | 工作区图形 | HEAD 摘要 | 工作区摘要 | 判定 |
|---|---|---|---|---|---|
| 235/4 | 1 | 1 | `87155998ad8f3c16` | `87155998ad8f3c16` | PASS |
| 68/20 | 3 | 3 | `ce4804a9ad60c4fb` | `ce4804a9ad60c4fb` | PASS |
| 69/20 | 3 | 3 | `ce4804a9ad60c4fb` | `ce4804a9ad60c4fb` | PASS |


## 逐字节对照（时间戳）

摘要比较**不读**时间戳，所以它证明不了"两个文件只差时间戳"。本节做
相反的检查：逐字节比较，并要求**每一个**不同的字节都落在 `BGNLIB`
(0x0102) 或 `BGNSTR` (0x0502) 日期记录内部。

| 文件 | 字节数 | 不同字节 | 命中的日期记录 | 日期记录之外 |
|---|---|---|---|---|
| A | 628 | 16 | BGNLIB, BGNSTR | NONE |
| B | 564 | 16 | BGNLIB, BGNSTR | NONE |
| C1 | 1014 | 16 | BGNLIB, BGNSTR | NONE |
| C3 | 692 | 16 | BGNLIB, BGNSTR | NONE |
| C4 | 308 | 16 | BGNLIB, BGNSTR | NONE |
| D | 1012 | 16 | BGNLIB, BGNSTR | NONE |
| E | 568 | 16 | BGNLIB, BGNSTR | NONE |
| ALL | 4390 | 64 | BGNLIB, BGNSTR | NONE |

## 结论

**PASS** — 七个宏加合并版，逐图形摘要与 HEAD 完全一致。

> 这证明工作区没有改动任何宏的几何。V1（`24fc6a5`）里根本没有
> 这些研究宏，因此不存在"与 V1 比较"这件事。
