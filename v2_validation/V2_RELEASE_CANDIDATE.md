# V2 Release Candidate — 第五轮 CI 预提交报告

编写：2026-10-30
分支：`exp/v2-2x2-research`
基线 Commit：`b4e32b8a2c679619acc03fe3ad415bb476258260`（第四轮，不可变历史基准）
V1 黄金：`24fc6a5be9271d023a20961d40685719b7e9f755`（未触碰）

---

## 1. 已修复的实际缺陷

### 1.1 三宏 LEF 坐标系（第四轮 6 个 LVS 错误的根因）

**缺陷**：`gen_lef.py` 把 `ORIGIN` 设为 GDS bbox 左下角，同时又把每个 RECT 减去同一个
bbox——**双重计数**。OpenROAD 把 `ORIGIN` 加回变换（`abs = place + ORIGIN + RECT`），
Magic 则按 LEF 语义减去它（`abs = place + RECT − ORIGIN`）。两者相差 `2×ORIGIN`，
Magic 因此把三个宏的每个 PIN 都放到宏体之外，抽成悬空网络。

**修复（路线 B）**：只对 A/B/C1 三个电气宏把 cell 几何归一化到 `(0,0)`，
LEF `ORIGIN` 归零，placement 加回同样的偏移。C3/C4/D/E 完全不动。

| 文件 | 改动 |
|---|---|
| `macros/gen_v2_macros.py` | 新增 `NORMALISE = {'A','B','C1'}`，cell 平移 `−bbox_LL`，记录 `local_origin_um` |
| `macros/gen_lef.py` | `ORIGIN` 写 cell 自身 bbox；PINS 用 `local_origin` 换算 |
| `macros/p3_placement_plan.py` | 新增 `place_x_um/place_y_um` = 设计意图 + `local_origin`；间距/重叠/核心包含全部改用真实 footprint |
| `macros/p3_patch_config.py` | 写 `place_*`，不再覆盖成旧值 |

**效果**：8/8 引脚在 OpenROAD 与 Magic 两个模型下**坐标完全相同**（见 §2）。

### 1.2 四个验证器的坐标系缺陷

| 文件 | 缺陷 | 修复 |
|---|---|---|
| `p3_gds_identity.py` | 基线用 `HEAD` 且优先读陈旧缓存（`struct_C1.gds` bbox y=4.870，实际 4.830） | 基线固定为 `b4e32b8`；git 优先、缓存回退；新增 `NORMALISED` 判定（刚性平移后逐矩形相等） |
| `p5_geometry_record.py` | 「几何必须与 HEAD 逐图形相同」的硬前提被路线 B 违反 | 新增 `NORMALISED` 分类，平移量从 HEAD GDS 自行计算，不读生成器 manifest |
| `p5_intrusion_check.py` | `.v2ana/head` 只有 GDS 没有 LEF → PIN 列表为空 → 一切接触都判 off-PIN（**假污染**）；且用 `DEFAULT_MACRO_DIR` 读 LEF 而非配对目录 | LEF 与 GDS 从同一目录取；LEF 缺失时明确报错；历史 GDS 配历史 placement |
| `p3_assert_consistency.py` | `x1 == x+w`、`config == plan.x_um`、MD 表用 `x_um` | 全部改用 `place_*_um` |

### 1.3 文档与代码不一致（P2 独立验证发现）

- **`ena` 不是全局使能**：只出现在 `project.v:56` 且与 `mode == 0` 相与。
  修正 `project.v` 注释与 `README.md`。
- **README「All uio pins are configured as inputs (unused)」是 V1 残留错误**，
  实际 mode 1/2 会驱动 `uio_out[0]`、`uio_oe[0]`、`uio_out[1]`、`uio_oe[1]`。
- **reset 语义**：只有 mode 0 是异步复位，PWM/LFSR 是同步复位。已在 README 说明。

> 这三项都是**文档缺陷**，RTL 未改动一个逻辑门。

### 1.4 生成器自身 bug

`p6_world_equiv.py` 在 WSL 下用字面 `C:\tmp` 作临时目录，创建了名为 `C:tmp` 的垃圾
目录。已修复为 `tempfile.gettempdir()`，工作区已清理。

