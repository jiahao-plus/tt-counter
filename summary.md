# tt-counter-exp — 科研版 IP 集成与可行性验证（本地构建验证）

> 仅本地构建验证；未 push、未投片、未修改只读原目录 `../tt-counter`。
> 所有 PASS 均有真实日志；未执行的项目标注“未验证”。
> 分支：`exp/ip-integration`；基线 HEAD：`9ecb930a2ae4a8b1f76cc06f3ec4ed475b3a165e`（与上游一致）。

## 0. 仓库与产物路径

- 实验仓库（Windows）：`C:\Users\Lenovo\DoubaoWork\chats\2026-10-13\new-chat\tt-counter-exp`
- WSL 路径：`/mnt/c/Users/Lenovo/DoubaoWork/chats/2026-10-13/new-chat/tt-counter-exp`
- 工具脚本：`tools/def_stats.py`、`tools/pya_merge_gds.py`
- 统计 JSON：`logs/stats.json`（DEF）、`logs/gds_stats.json`（单元 GDS 回退版）
- P&R 产物：`logs/orfs/6_final.def`、`6_final.v`、`6_final.spef`、`1_2_yosys_netlist.v`、`route.guide`、`6_merged_cells.gds`（回退，非完整布线 GDS）
- P&R 配置留档：`logs/orfs/pr_config/`（config.mk、constraint.sdc、rtl/）
- 各 stage 日志：`logs/orfs/stage_logs/` 与 `logs/orfs/stage_*.console.log`

## 1. 克隆与一致性核对

- Windows 侧 `git -c core.autocrlf=false clone https://github.com/jiahao-plus/tt-counter`。
- HEAD = `9ecb930a2ae4a8b1f76cc06f3ec4ed475b3a165e`；与只读原目录逐文件 MD5 比对一致（仅本地生成物 results.xml/vcd/sim_build/__pycache__ 差异，已忽略）。

## 2. RTL 回归（cocotb / iverilog 11.0 / cocotb 1.9.1）

| 运行 | 日志 | 结果 |
| --- | --- | --- |
| 基线（原计数器） | `logs/00-baseline-cocotb.log` | **5/5 PASS**（reset/up/down-wrap/en-off-hold/255→0 wrap） |
| 集成版（mode0 原行为 + 两 IP + 模式隔离） | `logs/02-integrated-cocotb.log` | **8/8 PASS**（原 5 项未改 + PWM duty=64 + LFSR 黄金值/输出相位 + mode0 保持 uio 为输入） |

`test/results.xml`（最近一次集成运行）含 8 个 `<testcase>`，无 failure/error 子元素。

## 3. 基线 vs 增强 综合对比（本机 Yosys 0.69 + sky130hd tt_025C_1v80.lib）

方法：`read_verilog → synth -top tt_um_jiahao_plus_counter -flatten → dfflibmap → abc → stat -liberty`。日志：`logs/01-baseline-synth.log`、`logs/03-enhanced-synth.log`。

| 指标 | 基线（mode0 计数器） | 增强版（mode0+PWM+LFSR） |
| --- | --- | --- |
| 已映射标准单元 | 46 | 200 |
| 触发器 FF（已映射） | 8（dfrtp_1） | 35（27 dfrtp_1 + 8 dfxtp_1） |
| Chip area（liberty 求和） | 469.200000 µm² | 1774.201600 µm² |
| 其中时序单元面积 | 200.192（42.67%） | 835.8016（47.11%） |
| 未映射单元 | 无 | 16 个 `$_ALDFFE_PNP_`（原始 LFSR 异步非恒定置位，liberty 无对应单元） |

说明：任务给定旧记录 33 单元 / 8 DFF / 171.4144 µm² 来自官方 OpenLane2 CI 流程，与本机 Yosys+liberty 方法（单元选择、映射脚本不同）不可直接比较；本机实测基线为 46 / 8 / 469.2，已在日志如实记录，未沿用旧值。

## 4. 集成 IP（均 vendor 至 third_party/，保留 LICENSE，MIT）

| IP | repo | commit | 顶层/端口 |
| --- | --- | --- | --- |
| PWM | bhasan60/verilog-pwm-controller | `789f55292b94b392b586752821033ad2b1568759` | `pwm(clk, rst[高有效], duty[7:0], pwm_out)` |
| LFSR | Brafamous/Linear-Feedback-Shift-Register-Design | `fc59536f0017ddba4447f9497b2485072bc6ee99` | `LFSR_Design #(8,8,4)(clk,rst,enable,output_enable,seed_value[7:0],valid,Out,lfsr_out[7:0])` |

集成：顶层名 `tt_um_jiahao_plus_counter` 与全部端口保留；`ui_in[7:2]`=mode。mode0 行为完全不变（en=ui[0], dir=ui[1], rst_n 低有效清零, ena 全局使能）。

## 5. ORFS sky130hd 布局布线（本地 ORFS 流程，非官方 TT CI 产物）

平台自带 lib/lef/gds（`/root/openroad-flow-scripts/flow/platforms/sky130hd`），无需外部 PDK_ROOT。设计目录 `flow/designs/sky130hd/tt_counter/`；约束 100 kHz / 10000 ns，CORE_UTILIZATION=40，PLACE_DENSITY=0.55。

