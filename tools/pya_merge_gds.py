#!/usr/bin/env python3
"""
Build a cell-only merged GDS from the ORFS 6_final.def against the sky130hd
platform cell GDS, and count polygons per (layer, datatype).

NOTE / limitation:
  - This places standard-cell masters (all 49 used types matched) but does NOT
    redraw routed met1/met2 wires or signal vias (DEF does not carry full
    geometry for those; ORFS official merge crashed on the klayout Ruby macro).
  - Orientation is applied as identity (N); mirror/FS rows are not remapped.
  - Used as a local fallback because openroad reduced build lacks write_gds.

Usage:
  python3 pya_merge_gds.py <6_final.def> <platform.gds> <out.gds> <out_gds_stats.json>
"""
import sys, re, json
import klayout.db as pya

def_path, plat_gds, out_gds, out_json = sys.argv[1:5]
DBU = 1000.0  # DEF UNITS DISTANCE MICRONS 1000 -> 1 unit = 0.001 um

COMP = re.compile(r'^\s*-\s+(\S+)\s+(\S+)\b.*?PLACED\s*\(\s*(\d+)\s+(\d+)\s*\)\s+(\w+)\s*;')

ly = pya.Layout()
ly.read(plat_gds)
top = ly.create_cell("tt_um_jiahao_plus_counter")

inst_count = {}
with open(def_path, errors='replace') as f:
    for line in f:
        m = COMP.match(line)
        if not m:
            continue
        _inst, cellname, x, y, orient = m.groups()
        master = ly.cell(cellname)
        if master is None:
            print("WARN missing master", cellname)
            continue
        tx = pya.Trans(int(x) / DBU, int(y) / DBU)  # identity orientation fallback
        top.insert(pya.CellInstArray(master.cell_index(), tx))
        inst_count[cellname] = inst_count.get(cellname, 0) + 1

ly.write(out_gds)

# Count polygons per (layer,datatype), weighted by instance occurrences.
poly_per_layer = {}
for cell in ly.each_cell():
    n = inst_count.get(cell.name, 0)
    if n == 0 and cell.name != "tt_um_jiahao_plus_counter":
        continue
    for li in ly.layer_indexes():
        info = ly.get_info(li)
        shp = cell.shapes(li)
        cnt = 0
        for s in shp.each():
            if s.is_polygon():
                cnt += 1
        if cnt:
            key = f"layer{info.layer}/datatype{info.datatype}"
            poly_per_layer[key] = poly_per_layer.get(key, 0) + cnt * max(n, 1)

result = {
    "note": "cell-only merged GDS; no routed wires; identity orientation; polygon count = sum over instances of master polygons.",
    "placed_instances": sum(inst_count.values()),
    "distinct_cell_types": len(inst_count),
    "polygons_per_layer_datatype": dict(sorted(poly_per_layer.items(), key=lambda kv: -kv[1])),
}
with open(out_json, 'w') as f:
    json.dump(result, f, indent=2, ensure_ascii=False)
print(json.dumps(result, indent=2, ensure_ascii=False))
