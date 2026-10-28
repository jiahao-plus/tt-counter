# 综合后网表的七宏实例检查

自动生成：`macros/p3_synth_netlist_check.py`  
流程：`synth` → `flatten` → `opt` → `write_verilog`（贴近官方，
而不是只跑 `proc; opt`）

| 实例 | 宏 | 存在 | cell 正确 | 端口正确 | 端口连接 |
|---|---|---|---|---|---|
| `u_rs_via1` | `research_via1` | ✓ | ✓ | ✓ | net=pwm_out |
| `u_rs_via2` | `research_via2` | ✓ | ✓ | ✓ | net=pwm_out |
| `u_rs_branch` | `research_branch` | ✓ | ✓ | ✓ | net=pwm_out |
| `u_rs_near` | `research_near` | ✓ | ✓ | ✓ | — |
| `u_rs_cross` | `research_cross` | ✓ | ✓ | ✓ | — |
| `u_rs_dense` | `research_dense` | ✓ | ✓ | ✓ | — |
| `u_rs_fiducial` | `research_fiducial` | ✓ | ✓ | ✓ | — |

## 结论

**PASS** — 七个实例在 synth + flatten + opt 之后全部存在，
cell 类型与端口连接均正确。

> `(* keep *)` 只保住了实例、名字和端口连接。它**不**证明
> 物理宏接线正确——那是 LVS 的问题，仍未验证。