---

## 2. 三个电气宏：旧新位置与全局几何等价证据

### 2.1 位置（双独立来源：历史 DEF + git baseline）

| 单元 | 第四轮 placement | 第五轮 placement | delta |
|---|---|---|---|
| `research_via1` | (33.500, 208.000) | **(34.430, 209.930)** | (+0.930, +1.930) |
| `research_via2` | (64.000, 208.000) | **(64.930, 209.930)** | (+0.930, +1.930) |
| `research_branch` | (79.320, 208.000) | **(80.250, 212.830)** | (+0.930, +4.830) |

三个 delta 精确等于各自的 `local_origin`。

### 2.2 世界坐标等价（`macros/p6_world_equiv.py`，纳入 27 项检查）

```
cell             polygons   world ok   note
research_via1    7          YES        world coordinates identical
research_via2    6          YES        world coordinates identical
research_branch  13         YES        world coordinates identical
research_near    8          YES        world coordinates identical
research_cross   2          YES        world coordinates identical
research_dense   13         YES        world coordinates identical
research_fiducial 6         YES        world coordinates identical

ROUTE-B WORLD-COORDINATE EQUIVALENCE: PASS
```

方法：参考侧用 `git cat-file blob b4e32b8:macros/out/struct_*.gds` + 历史 DEF 的
COMPONENTS 位置；候选侧用当前 GDS + `src/config.json` 的位置。**逐多边形顶点比对**，
不是 bbox、不是图形数。两条参考链互相独立，均不来自生成器的 manifest。

### 2.3 两工具模型一致（P1 目标达成）

```
struct_A   ORIGIN=(0,0)  met1 OR=34.430,209.930  MG=34.430,209.930  AGREE
                         met2 OR=42.430,211.930  MG=42.430,211.930  AGREE
struct_B   ORIGIN=(0,0)  met2 OR=64.930,209.930  MG=64.930,209.930  AGREE
                         met3 OR=74.850,212.850  MG=74.850,212.850  AGREE
struct_C1  ORIGIN=(0,0)  met1 OR=80.250,212.930  MG=80.250,212.930  AGREE
                         met2 OR=81.250,214.930  MG=81.250,214.930  AGREE
                         met2 OR=85.250,215.430  MG=85.250,215.430  AGREE
                         met2 OR=89.250,215.930  MG=89.250,215.930  AGREE
```

**8/8 完全一致**。这是消除 6 个 LVS 错误的直接前提。

---

## 3. 四个几何宏未变的独立证据

| 单元 | 局部几何 vs `b4e32b8` | LEF 是否改动 |
|---|---|---|
| `research_near` (C3) | **IDENTICAL** | 未改 |
| `research_cross` (C4) | **IDENTICAL** | 未改 |
| `research_dense` (D) | **IDENTICAL** | 未改 |
| `research_fiducial` (E) | **IDENTICAL** | 未改 |

`git diff` 中 `struct_C3/C4/D/E.lef` 无任何变化；对应 `.gds` 已恢复到 HEAD
（几何相同，仅时间戳差异无意义）。

---

## 4. 验证器改动：只改坐标假设，未放宽标准

| 脚本 | 是否放宽 | 说明 |
|---|---|---|
| `p3_gds_identity.py` | **否** | `NORMALISED` 要求平移后**逐矩形完全相等**且 via 同步平移；`GEOM_IDENTICAL` 仍要求逐图形相同 |
| `p5_geometry_record.py` | **否** | 同上；`OTHER` 仍判 FAIL |
| `p5_intrusion_check.py` | **否** | off-PIN 接触仍判 POLLUTION；仅修正了「LEF 缺失导致 PIN 列表为空」的假阳性 |
| `p3_assert_consistency.py` | **否** | 断言未变，只换成正确的坐标字段 |
| `p3_sync_docs.py` | **否** | 文档改为反映真实位置 |

**没有任何一处把 FAIL 改成 WARNING，没有面积豁免阈值，没有坐标白名单。**

