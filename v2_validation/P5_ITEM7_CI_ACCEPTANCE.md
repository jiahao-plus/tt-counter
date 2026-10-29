# Item 5(7) — 第四轮官方 CI 的具体验收标准

编写日期：2026-10-29
对应交付物 (7)：**第四轮官方 CI 的具体验收标准**

> 本文件是**提交前就要定死的判据**，不是在看到结果之后再解释。
> 每条都给出：第三轮实测基数、本轮已做的本地修复、第四轮期望值、
> 以及"如果没达到"的判定动作。

---

## 0. 第三轮基数（验收的比较起点）

| 指标 | 第三轮实测 | 来源 |
|---|---|---|
| Run ID | `40726887237` | — |
| Commit | `7135c54311a68b62b998002e8f396f06725882e9` | — |
| LibreLane 阶段 | 72/72 完成 | `flow.log` |
| `CheckMacroInstances` | 7 个宏全部通过 | `resolved.json` |
| **Magic DRC 错误** | **669** | `62-magic-drc` |
| **Netgen LVS 错误** | **44** | `66-netgen-lvs/state_out.json` → `design__lvs_error__count` |

### 0.1 669 个 Magic DRC 错误的两类分解

| 类别 | 规则 | 数量 | 归属 | 本轮能否修 |
|---|---|---|---|---|
| **包围类** | `via.5a` 49 + `met2.5` 36 + `via2.4a` 8 | **93** | 宏内 via pad | ✅ **已修**（Item 2）|
| **tap/row 类** | `LU.3` 342 + `LU.2` 220 + `nwell.4` 14 | **576** | 宏外（标准单元行/tap）| ⚠️ **未修，等审批**（Item 1）|
| 合计 | | **669** | | |

**576 + 93 = 669** ✓

### 0.2 44 个 LVS 错误的构成（Item 3 的独立归因）

**权威来源：`66-netgen-lvs/state_out.json` 的 `metrics`**，LibreLane 自己写下的指标：

| 指标 | 值 | 含义 | 根因 | 修 tap 能解决吗 |
|---|---|---|---|---|
| `design__lvs_device_difference__count` | **21** | 器件总数 388 vs 367 | **R2**（纯物理单元被 VPB 悬空拆碎：`decap_3` 类差 13 + `fill_2` 类差 8）| ✅ **能** |
| `design__lvs_net_difference__count` | **16** | 网络总数 405 vs 389 | **R2** 为主，R1 占一部分 | ⚠️ 部分 |
| `design__lvs_unmatched_net__count` | **1** | `pwm_out` ↔ `FILLER_53_9/VPB` | **R1**（net 名未传到 Magic）| ❌ |
| `design__lvs_unmatched_device__count` | **1** | `decap_3` 类 | **R2** | ✅ 能 |
| `design__lvs_unmatched_pin__count` | **5** | 顶层端口未匹配（`VGND`/`VPWR` 3 处 + 对称歧义 2 处）| **R1**（3 个）+ **R3**（2 个）| ❌ **不能** |
| `design__lvs_property_fail__count` | **0** | 无属性失配 | — | — |
| **`design__lvs_error__count`** | **44** | **21+16+1+1+5+0** | | |

`.rpt` 里的逐条明细是**另一套口径**，不要与上面的指标相加：
`NET mismatches` **19 行**、`DEVICE mismatches` **23 行**、`Subcircuit pins` **5 行不符**。
其中 23 行 DEVICE 明细 = 14 `decap_3` + 9 `fill_2`，21 行是 `(no matching instance)`，
恰好等于 `device_difference = 21`。

**顶层 PIN 的 5 处不符（按 JSON 索引对齐实测）**：

| 索引 | Circuit 1 | Circuit 2 | 归类 |
|---|---|---|---|
| 0 | `VGND` | `(no matching pin)` | R1 |
| 1 | `VPWR` | `(no matching pin)` | R1 |
| 32 | `uio_out[7]` | `(no matching pin)` | R3 |
| 43 | `uio_oe[2]` | `(no matching pin)` | R3 |
| 45 | `(no matching pin)` | `VPWR` | R1 |

**明确结论：修 tap 单独不能使 LVS 通过。** 详见 `P5_ITEM3_LVS_ROOTCAUSE.md`。

---

## 1. 七条验收判据（第四轮 CI）

