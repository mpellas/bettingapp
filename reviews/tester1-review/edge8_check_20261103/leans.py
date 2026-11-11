import csv,glob,json,collections,math
def shots_by_id(date):
    m={}
    for f in glob.glob('box/*.json'):
        d=json.load(open(f))
        if d['gameDate'].replace('-','')!=date or d['gameState'] not in ('OFF','FINAL'): continue
        for t in ('awayTeam','homeTeam'):
            for g in ('forwards','defense'):
                for p in d['playerByGameStats'][t][g]: m[p['playerId']]=p.get('sog',0)
    return m
def pay(a): a=int(a); return a/100 if a>0 else 100/-a
R=[]
for f in sorted(glob.glob('in/picks/2026*_D.csv')):
    dte=f.split('/')[-1][:8]
    if not '20261011'<=dte<='20261102': continue
    sh=shots_by_id(dte)
    for r in csv.DictReader(open(f)):
        try: pm=float(r['p_model_over']); nv=float(r['nv_over']); nid=int(float(r['nhl_id']))
        except: continue
        eo=(pm-nv)*100; s='OVER' if eo>0 else 'UNDER'; e=abs(eo); p=pm if s=='OVER' else 1-pm
        if nid not in sh: R.append(dict(d=dte,res=None)); continue
        L=float(r['line']); win=(sh[nid]>L)==(s=='OVER')
        R.append(dict(d=dte,e=e,p=p,win=win,u=(pay(r['over' if s=='OVER' else 'under']) if win else -1),conf=r['side_method']=='milestone',res=1))

G=[r for r in R if r['res']]
print('rows',len(R),'graded',len(G))
def rep(lab,xs):
    if not xs: return
    w=sum(x['win'] for x in xs); print(f"{lab}: n={len(xs)} {w}-{len(xs)-w} {sum(x['u'] for x in xs):+.1f}u hit {w/len(xs):.1%} claimed {sum(x['p'] for x in xs)/len(xs):.1%}")
for nm,f in [('all',lambda r:True),('conf',lambda r:r['conf']),('unconf',lambda r:not r['conf'])]:
    xs=[r for r in G if f(r)]
    rep(nm+' 8+',[r for r in xs if r['e']>=8]); rep(nm+' 8-12',[r for r in xs if 8<=r['e']<12]); rep(nm+' 12+',[r for r in xs if r['e']>=12]); rep(nm+' <8',[r for r in xs if r['e']<8])
# binomial test unconf 8+ vs claimed p
u=[r for r in G if not r['conf'] and r['e']>=8]
w=sum(r['win'] for r in u); mu=sum(r['p'] for r in u); var=sum(r['p']*(1-r['p']) for r in u)
z=(w-mu)/math.sqrt(var); print('unconf8 z',round(z,2),'p1side',0.5*math.erfc(-z/math.sqrt(2)))
