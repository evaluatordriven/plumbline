import json, os
p=json.load(open('packet.json'))
fr=p['artifact'].get('frozen',[]); ed=p['artifact'].get('editable',[])
print("--- FROZEN ---")
print('\n'.join(sorted(fr)))
print("--- EDITABLE ---")
print('\n'.join(sorted(ed)))
for m in ('kit/custody_history.py',):
    print(f"{'FROZEN' if m in fr else ('EDITABLE' if m in ed else '???')} {m}")
os.system('git status --porcelain kit/custody_history.py')
