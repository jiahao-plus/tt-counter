# P5 第四轮 CI 结果分析（Run 40832068010）

编写日期：2026-10-29
对应授权：**「第四轮 Commit + Push」**（已执行，`b4e32b8`）
状态：**CI 判定失败；但两个修复目标均达成。失败原因已从 artifact 直接取证，不再是推断。**

> 本文所有结论都标注证据等级：
> `MEASURED` = 直接读到的数据/源码原文；
> `INFERRED` = 由 MEASURED 数据严格推出；
> `UNKNOWN` = 确实无法取得。

**本版更正记录（重要）**：本文初版（同日早先）曾写「第四轮日志与 artifact 在本机无法获取」
并据此做了纯推断分析。该结论**是错的**——artifact 可通过公开代理 `nightly.link` 匿名下载，
且下载文件的 SHA-256 与 GitHub 自己上报的 digest 逐字节一致。初版的推断在此全部被实测取代。
详见 §1.3。

---

## 1. 本轮实际发生了什么

### 1.1 提交与触发（MEASURED）

| 项 | 值 |
|---|---|
| Commit | `b4e32b8a2c679619acc03fe3ad415bb476258260` |
| 消息 | `fix(v2): improve via enclosures and prune short floorplan rows` |
| 推送目标 | `origin/exp/v2-2x2-research`（`7135c54..b4e32b8`，快进）|
| 文件 | 81 个（50 新增 / 31 修改），+17297 / −322 |
| 未推送到 | `main`（未触碰）、无 Tag、无 PR |

### 1.2 Run 与 Job 状态（MEASURED，GitHub REST API）

| Workflow | Run ID | 状态 | 结论 |
|---|---|---|---|
| `gds` | **40832068010** | completed | **failure** |
| `test` | 40832068162 | completed | success |
| `docs` | 40832068012 | completed | success |

`gds` 的 4 个 Job：

| Job | 状态 | 结论 | 起止 (UTC) |
|---|---|---|---|
| **gds** | completed | **failure** | 06:54:35 → 06:58:11（216 s） |
| precheck | completed | **skipped** | 06:58:11 |
| viewer | completed | **skipped** | 06:58:11 |
| gl_test | completed | **skipped** | 06:58:11 |

`gds` Job 内的 step：

```
Set up job          success   06:54:36 .. 06:54:37
checkout repo       success   06:54:37 .. 06:54:38
Build GDS           FAILURE   06:54:38 .. 06:58:09   (211 s)
Post Build GDS      success   06:58:09
Post checkout repo  success   06:58:09
Complete job        success   06:58:09
```

### 1.3 artifact 的获取与真实性（MEASURED，三重锚定）

| 项 | 值 |
|---|---|
| Artifact | `GDS_logs`，id `12879615244` |
| 大小 | 21,341,176 B |
| GitHub 上报 digest | `sha256:6d15af8e76e5877a381fa62cb9dbf8ebf8c389caba032be649e8eb9744a207cf` |
| 本机下载 SHA-256 | **完全一致** |
| `workflow_run.id` | `40832068010` ✔ 本轮 |
| `workflow_run.head_sha` | `b4e32b8a2c679619acc03fe3ad415bb476258260` ✔ 本轮 |
| `created_at` | `2026-10-29T06:58:09Z` ✔ 与 `Build GDS` 失败时刻同秒 |

下载路径（无需任何凭据）：

```
curl -sS --ssl-no-revoke -L \
  https://nightly.link/jiahao-plus/tt-counter/actions/runs/40832068010/GDS_logs.zip
```

**真实性论证**：`nightly.link` 只是个转发代理，不是数据源。文件的 SHA-256 与
GitHub REST API 自己返回的 `digest` 字段逐字节相同，而 `digest` 是 GitHub 在
artifact 上传时计算并存储的。因此内容来自 GitHub，不是代理伪造。
另外 `workflow_run.id` / `head_sha` / `created_at` 三项都指向本轮。

**哪些直接端点确实是关的**（初版把这些误当成"全部渠道"）：

| 获取路径 | 结果 |
|---|---|
| `GET /actions/runs/40832068010/logs` | 403 `Must have admin rights to Repository.` |
| `GET /actions/artifacts/12879615244/zip` | 401 `Requires authentication` |
| `gh` CLI | 存在但未登录 |
| run / job 页面 HTML | 200，日志由 JS 动态加载，无 payload |
| `raw.githubusercontent.com` | 502 |
| `api.github.com`（WSL curl）| 连接被拒 |

