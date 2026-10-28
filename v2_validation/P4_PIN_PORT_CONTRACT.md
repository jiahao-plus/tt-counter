# 五视图链断言（α′ 接口）

自动生成：`macros/p3_assert_pin_port_contract.py`  
接口：**一个 PIN、一个 PORT、PORT 内含多个跨层几何**（强连接）

| ID | 宏 | LEF PIN | Verilog 端口 | GDS 分量 | 无 PIN 分量 |
|---|---|---|---|---|---|
| A | `research_via1` | 1 | 1 | 2 | 1 |
| B | `research_via2` | 1 | 1 | 1 | 0 |
| C1 | `research_branch` | 1 | 1 | 1 | 0 |
| C3 | `research_near` | 0 | 0 | 8 | 8 |
| C4 | `research_cross` | 0 | 0 | 2 | 2 |
| D | `research_dense` | 0 | 0 | 13 | 13 |
| E | `research_fiducial` | 0 | 0 | 4 | 4 |

## 检查项

- C1 LEF PIN name == Verilog port name (character-exact)
- C2 LEF PIN count == Verilog port count
- C3 exactly one PORT per PIN (strong connectivity)
- C4 all PORT geometries of a PIN in one GDS component
- C5 that component contains at least one via cut
- C6 LEF DIRECTION matches Verilog direction
- C7 geometry-only macros declare zero PINs
- C8 un-pinned component count matches physics; none holds a via
- C9 synthesized instance port names == LEF PIN names
- C10 every port connects to exactly one non-constant net
- C11 A/B/C1 land on the same net

## 综合网表视图

| 实例 | 宏 | 端口连接 |
|---|---|---|
| `u_rs_via1` | `research_via1` | net=pwm_out |
| `u_rs_via2` | `research_via2` | net=pwm_out |
| `u_rs_branch` | `research_branch` | net=pwm_out |
| `u_rs_near` | `research_near` | — |
| `u_rs_cross` | `research_cross` | — |
| `u_rs_dense` | `research_dense` | — |
| `u_rs_fiducial` | `research_fiducial` | — |

## 结论

**PASS** — 五视图链的前四视图逐宏一致。

> 第五视图（最终 GDS）需要官方 CI，本地未验证。
> 本断言**不**证明 pin access、布线或 LVS 通过。
