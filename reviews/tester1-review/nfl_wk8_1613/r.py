import json,glob,csv,statistics as st,math
def imp(a):return 100/(a+100) if a>0 else -a/(-a+100)
L={}
for f in glob.glob('20261102T0013/*.json'):
 d=json.load(open(f))
 for b in d['bookmakers']:
  for m in b['markets']:
   for o in m['outcomes']:
    L.setdefault((o['description'].lower(),m['key'].replace('player_',''),o.get('point')),{}).setdefault(b['key'],{})[o['name']]=o['price']
sides=[];both=0;priced=0
for k,bk in L.items():
 two={b:v for b,v in bk.items() if 'Over' in v and 'Under' in v}
 if not two: continue
 priced+=1; both+= 'fanduel' in two and 'pinnacle' in two
 for s in ('Over','Under'):
  fp=st.median(imp(v[s])/(imp(v['Over'])+imp(v['Under'])) for v in two.values())
  for b in ('draftkings','fliff'):
   if b in bk and s in bk[b]:
    p=bk[b][s];dec=1+(p/100 if p>0 else 100/-p)
    sides.append((round((fp*dec-1)*100,2),k,s,b,p,len(two)))
sides.sort(reverse=True)
print(len(sides),'sides; priced',priced,'both FD+PIN',both)
for x in sides[:4]:print(x)
names={k[0] for k in L}
for pre in ['175833Z','210053Z']:
 M={}
 for r in csv.DictReader(open(f'/workspace/nfl-props/data/predictions/2026_wk08/pregame_20261101T{pre}.csv')):
  if r['in_model_universe']=='True':M[(r['player_display_name'].lower(),r['market'])]=r
 print(pre,'dyami in model:',any(n=='dyami brown' for n,_ in M))
 for r in csv.DictReader(open('shadow_modelled_20261101_1614.csv')):
  m=M.get((r['player'],r['market']))
  if m: print(' ',r['player'],r['market'],r['model_p'], round(0.5*(1+math.erf((float(r['line'])-float(m['mu']))/float(m['s'])/2**.5)),4))
