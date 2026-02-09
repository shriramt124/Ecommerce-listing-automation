import numpy as np

data = np.load('st_keywords_index/keywords_index.npz', allow_pickle=True)
keywords = data['keywords']
scores = data['scores']

# Deduplicate
seen = {}
for k, s in zip(keywords, scores):
    k_lower = str(k).lower().strip()
    if k_lower not in seen or float(s) > seen[k_lower][1]:
        seen[k_lower] = (str(k), float(s))

top_vol = sorted(seen.values(), key=lambda x: x[1], reverse=True)

print(f"Total entries: {len(keywords)}")
print(f"Unique keywords: {len(seen)}")
print(f"\nTOP 30 by volume:")
for i, (kw, vol) in enumerate(top_vol[:30], 1):
    print(f"  {i:2d}. vol={vol:>8.0f}  '{kw}'")

# Check what keywords contain "dumbbell" or "weight"
print(f"\n--- Keywords containing 'dumbbell' ---")
dumbbell_kws = [(k, v) for k, (_, v) in seen.items() if 'dumbbell' in k]
dumbbell_kws.sort(key=lambda x: x[1], reverse=True)
for kw, vol in dumbbell_kws[:20]:
    print(f"  vol={vol:>6.0f}  '{kw}'")

print(f"\n--- Keywords containing 'weight' ---")
weight_kws = [(k, v) for k, (_, v) in seen.items() if 'weight' in k]
weight_kws.sort(key=lambda x: x[1], reverse=True)
for kw, vol in weight_kws[:15]:
    print(f"  vol={vol:>6.0f}  '{kw}'")

print(f"\n--- Keywords containing 'gym' or 'fitness' ---")
gym_kws = [(k, v) for k, (_, v) in seen.items() if 'gym' in k or 'fitness' in k]
gym_kws.sort(key=lambda x: x[1], reverse=True)
for kw, vol in gym_kws[:15]:
    print(f"  vol={vol:>6.0f}  '{kw}'")

print(f"\n--- Keywords containing 'kettlebell' ---")
kb_kws = [(k, v) for k, (_, v) in seen.items() if 'kettlebell' in k or 'kettle' in k]
kb_kws.sort(key=lambda x: x[1], reverse=True)
for kw, vol in kb_kws[:10]:
    print(f"  vol={vol:>6.0f}  '{kw}'")