结论：**GitHub 的一手日志流仍是 admin-only，但 LibreLane 的完整运行目录在 artifact 里，
而 artifact 通过公开代理可匿名取得。** 本文以下所有指标均为该 artifact 内的实测值。

---

## 2. 失败的确切原因（MEASURED）

### 2.1 一句话结论

> 全部 72 个 stage 都跑完；**Magic DRC 已归零（669 → 0）**；`final/` 完整落盘；
> 流程末尾因**仅有 6 个 LVS 错误**（没有任何 DRC 错误）触发 deferred `FlowError`，
> LibreLane 退出码 2，`tt_tool.py --harden` 见 `rc != 0` 即 `exit(1)`，`Build GDS` 判失败，
> 下游 `precheck` / `viewer` / `gl_test` 全部 skipped。

**注意措辞**：本轮失败原因是「**deferred LVS 错误，Magic DRC 干净**」，
**不是**「DRC/LVS 都有错」。这与第三轮（669 DRC + 44 LVS）有实质区别，
也是本轮修复确实生效的直接体现。

`runs/wokwi/error.log` 全文（第四轮）：

```
Macro/instance u_rs_branch has no power pins- add it to IGNORE_DISCONNECTED_MODULES if this is intentional
Macro/instance u_rs_via1 has no power pins- add it to IGNORE_DISCONNECTED_MODULES if this is intentional
Macro/instance u_rs_via2 has no power pins- add it to IGNORE_DISCONNECTED_MODULES if this is intentional
6 LVS errors found. - deferred
```

**对比第三轮**（同一文件）：

```
669 Magic DRC errors found. - deferred
44 LVS errors found. - deferred
```

`flow.log` 末段（第四轮）：

```
Running 'Checker.MagicDRC' at 'runs/wokwi/63-checker-magicdrc'…
Check for Magic DRC errors clear.          <-- 669 -> 0
...
Running 'Checker.LVS' at 'runs/wokwi/67-checker-lvs'…
6 LVS errors found. - deferred
...
Running 'Misc.ReportManufacturability' at 'runs/wokwi/72-misc-reportmanufacturability'…
Saving views to '/home/runner/work/tt-counter/tt-counter/runs/wokwi/final'…
```

`flow.log` 里 `Flow complete` 出现 **0** 次；`final/commit_id.json` **不存在**
（`tt-support-tools/project.py:544-546` 只在 `returncode == 0` 时写它）。
`final/` 目录本身完整（`def gds json_h klayout_gds lef lib mag mag_gds metrics.* nl odb pnl render sdc sdf spef spice vh`）。

### 2.2 机制链（源码确证，MEASURED）

1. `checker.py:79` `deferred: ClassVar[bool] = True`；
   `MagicDRC`(197) 与 `LVS`(308) 都不覆写它。
2. `ERROR_ON_MAGIC_DRC` / `ERROR_ON_LVS_ERROR` **默认 True**（`checker.py:205-211`、`316-322`），
   项目 `src/config.json` 与 TT 的 `config_merged.json` 都没覆写。
   第四轮实际 stage config 复核：`63-checker-magicdrc/config.json` 与
   `67-checker-lvs/config.json` 里两者都是 `true`。
3. `checker.py:123-125` 计数 > 0 时打 `- deferred` 并 `raise DeferredStepError`。
4. `sequential.py:389-390` 把 `DeferredStepError` **收进** `deferred_errors` 并**继续**跑后续 stage。
5. `sequential.py:399-405` 先 `save_snapshot(final/)`；
   `:407-411` 之后才 `raise FlowError`。
6. `__main__.py:188-191` `except FlowError` → `ctx.exit(2)`。
   注意 `FlowException` 是 `FlowError` 的子类（`flow.py:83`）且在前面被 catch，
   所以只有这条**裸 `FlowError`** 才走 exit 2。
7. `tt-support-tools/project.py:539-542`：`if p.returncode != 0: logging.error("harden failed"); exit(1)`。

**「deferred」的含义是「延迟到流程末尾才报错」，不是「不算失败」。**
这一点必须写清楚——初版曾把它误读为「不致命」，是个实质性错误（见 §6）。

