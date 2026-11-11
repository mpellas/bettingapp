import json,glob,datetime as dt
def c(p): return abs(p)-100 if p<0 else 100-p
rows=[]
for f in glob.glob('raw/*.json'):
    e=json.load(open(f))
    if not isinstance(e,dict) or 'bookmakers' not in e: continue
    ko=dt.datetime.fromisoformat(e['commence_time'].replace('Z','+00:00'))-dt.timedelta(hours=7)
    g=f"{e['away_team']} @ {e['home_team']}"
    for b in e['bookmakers']:
        for m in b['markets']:
            d={}
            for o in m['outcomes']: d.setdefault((o.get('description'),o.get('point')),{})[o['name']]=o['price']
            for (pl,pt),s in d.items():
                if 'Over' in s and 'Under' in s:
                    ov,un=int(s['Over']),int(s['Under']); gap=c(ov)+c(un)
                    inr=any(-150<=x<=100 or x==100 for x in (ov,un))
                    rows.append((gap,inr,ko.strftime('%-I:%M %p'),g,pl,m['key'].replace('player_',''),pt,ov,un,b['title']))
print('total',len(rows))
from collections import Counter;print(Counter(r[0] for r in rows).most_common(12))
q=[r for r in rows if r[1] and 22<=r[0]<=28]
print('22-28 in range',len(q))
for r in sorted(q,key=lambda r:(abs(r[0]-25),r[3])): print(r)
