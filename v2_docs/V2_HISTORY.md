# V2 历史与决策记录

本文件把 V2 从基线审计到 α′ 定案的**关键事实**压缩成一页。单轮过程报告
（P3_* 系列）的内容已并入此处；原始长报告不再保留。

完整验收结论见 [V2_FINAL_ACCEPTANCE.md](V2_FINAL_ACCEPTANCE.md)，
最终接口定义见 [V2_FINAL_INTERFACE_DECISION.md](V2_FINAL_INTERFACE_DECISION.md)。

---

## 1. 时间线

| 轮次 | 内容 | Commit | 结果 |
|---|---|---|---|
| P0 | 只读基线审计（V1 黄金 commit 确认、环境清点） | — | PASS |
| P1 | M1-Via1-M2 最小可行性宏 | — | PASS |
| P2 | 七结构几何生成 + 面积预算 + 规则提取 | — | PASS |
| P3-0…P3-3 | 七宏物理集成、放置、本地验证 | — | PASS |
| **CI 第 1 轮** | 首次官方 GDS 构建 | `45e629e` | **失败**：`research_macros.v` 在 `v2_rtl/` 而非 `src/`，构建在 "Fetch verilog and build config" 阶段就停了，**从未进入 P&R** |
| 修复 1 | `git mv v2_rtl/research_macros.v src/`；同步 `test/Makefile`、`synth_check.ys`、`p3_integration_matrix.py`；新增 `tools/check_source_files.py` | 未提交 | PASS（本地）|
| **CI 第 2 轮** | 第二次官方 GDS 构建 | `6eb6eb5` | **失败**：`OpenROAD.CheckMacroInstances` —— yosys 把 A/B/C1/C3 四个电气宏删掉了 |
| 修复 2 | 七个模块全部改 `(* blackbox *) (* keep *)` 且**无模块体** | 未提交 | PASS（本地）|
| P4 | 官方规则研究、架构决策、五视图契约 | 未提交 | CONDITIONAL → 用户纠正判据 |
| **接口定案** | α′：1 PIN / 1 PORT / 多跨层几何 | 未提交 | **本轮 10/10 本地验收 PASS** |

远程分支 `origin/exp/v2-2x2-research` 停在 `6eb6eb5`。**本轮的 α′ 改动尚未 Commit。**

---

## 2. 两次 CI 失败的真实根因

### 2.1 第 1 轮：文件放错目录

`info.yaml` 的 `source_files` 路径以 `src/` 为基准。文件实际在 `v2_rtl/`，
官方构建连 Verilog 都没读全，直接停在 config 阶段。

**教训**：官方构建只认 `src/`。`tools/check_source_files.py` 现在断言
`info.yaml` / `src/` / `test/Makefile` 三者一致，防止复发。

### 2.2 第 2 轮：空模块被 yosys 优化掉

两个独立机制，缺一不可：

| 机制 | 证据 |
|---|---|
| `(* keep *)` 单独不够 | 控制实验 `_t3.v`：`m_plain` 被删、`m_keep` 存活但输出被常量折叠 |
| `write_verilog` 会内联**有模块体**的模块 | 控制实验 `_t4.v`：`bb_port` 被写出，`body_port` 没有 |

**修复**：七个模块全部 `(* blackbox *) (* keep *)` **且无 body**。
本地复现命令见 `macros/p3_synth_netlist_check.py`。

---

## 3. 判据纠错记录（最重要的一节）

### 3.1 错误判据：`所有 PIN 必须在同一 GDS 连通分量`

我最初用这条作为"能否有电气端口"的准入条件。**用户指出这是错的**：

> 普通多 Net 宏的 PIN 可以分别位于不同连通分量；
> 相反，同一 GDS 连通分量上的多个 PIN，如果被连接到不同逻辑 Net，
> 才需要特别警惕物理短接与网表不一致。

这条纠正把 A/B/C1 从"合规"翻成"有问题"：它们原有 2 个 PIN 分属两 net，
而物理上是一个节点 —— 那是**物理短路被拆成两个逻辑 net**。

### 3.2 错误接口：α（多 PORT）

我曾想用"1 PIN + 多 PORT"表达一个节点。**用户指出 LEF/DEF 5.8 语义**：

| 结构 | 语义 | 路由器行为 |
|---|---|---|
| 同一 PIN 下多个 PORT | **弱连接** | 各 PORT 不保证连通，信号路由不适用 |
| 同一 PORT 内多个几何 | **强连接** | 视为一个接入点 |