关于 C1 的 `0.0434 µm²`：修复后判定为
`CONTACT on PIN x1 (intended net)`——即该外来多边形**同时接触宏金属与 PIN 矩形**，
属于同 Net 合法接入。判定依据是几何关系（`foreign ∩ pin_dil ≠ ∅`），不是豁免规则。

---

## 5. 负向对照结果

### 5.1 既有对照（`_neg_gds_identity.py`）

```
translate_1dbu     CAUGHT=True
widen_1dbu         CAUGHT=True
mirror_x           CAUGHT=True
shrink_wire        rejected=True PASS
move_wire_2um      rejected=True PASS
move_via_cut_1dbu  rejected=True PASS
NEGATIVE CONTROL: PASS (all perturbations detected)
```

### 5.2 新增 `NORMALISED` 路径对照（`C:\tmp\p6\neg_norm.py`）

```
reference: HEAD shifted == current ? True
shift_all_1dbu       CAUGHT=True
widen_met2_1dbu      CAUGHT=True
delete_one_rect      CAUGHT=True
NORMALISED NEGATIVE CONTROL: PASS
```

### 5.3 功能测试非空证明（P2，12 个变异全部捕获）

```
pwm_ge_duty        mismatches=9      FAIL
pwm_no_inc         mismatches=1057   FAIL
count_updown_swap  mismatches=296    FAIL
ena_global         mismatches=263    FAIL
lfsr_shift9        mismatches=120    FAIL
lfsr_fb_tap        mismatches=114    FAIL
lfsr_msb_first     mismatches=28     FAIL
valid_off_by_1     mismatches=64     FAIL
oe_bits_1          mismatches=218    FAIL
default_pwm_leak   mismatches=5      FAIL
count_reset_async  mismatches=3      FAIL
pwm_reset_async    mismatches=1      FAIL
positive control (unchanged):       PASS
```

注意 `ena_global  mismatches=263` —— 如果把 RTL 改成 docstring 字面的「全局使能」，
测试就会失败。这证明测试约束的是**真实 RTL 行为**，不是文档措辞。

### 5.4 对抗性复核（独立 verifier）

**核心功能结论全部被独立复现**：

- 从零重写独立模型（`indep_model.py`，不 import `refmodel.py`），
  8003 随机向量 **0 mismatch**，与 `refmodel.py` 在 60003 个采样点一致。
- 补齐了原报告承认未覆盖的全部空隙：
  - **全 256 个 LFSR 种子**：6659 向量，0 mismatch
  - **全 256 个 PWM duty**：8 × 8387 向量，0 mismatch
  - **全 64 个 mode 值**：387 向量，0 mismatch
  - 三次 12003 向量随机测试，各 0 mismatch
- 重跑 12 个变异对照，数值完全一致（9/1057/296/263/120/114/28/64/218/5/3/1）。

**verifier 同时指出的缺陷（对交付无影响，但如实记录）**：

| 缺陷 | 性质 | 影响 |
|---|---|---|
| `refmodel.py` 假定未复位时 `count=0`（实际是 X） | 临时模型的 bug | **不在仓库**，不影响交付 |
| 若干行号引用错误（如 `refmodel.py:262-270` 等） | 报告瑕疵 | 同上是临时脚本 |
| 测试平台 `MAX_VEC=16384` 会静默截断 | 工具限制 | 主测试只用 3072 向量，未触发 |
| X 检测只判整字节而非逐位 | 工具限制 | 主测试无 X，未触发 |
| 原报告漏检 `summary.md:52` 的「ena 全局使能」 | **已修**（见下） | — |
| 原报告未检查 `docs/info.md` 的种子采样描述 | **已修**（见下） | — |

**已据此修正的两处文档缺陷**：

- `summary.md:52`：`ena 全局使能` → `ena 只在 mode0 生效——不是全局使能`
- `docs/info.md:46`：`seed_value, sampled while rst_n is low`
  → 明确说明是**上升沿同步采样**，rst_n 低电平期间的种子若在下一个上升沿前消失则采不到

---

## 6. 全套本地回归

