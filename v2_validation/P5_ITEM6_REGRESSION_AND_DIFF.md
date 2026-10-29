# Item 5(6) — 本地回归结果与 Git Diff

编写日期：2026-10-29
对应交付物 (6)：**全部本地回归结果和 Git Diff**

> **本轮没有 Commit、Push、PR 或 CI。** 下面的 diff 全部停留在工作区，
> 等待你的审查与第四轮提交授权。

---

## 1. 一键回归：26/26 PASS，0 SKIP

命令：`bash macros/_run_all_checks.sh`

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
p5_geometry_record.py                      PASS
p5_intrusion_negative.py                   PASS
p5_intrusion_check.py                      PASS
p5_pad_impact.py                           PASS

ALL LOCAL CHECKS PASS
```

**0 SKIP。** 这一点单独说明：`p5_intrusion_check.py` 与 `p5_pad_impact.py`
依赖仓库外的第三轮最终 GDS，脚本对缺失产物会报 `SKIP` 而**不是** PASS。
本次两者都真正运行了（`FINAL_GDS` 存在），所以 26 条全部是真跑出来的。

### 1.1 本轮新增到一键脚本的 4 条

```bash
run "p5_geometry_record.py"        python3 macros/p5_geometry_record.py
run "p5_intrusion_negative.py"     python3 macros/p5_intrusion_negative.py
run "p5_intrusion_check.py"        python3 macros/p5_intrusion_check.py \
                                     "$FINAL_GDS" "$FINAL_DEF" \
                                     tools/v2_ci_diagnostics/intrusion_check.json tools/v2_ci_diagnostics/head
run "p5_pad_impact.py"             python3 macros/p5_pad_impact.py \
                                     "$FINAL_GDS" "$FINAL_DEF" \
                                     tools/v2_ci_diagnostics/head tools/v2_ci_diagnostics/pad_impact.json
```

`FINAL_GDS` / `FINAL_DEF` 默认指向
`$TT_RUN_DIR/final/{gds,def}/tt_um_jiahao_plus_counter.{gds,def}`，
可用同名环境变量覆盖；两者任一不存在时整段跳过并计入 SKIP（**不会**报 PASS）。

---

## 2. 各检查在本轮的具体结论

| 检查 | 关键输出 | 结论 |
|---|---|---|
| `gen_v2_macros.py` | 7 个宏重生成，`ENCL=0.095` | Via1 pad 0.340、Via2 pad 0.390 |
| `gen_lef.py` | OBS 不变量 O1/O3/O4 + 规则 E 全过 | ORIGIN/SIZE 随 prBoundary 自动同步 |
| `run_all_drc.py` | A/B/C1/C3/C4/D/E 各 0 违规 | `LOCAL_GEOM_DRC`（非官方 deck）|
| `_negative_control.py` | 3 条对照正确报违规 | 检查器会咬 |
| `p3_gds_identity.py` | 4 宏 `GEOM_IDENTICAL`、3 宏 `PAD_ONLY`、0 `OTHER` | 新判据 PASS |
| `_neg_gds_identity.py` | 7 条对照（3 摘要 + 4 PAD_ONLY 策略）| 全部按预期 |
| `p5_geometry_record.py` | 0 个 `OTHER` 分类 | PASS |
| `p5_intrusion_negative.py` | 12 条断言 | PASS |
| `p5_intrusion_check.py` | `layers_polluting = 0` | PASS |
| `p5_pad_impact.py` | 新增短接 0、新增间距违规 0、增长触外来金属 0 | PASS |

### 2.1 负向对照明细（这是"检查器真的会咬"的证据）

**`geom_drc.py` 的 9 条 via 包围对照**（`macros/out/neg_controls.json`）：

| # | 构造 | 期望 | 结果 |
|---|---|---|---|
| N1 | Via1 包围 0.055（第三轮 CI 的实际值） | FAIL | ✓ FAIL |
| N2 | Via1 对称 pad 0.280（**我上一轮的错误建议**） | FAIL | ✓ FAIL |
| N3 | Via1 对称 pad 0.320（正好 0.085） | PASS | ✓ PASS |
| N4 | Via1 对称 pad 0.310 | FAIL | ✓ FAIL |
| N5 | Via2→M2 包围 0.040（第三轮 CI 的实际值） | FAIL | ✓ FAIL |
| N6 | Via2→M3 包围 0.065（正好） | PASS | ✓ PASS |
| N7 | Via2→M3 包围 0.060 | FAIL | ✓ FAIL |
| N8 | 只有一对相对边达标（L/R=0.050，B/T=1.135） | PASS | ✓ PASS |
| N9 | 两边都不达标 | FAIL | ✓ FAIL |

N3 与 N4 一起把阈值钉在 0.320；N2 直接证明 0.280 不够。

**`_neg_gds_identity.py` 的 7 条对照**：

```
pya roundtrip      diffbytes=8 outside_dates=NONE  OK
translate_1dbu     shapes=8 (base 8)  CAUGHT=True  bytes_outside_dates=5
widen_1dbu         shapes=8 (base 8)  CAUGHT=True  bytes_outside_dates=2
mirror_x           shapes=8 (base 8)  CAUGHT=True  bytes_outside_dates=20

