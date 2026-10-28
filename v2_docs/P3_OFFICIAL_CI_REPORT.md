# P3 首次官方 CI 验收报告

日期：2026-10-28
分支：`exp/v2-2x2-research`
Commit：**`45e629e32db73fe57d7a029085c764618820b0bb`**
推送状态：✅ **成功**（本地与远程一致）

---

## 0. 执行摘要

| 项 | 状态 |
|---|---|
| Git Commit | ✅ **`45e629e`** 已完成 |
| Git Push | ✅ **成功**，`origin/exp/v2-2x2-research` = `45e629e` |
| GitHub Actions 触发 | ❓ **推测已触发，但无法确认** |
| CI 结果获取 | ❌ **BLOCKED** —— 本机 hosts 屏蔽 GitHub |
| 七结构最终验收 | ❌ **NOT_RUN** —— 需 CI 产物 |
| 官方 Precheck/DRC/LVS/STA | ❌ **NOT_RUN** —— 需 CI |

**结论：Push 已完成，但本机无法读取 CI 结果。下面详细说明。**

---

## 1. Commit 与 Push 的完整证据

### 1.1 Commit

```
45e629e32db73fe57d7a029085c764618820b0bb
v2: integrate all seven research structures for 2x2 first official CI
45 files changed, 4257 insertions(+), 33 deletions(-)
```

### 1.2 Push

```
$ git push -u origin exp/v2-2x2-research
To github.com:jiahao-plus/tt-counter.git
 * [new branch]      exp/v2-2x2-research -> exp/v2-2x2-research
branch 'exp/v2-2x2-research' set up to track 'origin/exp/v2-2x2-research'.
```

### 1.3 远程确认（SSH 协议，不受 hosts 影响）

```
$ git ls-remote origin
9ecb930a2ae4a8b1f76cc06f3ec4ed475b3a165e	HEAD
24fc6a5be9271d023a20961d40685719b7e9f755	refs/heads/exp/ip-integration
45e629e32db73fe57d7a029085c764618820b0bb	refs/heads/exp/v2-2x2-research   <-- 新分支
9ecb930a2ae4a8b1f76cc06f3ec4ed475b3a165e	refs/heads/main
```

**本地 HEAD == 远程分支引用，Push 确认成功。**

### 1.4 SSH 身份验证

```
$ ssh -T git@github.com
Hi jiahao-plus! You've successfully authenticated, but GitHub does not
provide shell access.
```

账户正确：`jiahao-plus`。远程仓库正确：`git@github.com:jiahao-plus/tt-counter.git`。

---

## 2. BLOCKED：无法获取 CI 结果

### 2.1 现象

| 端点 | 结果 |
|---|---|
| `https://api.github.com` | HTTP **000**（连接失败） |
| `https://github.com` | HTTP **000** |
| `https://raw.githubusercontent.com` | HTTP **000** |
| `https://codeload.github.com` | HTTP **000** |
| `https://www.baidu.com` | HTTP **000** |
| `https://pypi.org` | HTTP **000** |
| SSH `git@ssh.github.com:443` | ✅ **可用**（Push 走的就是这条） |

### 2.2 根因

**本机 hosts 文件把 20+ 个 GitHub 域名映射到 `127.0.0.1`。**

`C:\Windows\System32\drivers\etc\hosts`（72 行）与
WSL `/etc/hosts` 中均包含：

```
127.0.0.1 github.com
127.0.0.1 api.github.com
127.0.0.1 raw.githubusercontent.com
127.0.0.1 objects.githubusercontent.com
127.0.0.1 codeload.github.com      (若存在)
127.0.0.1 pages.github.com
127.0.0.1 gist.github.com
127.0.0.1 github.io
127.0.0.1 www.github.io
127.0.0.1 github.dev
127.0.0.1 github.githubassets.com
127.0.0.1 *.githubusercontent.com  (共 10 条)
...
```

同文件还屏蔽了 Steam、YouTube、HuggingFace 等（推测是某种网络加速/屏蔽工具写入）。

`getent hosts api.github.com` → `127.0.0.1`，确认是 hosts 而非 DNS 服务器问题。

### 2.3 为什么 Push 能成功

Push 走的是 `ssh.github.com:443`（我在 `~/.ssh/config` 里配的别名），
该域名**不在** hosts 屏蔽列表里，所以 SSH 通道正常。