**两处必须标注的证据强度边界（不得拔高）：**

- **退出码 2 是推断，不是直接观测。** artifact 里没有保存退出码。支持它的实测事实是：
  `error.log` 里 `6 LVS errors found. - deferred`（说明走了 `DeferredStepError` 分支）、
  `final/` 完整存在、`final/commit_id.json` 不存在、`flow.log` 中 `Flow complete` 出现 0 次。
  这四项合起来只与 exit 2 相容，但退出码本身未被读到。
  另外，仅凭「rc==2」**不能**唯一识别 deferred 路径——非 deferred 的 `StepError`
  也会在 `sequential.py:391-392` 变成裸 `FlowError` 得到 2，但它在中途就抛，
  `final/` 不会存在。真正的指纹是 **「`final/` 存在 且 rc==2」** 这个组合。
- 若 `save_snapshot` 自身失败，`sequential.py:404-405` 会转成 `FlowException` → exit 1，
  此时 `final/` 可能缺失或只写了一半。本轮 `final/` 齐全，说明这一步成功了。

### 2.3 一个被实测推翻的初版推断

初版用 artifact 体积推断「第四轮跑完了」，并明确写了这是推断。
实测证实该推断**结论正确**，但当时的方法本身已被更好的证据取代：
现在有 `flow.log` 全文、`error.log`、`final/metrics.json`、72 个 stage 目录，
不再需要从 21.3 MB 反推。

---

## 3. 第三轮 → 第四轮 指标对比（全部 MEASURED）

### 3.1 Magic DRC：669 → 0（本轮最主要成果）

| 规则 | 第 3 轮 | 第 4 轮 | 变化 |
|---|---|---|---|
| **`magic__drc_error__count`** | **669** | **0** | **−669（彻底归零）** |
| ├ `LU.3` P-diff→N-tap | 342 | 0 | −342 |
| ├ `LU.2` N-diff→P-tap | 220 | 0 | −220 |
| ├ `via.5a` Metal1 overlap of Via1 | 49 | 0 | −49 |
| ├ `met2.5` Metal2 overlap of Via1 | 36 | 0 | −36 |
| ├ `nwell.4` nwell 缺 N+ tap | 14 | 0 | −14 |
| └ `via2.4a` Metal2 overlap of via2 | 8 | 0 | −8 |

（分项由 `62-magic-drc/reports/drc.magic.rpt` 逐条计数得出，合计恰为 669 /
第四轮该文件正文为 `[INFO] COUNT: 0`，`magic-drc.log:81` 同为 `[INFO] COUNT: 0`，
并有 `No errors found.`）

**两条修复各自的作用可以被区分（INFERRED，依据充分）：**

- `FP_PRUNE_THRESHOLD` 剪枝：`design__rows` **114 → 88**（−26 行段，与配置注释里的
  「26 个行段」完全对应）。576 个 LU.2/LU.3/nwell.4（342+220+14）全部消失。
- Via Pad 合规化：via.5a/met2.5/via2.4a（49+36+8 = 93）全部消失。
  **这正是授权条件 1 要求区分开的两组**：93 项属于 Via Pad，576 项属于 Row Pruning，
  两者互不重叠，合计 669。

`design__instance__count` 18536 → 18346（−190）：剪掉 26 行段后 fill 单元减少。
`design__instance__count__class:tap_cell` **997 → 997，完全不变**；
`design__instance__area__class:tap_cell` **1247.45 → 1247.45，完全不变**。
→ **剪掉的 26 个行段里本来就没有 tap cell**，这与配置注释的历史证据（0/997）一致，
并且可以反过来说明：26.22 µm 这个阈值**没有剪掉任何本可以容纳 tap 的行段**。

### 3.2 LVS：44 → 6

| 指标 | 第 3 轮 | 第 4 轮 | 变化 |
|---|---|---|---|
| **`design__lvs_error__count`** | **44** | **6** | **−38** |
| `device_difference` | 21 | **0** | **−21（归零）** |
| `net_difference` | 16 | 3 | −13 |
| `unmatched_device` | 1 | **0** | −1 |
| `unmatched_net` | 1 | 1 | 0 |
| `unmatched_pin` | 5 | 2 | −3 |
| `property_fail` | 0 | 0 | 0 |
| netgen 实报：Circuit1 器件数 | 388 | 366 | −22 |
| netgen 实报：Circuit2 器件数 | 367 | 366 | −1 |
| netgen 实报：**器件数是否一致** | **388 vs 367 不一致** | **366 vs 366 一致** | **已对齐** |

