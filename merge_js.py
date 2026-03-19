import os

with open('/Users/fidelnamisi/Indaba/lw_js_part1.js', 'r') as f1:
    p1 = f1.read()
with open('/Users/fidelnamisi/Indaba/lw_js_part2.js', 'r') as f2:
    p2 = f2.read()
with open('/Users/fidelnamisi/Indaba/lw_js_part3.js', 'r') as f3:
    p3 = f3.read()

with open('/Users/fidelnamisi/Indaba/static/app.js', 'a') as f:
    f.write('\\n' + p1 + '\\n' + p2 + '\\n' + p3 + '\\n')
    
print("Appended successfully")
