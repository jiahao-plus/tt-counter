# V2 CI 诊断脚本（可复现保留集）

本目录保存 P5 收敛过程中**有长期复现价值**的诊断脚本，用来支撑
`v2_validation/P5_CLOSEOUT_A_PRUNE.md` 与 `v2_validation/P5_CLOSEOUT_B_LVS_CAUSAL.md`
里的每一条数值结论。

**本目录只做读取与计算，不修改任何设计文件、不修改 `src/config.json`、不触发流程。**

---

## 1. 数据来源与版本锚定

| 项 | 值 |
|---|---|
| Git Commit（第三轮 CI） | `7135c54311a68b62b998002e8f396f06725882e9` |
| Git 分支 | `exp/v2-2x2-research` |
| GitHub Actions Run ID | `40726887237` |
| 运行目录 | `GDS_logs/runs/wokwi` |
| Librelane 版本 | 3.0.14 |
| KLayout | 0.30.12（dbu = 0.001 µm） |
| 流程 PDK | sky130A @ `8afc8346a57fe1ab7934ba5a6056ea8b43078e71` |

### 证据文件 SHA-256

| 文件 | SHA-256 |
|---|---|
| `66-netgen-lvs/reports/lvs.netgen.rpt` | `a3002e41b92db1a28f0d1bca451018527a833a9bb6ab5da9110b7b9f5a7a0314` |
| `final/def/tt_um_jiahao_plus_counter.def` | `3bf208fc43ee24ffad1cdcb2207e3788449090d6f8abf1ef9db53606f7216fb8` |
| `final/gds/tt_um_jiahao_plus_counter.gds` | `2f3cfda420253201d79f88203ef2892fbd92aa1f7efb01ef5391e8550cc2b7d5` |
| `64-magic-spiceextraction/tt_um_jiahao_plus_counter.spice` | `8d6c5fa02e8c359845b32bce26e0dfb404c3917e113b24ed029a21456be7958d` |
| `52-openroad-fillinsertion/tt_um_jiahao_plus_counter.pnl.v` | `198f3b8600b6404ac4f12b4d7705e0f02ca4dd8f3f44a5d8dd8e4071dd79cd86` |
| `62-magic-drc/reports/drc.magic.lyrdb` | `458ce56a1e06f9190309b30c61879abf0377bb8bb84cecafbd9ec6eba5786b28` |

### 权威指标（LibreLane 口径）

```
design__lvs_error__count = 44
  device_difference 21 | net_difference 16 | property_fail 0
  unmatched_device   1 | unmatched_net 1   | unmatched_pin 5
```

> `.rpt` 的明细行数（19 NET / 23 DEVICE / 46 PIN）**不是**这套指标，
> 也不得相加后冒充指标。两者的对应关系见 `b_net_count.py`。

---

## 2. 运行前提

### 2.1 定位输入（不再硬编码个人路径）

所有脚本从 `paths.py` 取两个路径，可用环境变量覆盖：

| 变量 | 含义 | 默认值 |
|---|---|---|
| `TT_RUN_DIR` | LibreLane 运行目录（含 `final/`、`18-openroad-cutrows/`、`62-magic-drc/`） | `<lesson>/GDS_logs/runs/wokwi`，`<lesson>` 是 `tt-v2` 的上一级 |
| `TT_REPO` | 本仓库工作区 | 本脚本目录的上两级 |

两个默认值都对应原始机器的目录布局，所以**不设环境变量也能直接跑**。
换机器时只需：

```bash
export TT_RUN_DIR=/path/to/GDS_logs/runs/wokwi
export TT_REPO=/path/to/tt-v2
```

> 第三轮运行产物（`GDS_logs/runs/wokwi`）**不在仓库内**，按用户约束不予提交
> （体积大、且属于历史日志归档）。要复现本目录的全部数值，需要那份运行产物。

### 2.2 其它

- 需要 **WSL + Python 3 + klayout**（仅 `b_connectivity2.py`、`b_macro_shapes.py`、
  `b_enc_attrib.py`、`b_r1_frame.py`、`b_r1_origin_scope.py` 用到 klayout）。
- 路径可能含非 ASCII 字符，**不要**用 `cv2.imread` 之类的接口读这些路径。
- 脚本可从任意目录调用（`sys.path[0]` 自动解析为脚本所在目录）：