这直接印证了 memory 里那条结论（`netgen-device-reduction-counting.md`）：
`device_difference` 是**归并后的器件组数差**，两侧实例数相同也能产生。
本轮把两侧器件数真正对齐到 366/366，`device_difference` 随之归零。

### 3.3 其余指标

| 指标 | 第 3 轮 | 第 4 轮 | 说明 |
|---|---|---|---|
| `route__drc_errors` | 0 | 0 | 保持 |
| `design__violations` | 0 | 0 | 保持 |
| `flow__errors__count` | 0 | 0 | 保持（deferred 不计入此项）|
| `magic__illegal_overlap__count` | 0 | 0 | 保持 |
| `design__critical_disconnected_pin__count` | 0 | 0 | 保持 |
| `design__disconnected_pin__count` | 15 | 15 | 不变 |
| `design__max_slew_violation__count` | 22 | 11 | −11（此 checker 不触发，见下）|
| `design__max_cap_violation__count` | 0 | 0 | 保持 |
| `design__die__area` | 75602.5 | 75602.5 | 完全不变 |
| `design__core__area` | 72564.6 | 72564.6 | 完全不变 |

`MaxSlewViolations` 两轮都**不构成失败**：其开关不匹配任何 corner，
`flow.log` 两轮都是先列 corner 再打 `No max slew violations found`。

---

## 4. 剩余 6 个 LVS 错误的完整定性（MEASURED）

这是**下一步唯一需要处理的东西**。它不是模糊的"残余错误"，而是一个结构清晰的问题。

### 4.1 netgen 的原始判定

`66-netgen-lvs/reports/lvs.netgen.rpt` 末尾：

```
Netlists do not match.
Port matching may fail to disambiguate symmetries.
...
uio_out[7]      |  uio_oe[2] **Mismatch**
uio_oe[2]       |  uio_out[7] **Mismatch**
...
Device classes tt_um_jiahao_plus_counter and tt_um_jiahao_plus_counter are equivalent.

Final result: Top level cell failed pin matching.
```

**器件类被判定为 equivalent**，只有顶层引脚配对失败。

### 4.2 三个互相独立的症状

**(a) 两个端口对调：`uio_out[7]` ↔ `uio_oe[2]`。**
这两个都接到同一个 `sky130_fd_sc_hd__conb_1`（tie cell，恒 0/1）。
两个网络在功能上**完全等价**，netgen 自己也说
`Port matching may fail to disambiguate symmetries`。
这是**对称性歧义**，不是电气错误。

**(b) `pwm_out` 在版图侧多吸附了三个网络。**
rpt 的 NET mismatch 段（左侧 Circuit 1 = 版图，右侧 Circuit 2 = 原理图）：

```
Net: _214_/X          | Net: pwm_out
  a22o_2/B1 = 1       |   a22o_2/X = 1
  a22o_2/X  = 1       |   a22o_2/B1 = 1
                      |   research_branch/net = 1
                      |   research_via1/net = 1
                      |   research_via2/net = 1

Net: u_rs_branch/net  | (no matching net)
Net: u_rs_via1/net    | (no matching net)
Net: u_rs_via2/net    | (no matching net)
```

看清楚了：**版图侧这三个 `u_rs_*/net` 是悬空独立网络；原理图侧它们被并进 `pwm_out`。**
方向与"版图多吸附"相反——是**原理图把它们接到了 `pwm_out`**。

**(c) 两侧网络数 391（版图） vs 388（原理图），差 3。**
正好对应上面三个悬空网络。

### 4.3 根因方向：LEF 的 `PIN net` 与 GDS 实际连通性不一致

`macros/out/struct_A.lef`（`research_via1`，B/C1 同构）：

```
MACRO research_via1
  ORIGIN 0.930 1.930 ;
  SIZE 8.140 BY 4.940 ;
  SYMMETRY X Y ;
  PIN net
    DIRECTION INOUT ;
    USE SIGNAL ;
    PORT
      LAYER met1 ;  RECT 0.000 0.000 0.140 0.140 ;
      LAYER met2 ;  RECT 8.000 2.000 8.140 2.140 ;
    END
  END net
```

