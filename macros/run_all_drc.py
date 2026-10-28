"""Run the geometric DRC on every generated structure and summarise."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom_drc

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'out')
TAGS = ['A', 'B', 'C1', 'C3', 'C4', 'D', 'E']
results = {}
for tag in TAGS:
    p = os.path.join(OUT, 'struct_%s.gds' % tag)
    if not os.path.exists(p):
        results[tag] = {'error': 'missing', 'pass': False}
        continue
    r = geom_drc.run(p, verbose=False)
    results[tag] = {
        'pass': r['pass'],
        'n_violations': r['n_violations'],
        'layers': r['layer_counts'],
        'violations': r['violations'][:20],
    }

print('%-4s %-8s %-6s %s' % ('tag', 'DRC', 'viol', 'layers'))
for tag in TAGS:
    r = results[tag]
    if 'error' in r:
        print('%-4s %-8s %s' % (tag, 'MISSING', r['error'])); continue
    print('%-4s %-8s %-6d %s' % (tag, 'PASS' if r['pass'] else 'FAIL',
                                 r['n_violations'], r['layers']))
    if not r['pass']:
        for v in r['violations'][:5]:
            print('       ', v)

allok = all(results[t].get('pass') for t in TAGS)
json.dump({'results': results, 'all_pass': allok},
          open(os.path.join(OUT, 'drc_all.json'), 'w', encoding='utf-8'),
          indent=1, ensure_ascii=False)
print()
print('ALL STRUCTURES DRC:', 'PASS' if allok else 'FAIL')
sys.exit(0 if allok else 1)