### AC-1 · 流程完整性（硬性）

| 项 | 要求 |
|---|---|
| LibreLane 完成阶段数 | **72 / 72**（不得少） |
| `CheckMacroInstances` | **7 / 7 通过** |
| `route__drc_errors` | **0** |
| 出现新的 error 类阶段 | **不允许** |

**判定**：任何阶段失败或出现新错误类 → **FAIL，停止，不进下一轮**。

> 注意：`route__drc_errors = 0` **不是**"没有外来 wire/via"的证据 ——
> 那条由 AC-6 独立判定。

---

### AC-2 · Magic DRC 包围类错误 = 0（本轮修复的直接验收）

| 项 | 第三轮 | 第四轮要求 |
|---|---|---|
| `via.5a` | 49 | **0** |
| `met2.5` | 36 | **0** |
| `via2.4a` | 8 | **0** |
| 包围类合计 | 93 | **0** |

**依据**：Item 2 把 Via1 pad 从 0.260 提到 **0.340**（包围 0.095 ≥ 规则 0.085），
Via2 pad 从 0.280/0.330 提到 **0.390**。本地 `geom_drc.py` 七个宏全 PASS，
且**旧几何作反向对照时报 A=2 / B=1 / C1=6 违规**（证明检查器会咬）。

**判定**：
- 若包围类 = 0 → **AC-2 PASS**
- 若包围类 > 0 但**数量下降** → **判 FAIL 但仍继续分析**：说明我对 Deck 的
  某条规则理解仍有偏差，需比对具体规则名与坐标，**不得**声称"CI 波动"
- 若包围类**数量不降反升** → **FAIL，且回滚 Item 2**，重新读 Deck

---

### AC-3 · Magic DRC tap/row 类错误 ≤ 576 且不新增规则种类

**本轮状态：这一条尚未修复，因为涉及宏外配置变更，需你审批。**

| 项 | 第三轮 | 第四轮要求（若批准 Item 1 OPT-A）| 未批准时 |
|---|---|---|---|
| `LU.3` | 342 | 应显著下降 | 保持 ~342 |
| `LU.2` | 220 | 应显著下降 | 保持 ~220 |
| `nwell.4` | 14 | 应为 **0** | 保持 ~14 |
| **新增规则种类** | — | **不允许出现** | 不允许出现 |

**若批准 Item 1 的 OPT-A（`FP_PRUNE_THRESHOLD: 25.76`）**，本轮的定量预测是：

| 项 | 第三轮 | 预测 |
|---|---|---|
| 行段数 | 114 | 88 |
| 站点数 | 53872 | 53300 |
| **零 tap 的行段** | **26** | **0** |
| 面积损失 | — | 1.06 % |
| 最短幸存段 | — | 51.06 µm |

（该配置**尚未写入** `src/config.json`，等你的授权。）

**判定**：
- 若 `nwell.4` 仍 > 0 → 说明 tap 覆盖仍有盲区，**FAIL**
- 若出现第三轮没有的规则名（如 `LU.1`、`licon.*`）→ **FAIL，回滚**，说明修复引入了新问题
- 若 tap 类下降但包围类上升 → **FAIL**，说明两者相互干扰（本轮已证明二者集合不相交：

  `set(old_segments) ^ set(new_segments) = ∅`，所以理论上不应互相干扰）

---

### AC-4 · Netgen LVS 错误数 = 0 或已归零到已知的不可修项

**这是最需要说清楚的一条。** 44（= 21+16+1+1+5+0）的三个根因中：

| 根因 | 影响的指标 | 本轮是否处理 | 期望 |
|---|---|---|---|
| **R1** | `MAGIC_DEF_LABELS = False` → net 名未传到 Magic。解释 `unmatched_net` 的 1 项（`pwm_out` ↔ `FILLER_53_9/VPB`）、`net_difference` 的一部分、以及 `unmatched_pin` 5 项中的 3 项（`VGND`/`VPWR`）| ❌ **未改配置**（需审批）| 若批准改为 `True`：这几类应消失 |
| **R2** | 纯物理单元（`decap_*`、`fill_*`）因 VPB/VNB 浮空被拆开：`device_difference` **21**（全部）+ `unmatched_device` **1** + `net_difference` 的主要部分 | ❌ 依赖 AC-3 的 tap 修复 | tap 修好后 `device_difference` 应 → 0 |
| **R3** | `uio_out[7]` / `uio_oe[2]` 对称歧义：`unmatched_pin` 5 项中的 **2** 项 | ❌ **不可通过 tap 或 label 修复** | **预期仍存在** |