```bash
python3 tools/v2_ci_diagnostics/<script>.py
```

---

## 3. 脚本清单

### 3.1 Part A —— OPT-A 行修剪的物理有效性

| 脚本 | 回答的问题 | 关键输出 |
|---|---|---|
| `a_prune_physical.py` | 哪些 row segment 会被删？坐标、长度、相邻宏 | 26 段 / 572 sites / 715.686 µm² / 1.06% |
| `a_lu_audit.py` | LU.2 / LU.3 / nwell.4 违规总数与分布 | 576 条 |
| `a_lu_2d.py` | 逐规则的二维分布 | 规则 × 坐标矩阵 |
| `a_x_distribution.py` | Tap 的 X 间距分布 | 中位间距（**不可作为阈值依据**） |
| `a_tap_reconcile.py` | 间距 → tap 落点核算 | `O = 28 sites = 12.88 µm`，步距 56 sites = 25.76 µm |
| `a_spatial_crosscheck.py` | 违规是否都在被删段内 | 576/576 在 PRUNABLE，0 在 KEPT |
| `a_rootcause_test.py` | 删除是「消除根因」还是「移走问题区域」 | 3 个 `conb_1` 反例 |
| `a_threshold_basis.py` | 25.76 有无独立物理依据 | 安全窗 **(11.04, 51.06]**；25.76 = 2×round(13/0.46) §DERIVED |
| `a_prune_contents.py` | 被删段里到底有什么 | 单元清单 |
| `a_conb_probe.py` | `conb_1` 的落点与段归属 | 保留段 / 删除段各若干 |
| `a_rule_attribution.py` | 逐规则归因 | 表 |
| `a_gds_fragment_check.py` | 被删段在 GDS 里是否留下碎片 | — |

### 3.2 Part B —— R1 / R2 / R3 因果隔离

| 脚本 | 回答的问题 | 关键输出 |
|---|---|---|
| `b_lvs_causal.py` | `.rpt` 解析 + 悬空网络 → 段映射 | 19 NET / 23 DEVICE / 46 PIN |
| `b_lvs_struct.py` | 三个 research 子电路是不是空黑盒 | 均为 `.subckt ... / .ends` |
| `b_netgen_summary.py` | netgen 汇总 ↔ LibreLane 指标的桥 | 405 vs 389、388 vs 367 |
| `b_net_count.py` | **独立复算网络数** | C1 = 405 节点；`(no matching net)` = 16 行 |
| `b_decompose21.py` | 21 的分解 | `13 + 8 = 21`；**注意**：该脚本早期的「`struct_C1` ORIGIN 非法」判据已作废（ORIGIN 属父坐标系、SIZE 属局部坐标系，不可比大小） |
| `b_reduction_proof.py` | **两侧单元数是否相同 + 归并证明** | 五类实例数全相等；`13+1=14`、`8+1=9` |
| `b_final_decomp.py` | **44 的闭合分解 + 13 个 VPB 的段归属** | `12+4=16`；`13/13 PRUNABLE`；5 行 pin mismatch |
| `b_pin_position.py` | DEF 布线重建 + 端点定位 | 21 段 / 7 悬空端点 |
| `b_r1_frame.py` | **三个工具各用哪个坐标框架** | 路由器 5/5 框架 B；GDS 覆盖率 8/8 = 100% |
| `b_r1_origin_scope.py` | **ORIGIN 合法性 + 三框架铜命中** | 框架 B 8/8 有铜；A/C 8/8 为零 |
| `b_connectivity2.py` | **最终 GDS 是否物理连通** | 11 次迭代 / 30.700 µm² / 8 宏引脚全连通 |
| `b_macro_shapes.py` | 流片后宏几何是否完整 | 形状数 14/14、8/8、7/7 一致 |
| `b_enc_attrib.py` | 93 个 enclosure 违规归属 | 93/93 在宏 bbox 内 |
| `b_magic_view.py` | Magic 抽象视图端口落点 | 五个端点全在 ORIGIN-honoured 框内 |
| `b_r3_and_sensitivity.py` | R3 同构性 + R1/R2/R3 的 tap/row 敏感性 | `conb_1` 同构；R3 在 KEPT 段 |
| `b_conb_vpb.py` | **`conb_1` 的 VPB 归属（一个不进指标的真实异常）** | 3 个 VPB 悬空 → `uio_oe[5..7]`，全在 PRUNABLE；`conb_1 (12) \| (12)` 无 mismatch |

