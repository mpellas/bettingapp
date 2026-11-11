import json,glob,csv
from datetime import datetime,timedelta
def gap(a,b):
    f=lambda p:p if p>0 else p  # cents gap on 100-centered scale
    t=lambda p:p-100 if p>=100 else p+100
    return abs(t(a)-t(b))
rows=[]
for fn in glob.glob('raw/*.json'):
    d=json.load(open(fn)); ko=(datetime.fromisoformat(d['commence_time'].replace('Z','+00:00'))-timedelta(hours=7)).strftime('%a %-I:%M %p PT')
    for b in d['bookmakers']:
        for m in b['markets']:
            g={}
            for o in m['outcomes']: g.setdefault((o.get('description'),o.get('point')),{})[o['name']]=o['price']
            for (pl,pt),s in g.items():
                if 'Over' in s and 'Under' in s:
                    o,u=s['Over'],s['Under']
                    inr=lambda p:(100<=p) and False or (-150<=p<=-100) or p==100 or (100<=p<=100)
                    ok=any(-150<=p<=-100 or p==100 for p in (o,u)) or any(p==100 for p in (o,u))
                    gp=gap(o,u)
                    if ok and 18<=gp<=32: rows.append([d['commence_time'],ko,f"{d['away_team']} @ {d['home_team']}",pl,m['key'],pt,o,u,b['title'],gp])
rows.sort(key=lambda r:(r[0],-abs(25-r[9])*-1))
w=csv.writer(open('out/cfb_props_2026-10-10.csv','w'));w.writerow(['commence_utc','kickoff_pt','game','player','market','line','over','under','book','gap_cents']);w.writerows(rows)
print(len(rows))
for r in rows:print(r[1:])