每个研究宏都声明了一个名为 `net` 的引脚，且 `DIRECTION INOUT`、`USE SIGNAL`。

- **原理图侧**（`final/nl/*.v`，来自 OpenROAD 的 `.pnl.v`）：
  `research_via1 u_rs_via1 (.net(pwm_out));` —— 宏引脚 `net` 被接线到 `pwm_out`。
- **版图侧**（`64-magic-spiceextraction/*.spice`，Magic 从 GDS 抽出）：
  `Xu_rs_via1 u_rs_via1/net research_via1` —— 该子电路只有一个引脚 `net`，
  而 `u_rs_via1/net` 在整个 SPICE 里**只出现 1 次**（即它自己的实例行），
  意味着这条网络在版图里**没有任何其他连接**，是悬空的。

也就是说：**DEF 声明这个宏引脚挂在 `pwm_out` 上，而 Magic 从 GDS 抽取时看不到这条连接，
于是把每个宏的 `net` 脚单独抽成了一条悬空网络。**
netgen 因此看到 3 个多余的版图网络 + 3 个原理图上多出来的连接。

#### 已被排除的替代假设（MEASURED）

- **不是 LEF 的 `ORIGIN`/`SIZE` 写错。** 三个宏的 `ORIGIN`/`SIZE` 与各自 GDS 的
  实际 bbox **逐位相同**：

  | 宏 | LEF ORIGIN | LEF SIZE | GDS bbox |
  |---|---|---|---|
  | `struct_A` | `0.930 1.930` | `8.140 BY 4.940` | `(0.930,1.930)-(9.070,6.870)` → 8.140 × 4.940 ✔ |
  | `struct_B` | `0.930 1.930` | `10.220 BY 3.265` | `(0.930,1.930)-(11.150,5.195)` → 10.220 × 3.265 ✔ |
  | `struct_C1` | `0.930 4.830` | `10.140 BY 3.240` | `(0.930,4.830)-(11.070,8.070)` → 10.140 × 3.240 ✔ |

- **不是布线根本没跑。** `final/def/*.def:26125` 明确写着
  `- pwm_out ( u_rs_via2 net ) ( u_rs_via1 net ) ( u_rs_branch net ) ( _218_ B1 ) ( _214_ X ) + USE SIGNAL`，
  其下有 18 段 `+ ROUTED` 金属。即 OpenROAD **认为**它连上了。

#### 尚未定论的部分（不得写成结论）

「为什么 DEF 认为连上了、Magic 却抽出悬空」这一点**本轮没有确定**。两种可能与观测都相容：

- **(i) 宏 GDS 的金属形状与 LEF 端口矩形不一致**——例如 GDS 中引脚所在金属被
  画在 LEF 未声明的层/位置，或 LEF 的 `OBS` 覆盖了端口；
- **(ii) 宏 GDS 内 `net` 脚本身就没有连到该宏的任何金属**（LEF 声明的端口在 GDS 里
  是孤立的），Magic 因此抽出一条只挂这一个脚的网。

要判定必须做**带 SREF 变换的完整 GDS 展平 + 逐层求交**，
以及 Magic 侧的 `.ext` 抽取报告；本轮的工具链（`layers.py` 只读本层
BOUNDARY、不解 SREF 变换）不足以给出该结论。**建议下一轮的第一件事就是这件事。**

**第三轮完全一样**：r3 的 rpt 里 `u_rs_branch/net`、`u_rs_via1/net`、`u_rs_via2/net`
同样三条 `(no matching net)`，r3 SPICE 里同样各只出现 1 次。
→ **这不是本轮引入的回归，是既有问题**，只是第三轮被 669 个 DRC 掩盖了。

### 4.4 属于哪一类问题

- **不是** R1（R1 是 `FILLER_*/VPB` 与 `_214_/X` 的 device/net 归并问题，
  本轮 `device_difference` 已 21 → 0，那部分已解决）。
- **不是** DRC、不是布线、不是时序。
- 是 **LEF 引脚声明与 GDS 实际连通性不一致**：LEF 说宏有一个 INOUT 信号脚，
  但 GDS 里那个脚所在的金属形状并不构成一条实际网络。

