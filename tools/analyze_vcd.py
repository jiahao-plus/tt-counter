# analyze_vcd.py — dump LFSR async/sync comparison timeline from VCD
# Usage: python3 analyze_vcd.py <vcd_path>
import re, sys

vcd = open(sys.argv[1]).read()

# --- parse $var idents ---
ids = {}
for m in re.finditer(r'\$var (wire|reg) \d+ (\S+) (\S+)', vcd):
    ids[m.group(3)] = m.group(2)

print("idents:", ids)

def val_of(id, ts):
    """Scan back from timestamp ts to find last value of id."""
    best = None
    for m in re.finditer(r'#(\d+)\n' + re.escape(id) + r' ?([xXzZ01]*)', vcd):
        t = int(m.group(1))
        if t <= ts:
            best = m.group(2)
        else:
            break
    return best

# collect all timestamps where clk has a rising edge (b0 1 after 0)
clk_id = ids.get("clk") or ids.get("u_sync.clk") or ids.get("u_async.clk")
# iverilog names: lfsr_async_vs_sync_tb.clk, .enable, .rst
def get_id(name):
    return ids.get(name) or ids.get("lfsr_async_vs_sync_tb." + name)

clk = get_id("clk")
a_out = get_id("a_out"); b_out = get_id("b_out")
a_val = get_id("a_valid"); b_val = get_id("b_valid")
a_Out = get_id("a_Out"); b_Out = get_id("b_Out")
rst = get_id("rst"); en = get_id("enable")

# times of clk edges
times = sorted({int(m.group(1)) for m in re.finditer(r'#(\d+)\n' + re.escape(clk) + r' ?1', vcd)})

def edge_values(t, id):
    # value active at time t (last assignment with time <= t)
    best = None
    for m in re.finditer(r'#(\d+)\n' + re.escape(id) + r' ?([xXzZ01]*)', vcd):
        tt = int(m.group(1))
        if tt <= t:
            best = m.group(2)
        else:
            break
    return best

print("\n#clk  rst en  a_out  b_out  a_valid b_valid a_Out b_Out")
for i, t in enumerate(times[:24]):
    print(f"{i:3d} {t:6d}  {edge_values(t,rst) or '?':>2} {edge_values(t,en) or '?':>2} "
          f"{edge_values(t,a_out) or '?':>4} {edge_values(t,b_out) or '?':>4} "
          f"{edge_values(t,a_val) or '?':>3} {edge_values(t,b_val) or '?':>3} "
          f"{edge_values(t,a_Out) or '?':>3} {edge_values(t,b_Out) or '?':>3}")
