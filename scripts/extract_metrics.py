import json

nb = json.load(open('src/analyze/churn_prediction.ipynb', encoding='utf-8'))
cells = nb['cells']

# Show cell 16 full source
print("=== Hucre 16 (build_churn_snapshot full) ===")
print(''.join(cells[16]['source']))

print("\n=== Hucre 14-15 (constants/observation months) ===")
for i in range(14, 18):
    src = ''.join(cells[i]['source'])
    if src.strip():
        print(f"--- Cell {i} ---")
        print(src)