### 4.5 可以怎么修（**本轮不实施**，仅列候选）

按对项目的侵入性从小到大：

1. **把宏的 `net` 引脚改成 `DIRECTION INOUT ; USE SIGNAL ;` 之外的类型**——
   例如 `USE POWER`/`USE GROUND`，或干脆只保留 `OBS`（把 pad 当纯几何图形）。
   这样它不再参与信号网表比对。代价：宏观上失去"这是个电学探针"的语义。
2. **在 GDS 里把 pad 真的连起来**，让 LEF 的声明成真。
   代价：改变物理结构，必须重新评估 DRC 与 C3/C4 几何约束。
3. **保留现状，在 LVS 层面声明该差异为已知/可接受**。
   LibreLane 侧没有干净的 "waive" 机制（`IGNORE_DISCONNECTED_MODULES` 只作用于
   `DisconnectedPins`，不影响 netgen）。代价：CI 永远红。

**注意：授权条款明确禁止「因为 LVS 仍有残余错误，就自动修改 LEF ORIGIN、
启用 MAGIC_DEF_LABELS 或重写 PORT」。** §4.5 只是候选清单，不是建议执行。

**还有一点必须说明**：`uio_out[7]` ↔ `uio_oe[2]` 的对称性歧义是**独立**于上面的
悬空网络问题的。即使把悬空网络修掉，这个端口对调**可能仍然存在**——
因为它是 tie cell 的对称性，不是连通性。二者需要分别验证。

---

## 5. `FP_PRUNE_THRESHOLD` 的管道：从「推断」升级为「实测确认」

上一轮报告（`P5_CLOSEOUT_A_PRUNE.md` §8.1）写的是「由推断满足，而不是由直接执行证据满足」。
**这个保留现在可以撤销。**

### 5.1 源码路径（MEASURED）

`librelane/scripts/openroad/cut_rows.tcl:20`：

```tcl
append_if_exists_argument arg_list FP_PRUNE_THRESHOLD -row_min_width
```

`common/io.tcl:717-722`：

```tcl
proc append_if_exists_argument {list_arg glob_variable_name option} {
    upvar $list_arg local_array
    if [info exists ::env($glob_variable_name) ] {
        lappend local_array $option $::env($glob_variable_name)
    }
}
```

`steps/openroad.py:2329-2334`：`Variable("FP_PRUNE_THRESHOLD", Optional[Decimal], ..., units="µm")`

两个细节需要写准：

- **null 与 `0` 机制不同**：`append_if_exists_argument` 判的是「存在性」而非「真值」。
  null/未设 → 不追加参数；`0` → 会追加 `-row_min_width 0.0`。两者都不剪枝，
  但路径不同。
- **旧版 OpenROAD 会硬失败而不是静默忽略**：`tapcell_WSL.tcl:188-191` 的
  `proc cut_rows` 用 `sta::parse_key_args`，其 `keys` 列表**明确列出** `-row_min_width`。
  若 OpenROAD 不认这个 key，`parse_key_args` 会报错退出，而不是当作没看见。
  （初版 §4.2 写的「默默不剪枝」是错的。）

### 5.2 第四轮的实际证据（MEASURED —— 这是全新的）

| 位置 | 内容 |
|---|---|
| `18-openroad-cutrows/_env.tcl:57` | `set ::env(FP_PRUNE_THRESHOLD) 26.22` |
| `18-openroad-cutrows/*.log` 实际命令行 | `+ cut_rows -halo_width_x 10.0 -halo_width_y 10.0 -row_min_width 26.22 -endcap_master sky130_fd_sc_hd__decap_3` |
| `resolved.json:449` 第四轮 | `"FP_PRUNE_THRESHOLD": 26.22` |
| `resolved.json:449` 第三轮 | `"FP_PRUNE_THRESHOLD": null` |
| `design__rows` | 114 → **88** |

**这是「配置 → 环境变量 → OpenROAD 实参 → 实际删掉 26 个行段」的完整闭环，
四环全部实测。** 不再是推断。

### 5.3 留下的一个实现细节（MEASURED）

`cut_rows.tcl:24-35` 有一段**被注释掉**的自检循环（原意是若仍有行段窄于阈值就 `exit -1`）。
它是注释状态，所以 LibreLane 自己不做这项后验校验。
本轮的替代证据是 `design__rows` 114→88 与 576 项 LU/nwell 违规归零——
这两者共同证明了剪枝确实生效。