并且：**V1 的 VGND 多 PORT 不能作为依据** —— VGND 是电源网，电源路由器
对多 PORT 的处理与信号路由器不同。

**最终接口 α′**：1 PIN → 1 PORT → PORT 内多个跨层 LAYER/RECT。

### 3.3 被撤回的五条过度推断

- "因为 `MAGIC_EXT_USE_GDS=False`，所以 A/B/C1 必然不触发 LVS 问题"
- "LEF 解析成功 == Pin Access 成功"
- "SPICE 是必需产物"（官方文档写的是 Optional）
- "5 µm 间距可以降到 3 µm"（未经批准，已恢复）
- "C3 的 8 个导体必须有 8 个 PIN"（技术上合法，但会污染间距测量）

---

## 4. 用户定的三条决策

| # | 决策 | 状态 |
|---|---|---|
| 1 | `research_dense` 保持 **N** 朝向（不改） | 已执行 |
| 2 | 最小宏间距恢复 **5.00 µm**，并写成断言 | 已执行（实测最小 5.10 µm）|
| 3 | GitHub Pages 采用 **R1 + R2** 双重保护 | 已执行（备份在 `v2_validation/v1_pages_backup/`，已 gitignore）|

---

## 5. 环境事实（影响所有结论的口径）

| 项 | 事实 |
|---|---|
| **本地无 SKY130 PDK** | `extract_rules.py` 的规则来自实测/官方文档，不是本地 PDK 提取 |
| **本地 yosys 0.69** | 官方 LibreLane 3.0.14 用 0.62。`blackbox`+`keep` 行为已用控制实验复现一致，但**不是逐字节复现** |
| **本地无 KLayout 脚本能力** | KLayout 0.26.2 Ruby 解释器在 headless（`-b`/`-r`/`-rm`）下 SIGSEGV。改用 `pya.Region` 原生 API 实现 BEOL 规则，标注为 `LOCAL_GEOM_DRC` 而非 `OFFICIAL_DRC` |
| **本机 hosts 封锁 27 个 GitHub 域** | 学校管理设备，**不擅自修改 hosts 或绕过**。SSH（`ssh.github.com:443`）可用，HTTPS 不可用 → **CI 结果读不到** |

**第 4 条是硬约束**：Push 能成功，但读不回 CI 结果。这不是 FAIL，是 BLOCKED。

---

## 6. 研究真值的三层区分

| 层级 | 含义 | 状态 |
|---|---|---|
| **T1** | GDS 中确实存在 Via 连接 | ✅ 已实测 |
| **T2** | 该连通域被分配到功能信号 Net | ✅ 已实测（`pwm_out`）|
| **T3** | 功能电流必须经过该 Via | ❌ 未验证，**不声称** |

本课题的目标是 **T1 和 T2**。T3 需要电流路径分析 + 物理证据（IR drop、电迁移），
当前无任何证据。

---

## 7. 早期已被推翻的产物（已删除，勿再引用）

| 产物 | 为什么废弃 |
|---|---|
| `v2_validation/tb_v2_smoke.v` | 一次性冒烟测试，cocotb 13/13 已覆盖同等功能 |
| `v2_validation/synth_check.ys` | 早期综合脚本，已由 `p3_synth_netlist_check.py` 取代 |
| `v2_rtl/project_v1_reference.v` | V1 只读参照，以 git 历史 `24fc6a5` 为准 |
| `v2_rtl/patch_project_v2.py` | 一次性文本补丁脚本，已由人工编辑 + 断言取代 |
| `v2_validation/klayout_headless_crash.txt` | 崩溃记录，结论已并入本文件 §5 |
| `macros/out/drc_result.json` | P1 单次可行性 DRC 结果，已由覆盖七宏的 `macros/out/drc_all.json` 取代 |
| 六份 `P3_*.md` 单轮报告 | 内容已压缩进本文件 |
| `v2_docs/V2_BASELINE_AUDIT.md`、`v2_docs/V2_PROGRESS_P0_P2.md` | 早期阶段报告，内容已压缩进本文件 |

> 注：`macros/out/feasibility_via.*` 与 `macros/feasibility_via_macro.py` **仍然存在且被跟踪**，
> 它是 P1 最小可行性试验的留存记录，不是废弃产物。七宏的正式产物是 `struct_*.{gds,lef}`。