### 3.3 附带数据

| 文件 | 内容 |
|---|---|
| `c_floating_bulk_census.py` | **bulk 悬空单元是否全在被删段内**（OPT-A 的必要条件） | **182/182 在 PRUNABLE，0 在 KEPT**；13 个悬空网络 → 组数 14/9 → 21 |
| `c_cutrows_model.py` | 阈值窗口、丢 tap/row/cell 的精确含义 | 26 段 / 572 站点 / 715.686 µm²；丢 row **0**/81；窗口 (11.04, 51.06] |
| `c_prune_plumbing.py` | `FP_PRUNE_THRESHOLD` 是否到达 CutRows | 声明于 `resolved.json`；`_env.tcl` 通用过滤 null |
| `paths.py` | **路径解析**（`TT_RUN_DIR` / `TT_REPO`，见 §2.1） | 被其余全部脚本导入 |
| `magic_violations.json` | 从 `62-magic-drc/reports/drc.magic.lyrdb` 提取的违规列表（category / cx / cy / …），供 `b_macro_shapes.py`、`b_enc_attrib.py` 使用 |
| `MANIFEST.sha256` | 本目录全部脚本与数据的 SHA-256 |

校验：

```bash
cd tools/v2_ci_diagnostics && sha256sum -c MANIFEST.sha256
```

---

## 4. 已被推翻 / 已废弃的中间结论（保留作警示）

| 结论 | 状态 | 推翻依据 |
|---|---|---|
| 「`decap_3 16182->14` 表示版图比参考多 13 个 decap」 | **错误** | `b_reduction_proof.py`：两侧实例数完全相同，`->14` 是串并联归并后的器件组数 |
| 「13 个网络 = 13 个器件」 | **口径混用** | `FILLER_53_9/VPB` 一个网络挂 2 个端口；13 网络 ↔ 21 端口 |
| 「`i.trans * cell.dbbox()` 能直接给出绝对坐标」 | **错误** | 该式返回 dbu 整数，需 `cell.bbox()` + `.to_dtype(dbu)` |
| 「93 个 enclosure 违规在 GDS 内容里」 | **错误** | 早期变换 bug；`b_macro_shapes.py` 修正后 93/93 在宏实例 bbox 内 |
| 「25.76 有物理依据」 | **降级为 DERIVED** | `a_threshold_basis.py`：安全窗 (11.04, 51.06]，25.76 = 2×round(13/0.46) |
| 「Netgen 左右配对 = 物理短路」 | **错误** | 端口匹配失败后的错位排列；netgen 自print `Port matching may fail to disambiguate symmetries.` |
| 「R1 是缺标签」 | **已否定** | 端口几何在框架 A 下 8/8 命中 0 µm²；加标签不改变几何 |
| 「`struct_C1` ORIGIN 非法」 | **已否定** | `ORIGIN` 是父坐标系量、`SIZE` 是局部量，不可比。实测 ORIGIN == GDS bbox 左下角，七份 LEF 全合法 |
| 「DEF `ROW` 行前两个数字是 Y 再 X」 | **错误** | 实为 **X 再 Y**。读反会让所有几何判据交叉，曾伪造出「删掉 1 整行」 |
| 「保留段有 51 个 15 µm 违规」 | **已否决** | 那是「段边缘到 tap」代理模型；真实规则针对扩散区，且 Magic 实测保留段违规 = 0 |
| 「576 条违规里 552 条在删除段」 | **口径错误** | 用质心归属所限。改用 bbox 重叠：**576/576 全在 DEL，0 跨界** |

---

## 5. 明确不在本目录的内容

按用户约束，以下**不提交**：

- 大型 ZIP、完整中间产物
- 缓存（`__pycache__`、`.v2ana/tech.json`、`.v2ana/sky130.tech` 等从 PDK 导出的临时物）
- 临时日志（`synth_full.log` 等）
- 任何凭据

`.v2ana/` 下的探索性脚本（`dbg.py`、`cmp.py`、`rows.py` 一类）也保留在原处不迁移，
因为它们是一次性调试产物，没有独立复现价值。