| stage | 结果 | 证据 |
| --- | --- | --- |
| 1_synth / 1_2_yosys | rc=0（P&R 网表采用 LFSR 复位同步适配版，消除 16 个未映射 ALDFFE；pristine 留在 third_party，RTL/cocotb 用 pristine） | `stage_logs/1_2_yosys.log` |
| 2 floorplan | rc=0，Design area 2908 µm² @45% | `stage_logs/2_1_floorplan.log` |
| 3 place | rc=0，3090 µm² @47%，HPWL −9%，0 placement violation | `stage_logs/3_5_place_dp.log` |
| 4 cts | rc=0，3191 µm² @49% | `stage_logs/4_1_cts.log` |
| 5 route/fill | rc=0，2100(报告2093) vias，0 antenna，0 net/pin 违规；633 filler / 77 tap | `stage_logs/5_2_route.log`、`5_3_fillcell.log` |
| 6 finish GDS | **未完成**：do-gds-merged 步骤本机 klayout 0.26.2 Ruby 宏崩溃（环境 API 不匹配）；openroad reduced build 无 write_gds | `stage_finish.console.log`、`6_1_merge.log` |

完成态单元类型报告（`stage_logs/6_report.log`）：sequential 51、multi-input comb 232、timing repair buffer 32、clock buffer 8、inverter 17、fill 633、tap 77；总组件 1050。日志无显式 WNS/TNS（100 kHz 宽松约束，ORFS 未输出时序余量表）。

**GDS 状态**：官方合并 GDS 本地未生成；回退产物 `6_merged_cells.gds` 仅放置标准单元图形（48 类、973 实例），**不含布线线/信号 via**，仅供单元层参考，不可用于 DRC/流片。

## 6. GDS/DEF 统计摘要

DEF（`logs/stats.json`，脚本 `tools/def_stats.py`）：

- COMPONENTS 1050（fill 633 / tap 77 / 逻辑单元 340）；NETS 375（DEF 未单列 VDD/VSS，PDN 走 SPECIALNETS/网格）。
- 布线几何分段（DEF 内合并 PDN+信号）：met1 120、met2 180、met3 180、met4 21、met5 5；非零线宽 min 330 / median 370 / max 1600（nm，DEF 单位 1000/µm）。
- route 日志权威 via 汇总（`5_2_route.log`）：li1 1098、met1 955、met2 34、met3 6，合计 2093 up-vias。
- M1–Via1–M2 跨层候选：DEF 不枚举 via 实例，仅按 via 规则引用计数（via2_3=M1M2_PR）= 91，且绝大多数为 PDN 电源条 strap 列，**非信号 M1-Via1-M2 数量**；信号级 M1-Via1-M2 精确候选数 DEF 无法给出（判据已写入 JSON）。

单元回退 GDS（`logs/gds_stats.json`，`tools/pya_merge_gds.py`）：仅注释/引脚层多边形被统计，器件层未计入，不代表真实布线层覆盖。

## 7. 1×1 Tile 结论

- TT 1×1 tile 约 167×108 µm（≈18036 µm²）。
- 增强版 liberty 单元面积 1774.2 µm²，约为 tile 面积预算的 10%；ORFS 放置 die 约 85µm 见方（DIEAREA 85220/1000 µm），仍在 1×1 内。
- **结论：增强版（200 单元 / 35 FF）可放进 1×1 Tile，面积裕量充足。** 三备选（若未来进一步膨胀）：①精简（砍 LFSR 串行移位寄存器，仅留生成态）；②扩到 1×2/2×2；③把 PWM、LFSR 拆为独立 TinyTapeout 项目。

## 8. 未验证清单

- **门级仿真（GL test）**：未验证。本机缺 `$PDK_ROOT/sky130A/libs.ref/.../primitives.v` 与 `sky130_fd_sc_hd.v` 行为模型，iverilog elaborate 报 Unknown module type（证据 `logs/04-gatelevel-attempt.log`）。
- **官方 precheck（tt-tooling）**：未验证。`pip3 install tt-tooling` 在 PyPI 无该包，`tt_tooling` 不可导入（证据 `logs/precheck_gl.sh` 输出）。
- **官方合并 GDS / DRC / LVS**：未验证（klayout Ruby 宏崩溃，无完整布线 GDS）。
- **显式时序 WNS/TNS**：未输出（100 kHz 约束下 ORFS 未给余量报告）。
- **OpenLane2 官方镜像路线**：未尝试（镜像数 GB，按任务要求作为限时可选项放弃）。

## 9. 与官方 CI 的差异

| 项 | 官方 CI（.github/workflows） | 本机验证 |
| --- | --- | --- |
| RTL 测试 | iverilog+cocotb `make clean; make; ! grep failure results.xml` | 已复现，8/8 PASS |
| 综合 | OpenLane2（tt-gds-action@tt10）出单元/面积 | 本机 Yosys+liberty，方法/数值不同，仅作相对对比 |
| P&R / GDS | OpenLane2 全流程出合并 GDS、precheck、gl_test、viewer | 本机 ORFS sky130hd 跑到 route/fill；GDS 合并失败，GL/precheck 未验证 |
| precheck / gl_test / viewer | CI 内建 | 本机未复现（缺包/缺 PDK 模型） |
| 产物归属 | 官方 TT CI | 本地 ORFS，非官方产物，不可直接提交 |

## 10. 复现入口

```bash
cd test && make SIM=icarus                 # RTL 回归 8/8
python3 tools/def_stats.py logs/orfs/6_final.def logs/orfs/stage_logs/5_2_route.log logs/stats.json
# ORFS: 见 logs/orfs/pr_config/config.mk + constraint.sdc，在 /root/openroad-flow-scripts 下 make 对应 stage
```
