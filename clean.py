with open('/Users/fidelnamisi/Indaba/app.py', 'r') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if line.strip() == "# ── LIVING WRITER ──" and i < 2700:
        skip = True
    if skip and line.strip() == "# ── Earnings ──────────────────────────────────────────────────────────────────":
        skip = False
    
    if not skip:
        new_lines.append(line)

with open('/Users/fidelnamisi/Indaba/app.py', 'w') as f:
    f.writelines(new_lines)
print("Cleaned!")