PAD_ONLY containment controls (must all be REJECTED):
  shrink_wire        removed=[('68/20', 0.5)]      vias_unchanged=True   rejected=True   PASS
  move_wire_2um      removed=[('68/20', 0.7)]      vias_unchanged=True   rejected=True   PASS
  move_via_cut_1dbu  removed=[('68/44', 0.0001)]   vias_unchanged=False  rejected=True   PASS
  grow_only          removed=none                  vias_unchanged=True   rejected=False  PASS
```

前 3 条证明"图形数不变但几何变了"能被抓到（这正是上一轮只比数量的漏洞）。
后 4 条证明新的 `PAD_ONLY` 闸门能区分"只增长"（放行）与"缩短/移动/改 via"（拒绝）。

**`p5_intrusion_negative.py` 的 12 条断言**：

```
N1_clean     foreign=0 missing=0 gap=n/a   onPIN=0 offPIN=0 ok
N2_coexist   foreign=1 missing=0 gap=1.401 onPIN=0 offPIN=0 ok
N3_pollute   foreign=1 missing=0 gap=0.000 onPIN=0 offPIN=1 POLLUTED
N4_on_pin    foreign=1 missing=0 gap=0.000 onPIN=1 offPIN=0 ok
N5_missing   foreign=1 missing=1 gap=n/a   onPIN=0 offPIN=0 ok
ALL CONTROLS: PASS
```

N2 的 gap 断言要求落在开区间 (0.5, 2.5) —— 专门防"搜索上限饱和"（本轮修过的 bug：
上限曾是 5.0 µm，而 B 的真实间隙恰好 5.000 µm，两者无法区分；现已提到 20 µm）。

---

## 3. Git Diff 清单

```
 31 files changed, 912 insertions(+), 324 deletions(-)