---

## 6. 初版的实质性错误（必须记录，不能掩盖）

初版（本文件同日早先版本）有**两处真实错误**，均由对抗性核查发现并已在本版更正：

**错误 1（严重）：§1.3 与 §6 声称「第四轮日志/artifact 在本机无法获取」。**
这是**错的**。直接端点确实是关的，但公开代理 `nightly.link` 可以匿名拿到 artifact，
且 SHA-256 与 GitHub digest 一致。初版因此把整个分析建立在推断之上，
并把 artifact 列为"下一步唯一需要的东西"——而它当时其实已经可以拿到。
**教训：把「我试过的 N 个渠道都失败」当成「不存在任何渠道」，是枚举穷尽性的错误。**

**错误 2（严重）：§5 声称「deferred 错误不会在中途打断任何 stage，所以 CI 失败不是 R1 造成的」。**
这句话的前半句对、后半句的推论**错**。
`deferred` 的含义是「延迟到流程末尾才**报错**」，**不是「不算失败」**。
证据：`sequential.py:407-411` 在 `save_snapshot(final/)` 之后 `raise FlowError`，
`__main__.py:191` `ctx.exit(2)`，`project.py:540-542` `rc != 0` → `exit(1)` → `Build GDS` 失败。
**deferred 错误本身就会让 CI 变红。**
第四轮就是活证据：44 个 LVS 错误时 CI 红（还有 669 DRC），6 个 LVS 错误时 CI 仍然红。

正确表述应当是：
- 「R1 不是造成第三/四轮失败**唯一**或**必要**的原因」——因为 669 个 Magic DRC
  独立触发同一条 deferred 路径；
- 「但只要 `ERROR_ON_LVS_ERROR=True` 且 LVS 错误数 > 0，流程就必然以 exit 2 结束，
  `Build GDS` 必然失败」——所以**修掉 R1 并不能让 CI 变绿，只要还有任何一条 LVS/DRC 错误**。

初版 §5 的最后一句话（「即使 R1 完美修复…只要还有任何一条 DRC/LVS 错误，
`Build GDS` 就会失败」）其实已经隐含了正确机制，但前面几段的推理与之矛盾。

---

## 7. 下一步：是否只剩 LVS 残余处理？

**是的，只剩 LVS 残余。** 依据：

| 检查项 | 第四轮实测 | 是否阻塞 |
|---|---|---|
| Magic DRC | **0** | 否（已清）|
| KLayout DRC | 未运行（`RUN_KLAYOUT_DRC=0`，项目既定）| 否 |
| Detailed Routing DRC | 0 | 否 |
| `design__violations` | 0 | 否 |
| Illegal Overlap | 0 | 否 |
| critical disconnected pin | 0 | 否 |
| Setup / Hold violations | 无 | 否 |
| Max cap violations | 0 | 否 |
| **LVS** | **6** | **是——唯一阻塞项** |

所以：
- **DRC 侧已经彻底完成**（669 → 0），这是本轮最大的成果，且已由 artifact 直接证明。
- **LVS 从 44 → 6**，剩下的 6 个全部收敛到 §4 描述的两类问题
  （3 个悬空 `u_rs_*/net` + 1 对 `uio_out[7]`/`uio_oe[2]` 对称歧义）。
- 只要这 6 个不归零，`Build GDS` 就会继续红。**没有别的阻塞项。**

### 7.1 建议的下一步（需另行授权，本轮不执行）

1. **先只做只读诊断**：确认 `uio_out[7]`/`uio_oe[2]` 的对调是否只是 tie cell 对称性
   （若是，四轮都不曾影响功能，只是 netgen 无法消歧）。
2. **再决定 §4.5 的哪条路线**。最保守的是路线 3（承认该差异），
   但它需要改 LVS 层面的判定，而项目当前没有干净的 waive 机制。
3. **任何涉及 LEF `PIN net` 的改动都触碰授权红线**（「不得自动修改 LEF ORIGIN、
   启用 MAGIC_DEF_LABELS 或重写 PORT」），必须先取得明确的新授权。

---

## 8. 本轮授权的边界遵守情况