**第四轮的定量预测（若同时批准 OPT-A 且 `MAGIC_DEF_LABELS = True`）**：

| 指标 | 第三轮 | 预测 | 依据 |
|---|---|---|---|
| `device_difference` | 21 | **0** | 零 tap 行段清零 → VPB 不再悬空 |
| `net_difference` | 16 | 应显著下降，但**不保证归零** | R1 残余无法量化预测 |
| `unmatched_net` | 1 | **0** | 若 R1 修好 |
| `unmatched_device` | 1 | **0** | 同 `device_difference` |
| `unmatched_pin` | 5 | **2** | 只剩 R3 的 `uio_out[7]` / `uio_oe[2]` |
| `property_fail` | 0 | **0** | — |

**若只批准 OPT-A 而不改 `MAGIC_DEF_LABELS`**：`device_difference`/`unmatched_device`
应归零，但 `unmatched_net` 与 `unmatched_pin` 的 R1 部分**仍然存在**。

**判定（三档，必须显式选择一档，不得含糊）**：

| 结果 | 判定 |
|---|---|
| `design__lvs_error__count` = **0** | **PASS** |
| 剩余项**全部**落在 R3 或明确的 R1/R2 残余，且**每一项都能指名根因** | **CONDITIONAL PASS** —— 必须逐项列出指标名与数值，并说明为何不可修 |
| 出现**任何无法归因**的新 LVS 错误 | **FAIL，回滚** |

**禁止事项（重复强调）**：
- ❌ 不得添加任何**伪造** power PIN 来让 LVS 通过
- ❌ 不得关闭 LVS
- ❌ 不得因为"tap 修好了"就**推断** LVS 必过
- ❌ 不得把"未运行"写成 PASS
- ❌ 不得把 `.rpt` 的明细行数（19/23/5）当作 `design__lvs_error__count` 的分解

---

### AC-5 · 研究真值完整性（几何层面）

| 项 | 要求 | 本地已验 |
|---|---|---|
| 7 个宏全部通过 `CheckMacroInstances` | 是 | 第三轮已是 7/7 |
| 每个宏分类为 `GEOM_IDENTICAL` 或 `PAD_ONLY` | 无 `OTHER` | ✅ 0 个 OTHER |
| C3 八条独立导体 | 8 条，0 via | ✅ `eight_independent = True` |
| C4 无 via 交叉 | Via1 = Via2 = 0 | ✅ `crossing_has_no_via = True` |
| D 五级线宽阶梯 | 5 档：0.14/0.20/0.30/0.50/1.00 | ✅ `five_steps = True` |
| E 对准标记（M1 与 M2 重合） | M1 集合 == M2 集合，0 via | ✅ `m1_equals_m2 = True` |
| A/B/C1 的 via cut 中心与尺寸 | 与 HEAD 逐字节相同 | ✅ `via_identity_unchanged` |
| α′ 接口 | 不变 | ✅ PIN/PORT 契约检查 PASS |

**第四轮额外要求**：在**最终 GDS** 上（不是宏 GDS）重跑同一组不变量。
本地是在第三轮最终 GDS 上做的，第四轮 GDS 不同，**必须重跑**。

**判定**：任何一条不成立 → **FAIL**。研究真值优先级高于 DRC/LVS 通过。

---

### AC-6 · 外部路由侵入独立检测（不得只看 `route__drc_errors`）

| 项 | 第三轮实测 | 第四轮要求 |
|---|---|---|
| `layers_polluting` | **0** | **0** |
| `total_shorted_pins` | **0** | **0** |
| C1 的 `pwm_out` 接触 | 在 PIN 上（意图内）| 仍在 PIN 上 |
| C3 / C4 / E | CLEAN（0 外来图形）| 仍应 CLEAN |
| pad 增长 vs 外来金属重叠 | 0（最小间隙 0.901 µm）| **0** |

**判定**：
- `layers_polluting > 0` → **FAIL**，研究结构被外来网络改接
- `total_shorted_pins > 0` → **FAIL**，某个 PIN 被多个网络覆盖
- 若 C3/C4/E 出现外来图形 → **必须逐条说明**；这三个结构的设计前提就是"纯净"