| 项 | 结果 |
|---|---|
| 本地检查套件 | **27/27 PASS**（新增 `p6_world_equiv.py`） |
| cocotb | **13/13 PASS，FAIL=0，SKIP=0** |
| 独立参考模型仿真（iverilog） | **3072 周期，0 mismatch** |
| 变异测试 | **12/12 捕获** |
| 世界坐标等价 | **PASS（7/7 单元）** |
| 负向对照 | **PASS（含 NORMALISED 新路径）** |
| V1 黄金工作区 | `24fc6a5`，独立 worktree，零跟踪修改 |
| Pages 保护 | `.github/` 未改动 |
| 敏感文件扫描 | 0 命中（无 token/凭据/个人路径） |
| 意外生成物 | 已清理（`C:tmp` 垃圾目录、`synth_full.log`、`test/tb.fst` 均已恢复） |

---

## 7. 第五轮预计能消除哪些 LVS 错误

第四轮 `design__lvs_error__count = 6` 的构成：

| 分项 | 值 | 来源 |
|---|---|---|
| `device_difference` | 0 | — |
| `net_difference` | **3** | 三个悬空 `u_rs_*/net` |
| `unmatched_net` | **1** | 同一组 badnets |
| `unmatched_pin` | **2** | `uio_out[7]` / `uio_oe[2]` |

### 7.1 R3 的根因已被实验推翻重判

我此前把 `uio_out[7]` / `uio_oe[2]` 当作独立的「对称匹配歧义」。**这个判断是错的。**