```

（**实测值，2026-10-29 复核**。这组数字在 `gen_v2_macros.py` + `gen_lef.py`
重跑前后、以及 `_run_all_checks.sh` 完整重跑前后都完全一致 —— 已实测，
重生成是幂等的。注意 `v2_validation/P5_*.md` 六个交付文档是 **untracked**，
不进入 `git diff --stat`；它们的内容改动**不会**改变这组数字。）

### 3.1 源码与脚本（5 个文件）

| 文件 | 改动 | 为什么 |
|---|---|---|
| `macros/gen_v2_macros.py` | `ENCL 0.055→0.095`、`ENCL_M3 0.095` | **Item 2 的根因修复**：旧值全低于 0.085 规则 |
| `macros/geom_drc.py` | 阈值改为 0.085/0.085/0.085/0.065；directional 语义修正（阈值原先错用 dbu 比 µm） | 检查器原先与错误几何"自洽地通过" |
| `macros/p3_gds_identity.py` | 通过条件从"逐字节/逐图形全等"改为按分类判定；新增 `vias_of()`、`head_not_contained()`、`load_change_record()` | **Item 4**：逐字节相同不再是判据 |
| `macros/_neg_gds_identity.py` | 新增 4 条 `PAD_ONLY` 策略对照 | 证明新闸门会咬 |
| `macros/_run_all_checks.sh` | 接入 4 条 P5 检查 + `FINAL_GDS/FINAL_DEF` 环境变量与 SKIP 语义 | 把本轮的临时脚本固化成可复跑的一键检查 |

### 3.2 生成产物（24 个文件，全部由脚本重生成）

| 类别 | 文件 | 变化性质 |
|---|---|---|
| 宏 GDS | `struct_A/B/C1.gds` | **有意**：pad 增大 |
| 宏 GDS | `struct_C3/C4/D/E.gds` | **仅时间戳**（几何逐图形相同）|
| 合并版 | `v2_structures.gds` | 含前三个宏的 pad 变化 |
| 宏 LEF | `struct_A/B/C1.lef` | ORIGIN/SIZE/OBS 随 pad 同步 |
| 负向对照 GDS | `neg_bad_enclosure/neg_too_close/neg_too_narrow.gds` | 规则更新后重生成 |
| 清单 | `macro_index.json`、`v2_structures_manifest.json` | 尺寸/摘要更新 |
| 验证报告 | `P3_MACRO_BBOX.csv`、`P3_MACRO_VIEW_CONSISTENCY.{json,md}`、`P4_PIN_PORT_CONTRACT.json`、`P5_LEF_OBS.json`、`p3_placement.json`、`P4_GDS_IDENTITY.{json,md}` | 由检查脚本重生成 |
| 文档 | `v2_spec/P3_MACRO_PLACEMENT_PLAN.md` | `p3_sync_docs.py` 自动同步 |
| 日志 | `v2_validation/synth_full.log` | **仅计时/内存**（见 §3.3）|

### 3.3 必须逐一解释的三个"看起来可疑"的差异

**(a) `synth_full.log`** —— 只差计时与内存：

```diff
-End of script. Logfile hash: 732736a214, time: 0.21s, ... MEM: 29.43 MB peak
+End of script. Logfile hash: 732736a214, time: 0.20s, ... MEM: 29.54 MB peak
-Time spent: 64% 1x abc (0 sec), 7% 25x opt_clean (0 sec), ...
+Time spent: 63% 1x abc (0 sec), 7% 25x opt_clean (0 sec), ...
```

**`Logfile hash: 732736a214` 两边完全相同** —— 综合网表没有任何变化。
这与预期一致：本轮只动 BEOL pad，没有碰 RTL。

**(b) `P4_PIN_PORT_CONTRACT.json`** —— C1 的 PIN 相对坐标整体 +0.040：

```diff
-"rect": [0.0, 0.06, 0.14, 0.2]      -> [0.0, 0.1, 0.14, 0.24]
-"rect": [1.0, 2.06, 1.14, 2.2]     -> [1.0, 2.1, 1.14, 2.24]
```

这不是 PIN 动了，而是 **ORIGIN 动了**。C1 的 prBoundary 下边从 4.870 降到 4.830
（pad 向下长了 0.040），ORIGIN 跟着降 0.040；LEF `RECT` 是**相对 ORIGIN** 的，
所以相对值 +0.040。验证绝对坐标：

| 相对 y（旧→新） | + ORIGIN（旧 4.870 / 新 4.830） | 绝对坐标 |
|---|---|---|
| 0.060 → 0.100 | 4.930 / 4.930 | **4.930（不变）** |
| 2.060 → 2.100 | 6.930 / 6.930 | **6.930（不变）** |
| 2.560 → 2.600 | 7.430 / 7.430 | **7.430（不变）** |
| 3.060 → 3.100 | 7.930 / 7.930 | **7.930（不变）** |

**四个 PIN 的绝对坐标一个一个都没变。** 这正是"同步正确"的定义。

**(c) `struct_C3/C4/D/E.gds`** —— 几何完全没变，字节却不同：

4 个文件各差 **16 字节，全部落在 BGNLIB/BGNSTR 日期记录内**（`outside dates: NONE`）。
这不是本轮改出来的，是任何一次重新生成都会发生的。上一轮把"逐字节相同"
当通过条件，正是因为没意识到这一点。

---

## 4. 未纳入 Git 跟踪的新增内容

### 4.1 应当纳入（下一轮提交时）

| 路径 | 内容 |
|---|---|
| `macros/p5_geometry_record.py` | Item 4 几何变更记录 + 研究不变量 |
| `macros/p5_intrusion_check.py` | Item 4 独立侵入检测 |
| `macros/p5_intrusion_negative.py` | 12 条负向对照 |
| `macros/p5_pad_impact.py` | pad 放大对既有布线的影响 |
| `macros/out/neg_*.gds`、`neg_controls.json`、`intrusion_neg_controls.json` | 负向对照产物 |
| `v2_validation/P5_ITEM1_HALO_ROW_TAP.md` | 交付物 (2) |
| `v2_validation/P5_ITEM2_VIA_ENCLOSURE.md` | 交付物 (3) |
| `v2_validation/P5_ITEM3_LVS_ROOTCAUSE.md` | 交付物 (4) |
| `v2_validation/P5_ITEM4_GEOMETRY_CHANGE.md` | 交付物 (5) |
| `v2_validation/P5_ITEM6_REGRESSION_AND_DIFF.md` | 本文件，交付物 (6) |
| `v2_validation/P5_ITEM7_CI_ACCEPTANCE.md` | 交付物 (7) |

### 4.2 `tools/v2_ci_diagnostics/` —— 建议纳入，但需要你决定

`tools/v2_ci_diagnostics/` 共 **927 KB、81 个文件**，其中：

**应当保留（是结论的证据，不是草稿）：**

| 文件 | 作用 |
|---|---|
| `geometry_sha_pre_fix.json` | 旧几何 SHA256 冻结（任务明确要求）|
| `geometry_change_record.json` | 本轮几何变更的权威记录 |
| `head/struct_*.gds` | **权威旧几何字节**（从 `git cat-file HEAD:` 提取）|
| `sky130.tech` | Magic DRC deck 原文（规则依据）|
| `intrusion_3rd_round_head.json`、`pad_impact_head.json` | Item 4 的检测结果 |
| `pin_contact.json` | "0 个 PIN 被短接"的结论 |
| `LVS_ROOTCAUSE.md` | Item 3 分析的原始工作稿（正式版见 `v2_validation/P5_ITEM3_LVS_ROOTCAUSE.md`）|

**可以删除（一次性调试脚本）：** `dbg.py`、`cmp.py`、`who.py`、`frame_test.py`、
`probe`/`sweep`/`solve`/`calib` 系列等约 40 个探索性脚本 —— 它们的结论已写进
三份 Item 文档，脚本本身不再有复用价值。

**建议**：把 4.2 第一组纳入跟踪，第二组不纳入。**是否照做，等你的指示** ——
本轮我没有删除任何东西。

### 4.3 `tools/v2_ci_diagnostics/old/` 的定位（重要，容易搞错）

`tools/v2_ci_diagnostics/old/` 是**修复后重新生成的一份旧规则副本**（用 `rules_old.json` 的
`v1_m1=0.055 / v2_m2=0.040` 生成），它**不是** HEAD 的原始字节：

| 宏 | HEAD 字节 SHA | `tools/v2_ci_diagnostics/old` 字节 SHA |
|---|---|---|
| A | `49b97b2f…` | `3e22d740…` |
| C3 | `9e7fddd3…` | `51547c11…` |

已用规范化摘要证明二者**几何完全等价**（7/7 相同，`tools/v2_ci_diagnostics/snapshot_vs_head.json`）。
但为了避免"拿错基准"，本轮所有结论的基准已统一改为 `tools/v2_ci_diagnostics/head/`（HEAD 原始字节）。
**这件事写在这里，是因为拿错基准会让 Item 4 的所有结论失效。**

---

## 5. 未运行或不存在的检查（不得当作 PASS）

| 检查 | 状态 | 原因 |
|---|---|---|
| Magic DRC | **未运行** | 本机未安装 `magic` |
| Netgen LVS | **未运行** | 本机未安装 `netgen` |
| KLayout 官方 DRC deck | **未运行** | 本机只有 SKY130 的 Magic deck 源文件，无 klayout DRC 运行环境 |
| 天线 / 密度 / FEOL 规则 | **未运行** | `geom_drc.py` 明确不覆盖，结论标记 `LOCAL_GEOM_DRC` |
| 第四轮 LibreLane 全流程 | **未运行** | 本轮不授权触发 CI |

**本地 `geom_drc.py` 全部 PASS 不等于 Magic DRC 会通过。** 它只实现了
Deck 里的 BEOL 宽度/间距/via 尺寸/via 包围/网格几条规则。

---

## 6. 与 V1 的关系（不得含糊）

V1 黄金版本（`24fc6a5`）**没有这七个研究宏**，因此：

- 不存在"与 V1 比较这些宏"这件事；
- 本轮所有 diff 都是相对 V2 分支 HEAD（`7135c54`）的；
- **V1 未被修改**（未 touch、未生成、未提交）。

V1 的 SHA256 校验值本轮没有重新计算 —— 本轮也没有任何操作会触及 V1 的文件。