**方法要求**：必须用 `macros/p5_intrusion_check.py`（不读 `route__drc_errors`、
不读路由器报告、不读 LEF OBS），并同时报告负向对照 12/12 通过。

---

### AC-7 · V1 黄金版本与提交纪律

| 项 | 要求 |
|---|---|
| V1（`24fc6a5`）工作树 | **零改动** |
| V1 的 SHA256 | 与第三轮记录一致 |
| 本轮提交内容 | 仅 V2 工作区，且限于 §3 清单 |
| 是否有伪造的 SPICE/CDL/Liberty | **无** |

**判定**：V1 有任何改动 → **FAIL，立即回滚**。

---

## 2. 判定矩阵（一次看全）

| # | 判据 | 第三轮 | 第四轮目标 | 未达标动作 |
|---|---|---|---|---|
| AC-1 | 72/72 阶段、7/7 宏、`route__drc_errors=0` | ✅（但 DRC/LVS 有错）| ✅ | **FAIL 停止** |
| AC-2 | 包围类 Magic DRC | 93 | **0** | 回滚 Item 2 重读 Deck |
| AC-3 | tap/row 类 Magic DRC | 576 | 视审批 | 见 §1 AC-3 |
| AC-4 | Netgen LVS | 44 | 0 或可归因残余 | FAIL 回滚 |
| AC-5 | 研究真值不变量 | 未在最终 GDS 上验 | 全成立 | **FAIL** |
| AC-6 | 外部侵入 | 0 污染（已验）| **0** | **FAIL** |
| AC-7 | V1 未动 | ✅ | ✅ | **FAIL 回滚** |

**全部 7 条通过 → 才可进入正式投片讨论。**
**任一条 FAIL → 停止，不进入下一轮。**

---

## 3. 本轮**没有**做的事（避免误读）

| 事项 | 状态 |
|---|---|
| Commit | ❌ 未做 |
| Push | ❌ 未做 |
| PR | ❌ 未做 |
| 触发 CI | ❌ 未做 |
| 正式投片 | ❌ 未做 |
| 修改 `src/config.json` | ❌ 未做（OPT-A 待审批）|
| 修改 V1 | ❌ 未做 |
| 关闭任何物理检查 | ❌ 未做 |
| 安装 Magic / Netgen 本地跑 | ❌ 未做（本机无此工具）|

---

## 4. 第四轮提交前的最后检查清单

提交前必须逐项确认（全部为"是"才可提交）：

- [ ] `bash macros/_run_all_checks.sh` → `ALL LOCAL CHECKS PASS`，0 SKIP
- [ ] `git diff` 与 `P5_ITEM6_REGRESSION_AND_DIFF.md` §3 的清单完全一致，无清单外文件
- [ ] `tools/v2_ci_diagnostics/geometry_sha_pre_fix.json` 仍在，且 SHA256 未被改写
- [ ] `V1 (24fc6a5)` 工作树零改动
- [ ] OPT-A 是否写入 `src/config.json` **已有你的明确书面决定**
- [ ] 本轮生成的 `tools/v2_ci_diagnostics/intrusion_check.json` 中 `layers_polluting == 0`
- [ ] 提交信息中**不含**任何 Token
- [ ] 提交前已在本地确认 `remote.origin.url` 走 SSH（不是含 PAT 的 HTTPS URL）

---

## 5. 如果第四轮 CI 结果与预测不符，我的处理顺序

**不做的事**：不猜、不宣称"波动"、不通过改判据来"通过"。

**做的顺序**：

1. **先取证**：下载完整 `error.log` / `resolved.json` / `62-magic-drc` / `66-netgen-lvs` 报告
2. **分类对比**：按本文件 §0 的同一套规则名分类，与第三轮逐类比对
3. **定位首个偏离**：找出**第一个**与预测不符的规则名或阶段，不从总数开始解释
4. **单点复现**：在本地用 `geom_drc.py` / 宏 GDS 复现那一个点（若属宏内）
5. **报告**：明确说明"哪条预测错了、为什么错、需要改哪条判据"，
   **而不是**改判据去迁就结果
6. **停止**，等你审查

> 判据可以在下一轮被修正 —— 但必须**先承认它错了**，再修正。
> 不允许在结果出来之后悄悄放宽阈值。