R3 调查用受控 A/B 实验证明（`C:\tmp\p6\p2\r3\dec2\`，netgen 1.5.133）：

| 变体 | nets c1 / c2 | 判定 |
|---|---|---|
| `A_stub`（3 个悬空 stub，复刻真实缺陷） | **11 / 8** | `Netlists do not match` |
| `B_joined`（stub 并入 `sig`） | **8 / 8** | `Circuits match uniquely` |

**把三个悬空网络连上，LVS 就通过，且完全不动任何端口名。**

端口对调是**下游假象**：net 数不匹配后，两个 conb_1 是仅有的结构可互换实例，
pin resolver 唯一自洽的分配就是把它们对调。旁证：`uio_out[7]` 与 `uio_oe[2]`
恰是提取网表中 **fanout = 1 的两个端口**。

另有两条独立证据（R3 实测）：

1. **最小化复现无法重现原假设**。N ∈ {2,4,8,12,16,24,32} 个相同 tie 驱动的输出，
   16/16 全部 `Circuits match uniquely`。即使 N=32 打印 `**Mismatch**`，
   最终仍判匹配——**单纯端口名不同并不致命**。
2. **所有 matching 侧的补救都失败**：`equate pins`（netgen 报 `No such object`）、
   `ignore class`（删器件、违反禁用 LVS 精神）、`equate classes`、
   各种 no-setup 变体——**无一能补出一条不存在的 net**。

> **重要限定**：R3 的实验在 netgen **1.5.133** 上做，而真实失败来自 **1.5.316**
> （`netgen-lvs.log:1`）。跨版本行为不能假定相同。这一点在 §8 列为风险。

### 7.2 对第五轮的预测

**若 P6 使 Magic 看到正确的端口位置**，则：

- 三个宏的 port 将落在 `pwm_out` 布线所在处（已实测该处有真实金属接触，§7.3）
- → Magic 提取时把它们并入 `pwm_out` 而不是各成孤立 net
- → `net_difference` 3 → 0，`unmatched_net` 1 → 0
- → **端口对调随之消失**，`unmatched_pin` 2 → 0
- → **LVS 6 → 0**

**若 P6 未能让 Magic 合并**（例如 20–70 nm 窄搭接检测失败），则：

- `net_difference` 仍为 3，端口对调仍在
- **LVS 仍是 6**，与第四轮相同

**因此第五轮是一个清晰的二分判据**：LVS 变 0 → 修复生效；LVS 仍 6 → 说明
Magic 的几何合并是瓶颈，需要另找 extraction 侧的解法。

### 7.3 物理连通性（第四轮最终 GDS，实测）

| 宏 | 引脚 | 与顶层 `pwm_out` 金属接触 |
|---|---|---|
| research_via1 | met1 | 0 |
| research_via1 | met2 | **1** |
| research_via2 | met2 | **1** |
| research_via2 | met3 | **1** |
| research_branch | met1 | **1** |
| research_branch | met2a | 0 |
| research_branch | met2b | 0 |
| research_branch | met2c | **1** |

每个宏都至少有一个引脚真实接触 `pwm_out`。物理连通成立，缺的只是提取的正确性。

---

## 8. 其他必须由官方 CI 判断的风险

1. **LVS 是否真的归零**：本机无 LibreLane 3.0.14 与 Magic，无法本地复跑完整提取。
   两个坐标模型的一致性已证明（§2.3），物理连通已实测（§7.3），但 Magic 的实际
   几何合并只能由 CI 判定。
2. **20–70 nm 窄搭接**：3 处真实接触只有 20 nm（via1 met2）、70 nm（via2 met2）、
   20 nm（branch met1）。位置对齐已证明，但 Magic 能否在这些宽度上正确合并
   **只能由 CI 验证**。这是第五轮最可能失败的点。
3. **netgen 版本差异**：真实失败来自 netgen **1.5.316**，而 R3 的全部实验在
   **1.5.133** 上做。跨版本行为不能假定相同；若第五轮仍报端口对调，
   需在 1.5.316 上复核。
4. **`precheck` / `viewer` / `gl_test` 从未运行过**：第四轮全部 skipped。
   即使 LVS 归零，这三个 job 第一次真正执行，可能有全新问题。
5. **Pin Access / Detailed Routing**：LEF 的 `ORIGIN` 变了，但 OpenROAD 看到的
   引脚绝对坐标已验证逐位不变（§2.3），预期无影响；仍需 CI 确认。
6. **`.v2ana/head` 基线未纳入版本控制**：该目录是未跟踪的分析缓存。若在别的环境
   重新生成、或缓存被清理，`p3_gds_identity.py` / `p5_intrusion_check.py` 会回退到
   git 或报错（已实现 fail-loud），但历史 LEF 不会自动重建。
   **这是本地验证环境的已知限制，不影响 CI**（CI 不运行这些脚本）。

---

## 9. 即将 Commit / Push 的文件清单与 SHA 基线

**基线**：`b4e32b8a2c679619acc03fe3ad415bb476258260`

### 设计源（4 个）
```
src/config.json            7 个 placement 更新为 place_*
src/project.v              仅注释（ena 语义）
README.md                  修正 uio / ena / reset 描述
info.yaml                  未改动
```

### 生成器（4 个）
```
macros/gen_v2_macros.py    NORMALISE 归一化
macros/gen_lef.py          ORIGIN/PINS 坐标框架
macros/p3_placement_plan.py  place_* 字段 + 真实 footprint 校验
macros/p3_patch_config.py  写 place_*
```

### 验证器（5 个）
```
macros/p3_gds_identity.py    NORMALISED 判定 + 基线固定 b4e32b8
macros/p5_geometry_record.py NORMALISED 分类
macros/p5_intrusion_check.py LEF/GDS 配对 + 缺失时报错
macros/p3_assert_consistency.py  place_* 坐标
macros/p3_sync_docs.py       文档用真实位置
```

### 新增（3 个）
```
macros/poly_exact.py          精确多边形相交（原为临时脚本，转正式）
macros/p6_world_equiv.py      世界坐标等价验收
macros/_run_all_checks.sh     加入新检查（第 27 项）
```

### 派生（几何，由生成器产出）
```
macros/out/struct_A.gds, struct_B.gds, struct_C1.gds   归一化后
macros/out/struct_A.lef, struct_B.lef, struct_C1.lef   仅 ORIGIN 一行
macros/out/v2_structures.gds, v2_structures_manifest.json, macro_index.json
v2_validation/P3_MACRO_BBOX.csv, p3_placement.json, P3_MACRO_PLACEMENT_PLAN.md
v2_validation/P4_GDS_IDENTITY.{json,md} 及若干自动生成报告
```

### 文档（2 个，新增报告）
```
v2_validation/P5_ROUND4_CI_ANALYSIS.md
v2_validation/P6_LVS_SIX_ROOT_CAUSE.md
```

### 明确不提交
```
.v2ana/            （分析缓存，未跟踪）
macros/out/neg_*.gds（负向对照产物，未跟踪）
```

---

## 10. 为什么值得执行下一轮官方 CI

1. **这是唯一能验证 LVS 修复的方式**。坐标模型一致性已在本地用两条独立参考链证明
   （§2.2、§2.3），但 Magic 的真实提取只能由 CI 跑。
2. **预期结果可证伪**：如果 LVS 不是 6→2，说明我的根因分析有误，`error.log` 会直接
   指出偏差方向。这比继续本地推理更有信息量。
3. **即使失败也不会破坏已通过的项**：OpenROAD 侧引脚绝对坐标逐位不变（§2.3），
   Magic DRC=0 与 Routing DRC=0 的成果应保持不变。
4. **R3 仍会阻塞最终通过**，但拿到第五轮 `error.log` 后，`unmatched_pin` 是否仍是
   那两个端口、是否有新的信息，将决定下一步。

---

## 11. 尚未解决 / 需要你决策的事项

### 11.1 R3 端口匹配（已重新定性，不再是独立阻塞）

**此前的判断「R3 是独立的对称匹配歧义」已被实验推翻。**

真正的关系是：三个悬空 net（P6 修的）**导致**了端口对调。受控 A/B 实验证明
连上三个网后 `Circuits match uniquely`，完全不动端口名。

因此 R3 **不是需要单独解决的问题**，而是 P6 修复的预期副作用。若第五轮
LVS 归零，则 R3 一并解决。

若第五轮 LVS 仍为 6（即 Magic 没能合并那三处 20–70 nm 搭接），则瓶颈在
extraction 侧，需要重新考虑。可选项（**均未实施**）：
- 让 Magic 走 GDS 而非 LEF（`MAGIC_EXT_USE_GDS=1`，但这是验证开关，需另行授权）
- 加宽宏引脚的金属搭接面积（改 GDS）

**注意**：R3 的全部实验在 netgen 1.5.133 上做，真实失败来自 1.5.316。
这个版本差异是已知的不确定点。

### 11.2 Tiny Tapeout 提交路径（需要你决定）

**已确认的事实**：
- `info.yaml` 声明 `tiles: "2x2"`，`top_module: tt_um_jiahao_plus_counter`，正确。
- remote 为 `git@github.com:jiahao-plus/tt-counter.git`（SSH，无 token 泄漏）。
- **`origin/main` 是 `9ecb930`（V1），V2 在 `exp/v2-2x2-research`。**

**风险**：TT 平台按分支索引项目。如果提交时选了默认分支，拿到的是 V1 而不是 V2。

**需要你决定的三条路径**：

| 方案 | 做法 | 对 V1 / Pages 的影响 |
|---|---|---|
| **A（推荐）** | 提交时在 TT app 里**显式选择** `exp/v2-2x2-research` 分支 | 零影响 |
| B | 把 `main` 合并到 V2（或把 V2 合并到 main） | 改变默认分支内容，可能影响 Pages |
| C | 新建独立 V2 仓库 | 需要新远端仓库授权 |

> 注意：TT 的 app 是否支持任意分支选择，我**未能从官方文档直接确认**
> （`tinytapeout.com` 与 WebSearch 在此网络环境下不可用，GitHub API 的
> code-search 需要认证）。这一条标注为 **UNVERIFIED**，需要在提交时
> 在 app 界面上实际确认。

### 11.3 采购与交付

未核查。按授权，购买 Tile / 付款 / 正式 Submit Revision 均需你明确批准。

---

## 12. 请求批准

**请求授权：一次 Commit + 一次 Push 到 `origin/exp/v2-2x2-research`，触发第五轮 CI。**

不含：Push main、PR、Tag、正式 Tiny Tapeout Revision、付款、购买。

第五轮完成后我会只读分析日志，报告是否达到 PHYSICAL_VERIFIED，并明确
R3 是否仍是唯一阻塞项。**不会自动发起第六次提交。**