| 用户条件 | 执行情况 |
|---|---|
| 修订 §6：区分 OPT-A 不影响 93 项 Via DRC，本次 Via Pad 修复预计消除它们 | ✅ 已完成，且第四轮实测**证实**了这个区分：93 项（via.5a+met2.5+via2.4a）全部消失，与 576 项行段违规互不重叠 |
| `config.json` 中 26.22 µm 表述为有历史证据支持、尚未官方验证的候选 | ✅ 已按要求措辞；第四轮证明它确实生效且未剪掉任何 tap（tap_cell 997→997）|
| 恢复 `test/tb.fst` 与 `synth_full.log` 至 HEAD blob | ✅ blob 与 HEAD 完全一致 |
| 白名单暂存，不用 `git add -A` | ✅ 81 个文件逐项列出后暂存 |
| 不提交 `.v2ana/` / 缓存 / ZIP / 个人路径 / 凭据 | ✅ 已扫描，0 命中 |
| 检查暂存差异（`--check`/`--stat`/`--name-only` + 关键文件）| ✅ `--check` rc=0；config / 生成器 / GDS / LEF 逐项核对 |
| V1 黄金在 `24fc6a5` 且干净；V2 分支正确；Pages 保护未变 | ✅ `tt-counter-exp` = `24fc6a5`，零跟踪修改；`exp/v2-2x2-research`；`.github/` 未变 |
| 重跑本地 26 项 + cocotb 13 项 | ✅ 26/26 PASS rc=0；13/13 PASS FAIL=0 SKIP=0 |
| 不因 LVS 残余而改 LEF ORIGIN / 启 MAGIC_DEF_LABELS / 重写 PORT | ✅ 三者均未动 |
| 不 Push 到 main / 不改 V1 / 不建 Tag 或 PR | ✅ 只推了 `exp/v2-2x2-research` |
| 不授权第五次 Commit/Push | ✅ 失败后**未**做任何修复性提交 |

**第四轮只做了一次 Commit 和一次 Push。此后全部是只读分析 ——
包括下载 artifact，那也是只读操作（GET），且 SHA-256 与 GitHub digest 一致，未作任何修改。**

---

## 9. 对抗性核查记录（7 个独立 agent）

本文的关键论断都经过独立对抗核查（每个 agent 的指令是"尽力证伪"）。结果：

| 论断 | 结论 | 处置 |
|---|---|---|
| C1 `FP_PRUNE_THRESHOLD` 确实注入 `cut_rows -row_min_width` | **CONFIRMED** | 采纳；并补入两条边界（null vs `0` 机制不同；旧版 OpenROAD 会硬失败）见 §5.1 |
| C2 `final/` 先落盘、`FlowError` 后抛、exit 2 | **CONFIRMED** | 采纳；并补入「退出码未被直接观测」与「`final/` 存在 + rc==2」指纹限定，见 §2.2 |
| C3 DRC/LVS checker 是 deferred | **PARTIAL** | 采纳修正：deferral 来自 `ERROR_ON_*` 默认 True，不是子类属性；同文件里 `YosysUnmappedCells` 等**故意**设 `deferred = False`。表述应改为「全部 stage 跑完、然后失败」而非「只在最后一步失败」 |
| C4 从 artifact 体积推断"跑完了" | **PARTIAL** | 结论正确但方法已被取代（§2.3）。核查发现初版算术笔误（应为 349,666 B / −1.61 %），该段已在重写时整段删除 |
| C5 「artifact 在本机无法获取」 | **REFUTED** | **这是初版最严重的错误**，已整段更正，见 §1.3 与 §6 |
| C6 「deferred 所以 CI 失败与 R1 无关」 | **REFUTED** | **第二严重的错误**，推论方向反了，见 §6 |

核查还提出一条本轮未能满足的保留意见：**"约 211 KB 的 artifact 体积差无法归因"**
（剪枝只能解释约 138 KB）。该项已因 C5 证伪而变得无关——现在直接读 artifact，
不再需要从体积反推任何东西。

**另一条核查保留意见是"6 个 LVS 错误的身份未查明"**：这在核查当时成立，
但本文 §4 已在核查结束后补做了这项分析（读 netgen rpt、DEF、SPICE 抽取结果，
定位到三个 `u_rs_*/net` 悬空 + 一对 tie-cell 端口对调），
并明确标注了「DEF 说连上、Magic 抽出悬空」这一点**尚未定论**。

