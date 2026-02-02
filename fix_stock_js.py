import os

path = 'frontend/js/stock.js'
if not os.path.exists(path):
    print(f"File not found: {path}")
    exit(1)

with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Verify the cut points
print(f"Line 2561 content: {lines[2560]}")
print(f"Line 3775 content: {lines[3774]}")

if "startDataUpdate" not in lines[3774]:
    print("WARNING: Line 3775 is not startDataUpdate. Searching...")
    target_idx = -1
    for i, line in enumerate(lines):
        if "startDataUpdate() {" in line:
            target_idx = i
            break
    if target_idx != -1:
        print(f"Found startDataUpdate at {target_idx + 1}")
        cut_end = target_idx
    else:
        print("ERROR: startDataUpdate not found!")
        exit(1)
else:
    cut_end = 3774

new_lines = lines[:2560] + lines[cut_end:]

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"Fixed {path}. New length: {len(new_lines)}")
