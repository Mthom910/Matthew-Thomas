import json

with open('initiative_data.json') as f:
    d = json.load(f)

k = d['kpis']
print(f"jobs26 = {k['jobs26']}  (prev: 601)")
print(f"rev26  = {k['rev26']:,.0f}")
print()
print("Price segments:")
for seg in d['price_segs']:
    print(f"  {seg['label']:12s}: {seg['count26']:4d} orders")