但 GitHub Actions 的日志/产物下载必须走 HTTPS（`api.github.com`、
`codeload.github.com`），全部被 hosts 拦截。

### 2.4 这是 BLOCKED，不是 FAIL

- **不是** CI 失败——CI 很可能正在运行或已完成
- **不是** 设计问题——是本地网络配置阻止了结果读取
- **未经验证** 的任何 CI 结论都不能写进报告

---

## 3. 逐项状态

### 3.1 已完成的本地检查（在 Commit 前全部通过）

| # | 检查 | 结果 | 证据 |
|---|---|---|---|
| 1 | 七宏几何 DRC | ✅ `LOCAL_GEOM_DRC` PASS ×7 | `macros/out/drc_all.json` |
| 2 | 七宏拓扑 | ✅ `LOCAL_TOPOLOGY_CHECK` PASS ×7 | `macros/out/topology_verify.json` |
| 3 | DRC 负向对照 | ✅ 3/3 违规被抓 | `macros/_negative_control.py` |
| 4 | `RTL_SYNTHESIS` | ✅ 七宏全部存活 | yosys 0.69 |
| 5 | `RTL_SIMULATION` | ✅ 4/4 功能检查 | iverilog 11.0 |
| 6 | 四源放置一致性（含 5 µm 断言） | ✅ PASS | `P3_MACRO_BBOX.csv` 等 |
| 7 | 宏视图一致性（prB/LEF/GDS/PIN） | ✅ ALL CONSISTENT | `P3_MACRO_VIEW_CONSISTENCY.json` |
| 8 | 电气连通性（PIN/Net/分量） | ✅ PASS | `P3_ELECTRICAL_CONNECTIVITY.json` |
| 9 | 七结构全部保留 | ✅ 7/7 | `p3_placement.json` |
| 10 | 最小宏间距 ≥ 5.00 µm | ✅ 实测 5.10 µm | 断言通过 |
| 11 | V1 黄金 commit 未变 | ✅ `24fc6a5`，零改动 | `git status` |
| 12 | 无敏感凭据 | ✅ 扫描 0 命中 | 提交前扫描 |
| 13 | viewer 不从 V2 部署 | ✅ `if` 条件已验证 | `gds.yaml` |

### 3.2 需要 CI 但当前无法验证

| # | 检查 | 状态 | 阻塞原因 |
|---|---|---|---|
| 14 | `OFFICIAL_GDS_ACTION` | ❌ **BLOCKED** | 无法读取 Actions 状态 |
| 15 | `OFFICIAL_PRECHECK` | ❌ **BLOCKED** | 同上 |
| 16 | `OFFICIAL_DRC` | ❌ **BLOCKED** | 同上 |
| 17 | `OFFICIAL_LVS` | ❌ **BLOCKED** | 同上 |
| 18 | `OFFICIAL_STA` | ❌ **BLOCKED** | 同上 |
| 19 | 门级仿真（GL test） | ❌ **BLOCKED** | 同上 |
| 20 | 最终 GDS 中七结构存在性 | ❌ **NOT_RUN** | 无 GDS 产物 |
| 21 | 真实 2×2 Core 尺寸 | ❌ **NOT_RUN** | 无 DEF |
| 22 | 真实 PDN 布局与遮挡 | ❌ **NOT_RUN** | 无 DEF |
| 23 | 宏实际放置坐标 | ❌ **NOT_RUN** | 无 DEF |
| 24 | `research_dense` 五档线宽完整性 | ❌ **NOT_RUN** | 无 GDS |

**未执行 = 未验证。不做任何推断。**

---

## 4. 七结构验收矩阵（当前状态）

| Tag | 宏 | 本地集成 | 本地 DRC | 本地拓扑 | 最终 GDS | 官方 DRC | LVS |
|---|---|---|---|---|---|---|---|
| A | `research_via1` | ✅ | ✅ | ✅ | ❌ NOT_RUN | ❌ BLOCKED | ❌ BLOCKED |
| B | `research_via2` | ✅ | ✅ | ✅ | ❌ NOT_RUN | ❌ BLOCKED | ❌ BLOCKED |
| C1 | `research_branch` | ✅ | ✅ | ✅ | ❌ NOT_RUN | ❌ BLOCKED | ❌ BLOCKED |
| C3 | `research_near` | ✅ | ✅ | ✅ | ❌ NOT_RUN | ❌ BLOCKED | ❌ BLOCKED |
| C4 | `research_cross` | ✅ | ✅ | ✅ | ❌ NOT_RUN | ❌ BLOCKED | ❌ BLOCKED |
| D | `research_dense` | ✅ | ✅ | ✅ | ❌ NOT_RUN | ❌ BLOCKED | ❌ BLOCKED |
| E | `research_fiducial` | ✅ | ✅ | ✅ | ❌ NOT_RUN | ❌ BLOCKED | ❌ BLOCKED |

**七类全部完成本地集成，但无一项完成最终 GDS 验收。**

---

## 5. 解除阻塞的选项

### 选项 A：恢复本机 hosts（推荐，但不擅自执行）

需要你决定并执行的两种方式之一：

**A1. 临时注释 GitHub 相关行**

编辑 `C:\Windows\System32\drivers\etc\hosts`（需管理员权限），
把 26 行 `127.0.0.1 <github-domain>` 前加 `#`。

- 优点：可恢复 CI 结果读取
- 风险：这些条目可能是某个工具刻意写入的（同文件还屏蔽了 Steam/HuggingFace），
  注释后该工具的意图可能被破坏
- **需要你确认是否有意为之**

**A2. 用 SSH 隧道绕过**

可以配置 SOCKS 代理通过 SSH 访问 HTTPS，但需要一台能访问 GitHub 的中转主机。
本机只有一台机器，此方案不可行。

### 选项 B：在 GitHub 网页端查看（需要能访问 GitHub 的设备）

如果你有另一台能访问 `github.com` 的设备（手机、另一台电脑），可以：

1. 打开 https://github.com/jiahao-plus/tt-counter/actions
2. 找到 `exp/v2-2x2-research` 分支的最新 run
3. 查看各 job 状态
4. 下载 artifacts（GDS/DEF/日志）
5. 把文件放到本机，我继续分析

### 选项 C：GitHub CLI（同样受 hosts 影响）

`gh` 也走 HTTPS，同样被拦截。不可行。

---

## 6. 我的建议

**首先请你确认 hosts 里那 26 行 GitHub 屏蔽是否有意为之。**

如果是某个网络工具自动写入的（考虑到同时屏蔽了 Steam/YouTube/HuggingFace，
可能是某种"网络净化"或"防沉迷"工具），那么：

- **不应该**擅自注释它们
- 应该在**能访问 GitHub 的设备**上查看 CI 结果（选项 B）

如果这些条目是历史遗留、你并不需要，那么：

- 注释它们即可恢复（选项 A1）
- 我可以协助验证恢复后的连通性

**无论哪种，我都不会擅自修改你的 hosts 文件。**

---

## 7. 明确声明

### 已完成的

- ✅ Commit `45e629e`（45 文件）
- ✅ Push 到 `origin/exp/v2-2x2-research`
- ✅ 远程引用确认一致
- ✅ 全部 13 项本地检查通过

### 未完成的（BLOCKED / NOT_RUN）

- ❌ 无法确认 CI 是否触发
- ❌ 无法获取任何 CI 状态、日志或产物
- ❌ 无法做七结构最终 GDS 验收
- ❌ 无法确认官方 DRC/LVS/STA/Precheck 是否执行
- ❌ 无法从真实 DEF 获取 Core/PDN/宏坐标

### 不做的事

- ❌ **不**声称 CI 成功（无法观测）
- ❌ **不**声称 CI 失败（同样无法观测）
- ❌ **不**做第二次 Commit 或 Push（未获批准）
- ❌ **不**修改 hosts 文件（你的机器配置）
- ❌ **不**把本地检查结果当作流片签核

---

## 8. 下一步

**需要你决定：**

1. **hosts 里的 GitHub 屏蔽是否有意为之？**
   - 是 → 请用能访问 GitHub 的设备下载 CI 产物（选项 B）
   - 否 → 授权我协助恢复正常访问（选项 A1），我验证后继续

2. **如果暂时无法访问 CI**：本次任务在此 BLOCKED。
   本地工作已尽完成，七结构集成就绪，等待 CI 证据。

**在获得 CI 产物之前，V2 的状态是 `LOCAL_INTEGRATED`，不是 `PHYSICAL_VERIFIED`，
更不是 `SUBMISSION_READY`。**
