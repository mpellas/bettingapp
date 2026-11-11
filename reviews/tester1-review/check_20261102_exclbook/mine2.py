import json,glob,re,os,pandas as pd
def nm(s):
    s=re.sub(r"[.'’]","",s.lower()); s=re.sub(r"\b(jr|sr|ii|iii|iv)\b","",s); return " ".join(s.split())
# box
stats={}
for f in glob.glob('espn/*.json'):
    d=json.load(open(f))
    for t in d.get('boxscore',{}).get('players',[]):
        for g in t['statistics']:
            cat={'passing':'pass_yds','rushing':'rush_yds','receiving':'reception_yds'}.get(g['name'])
            if not cat: continue
            i=g['labels'].index('YDS')
            for a in g['athletes']:
                n=nm(a['athlete']['displayName']); v=float(a['stats'][i]); stats[(n,cat)]=v
                ln=n.split()[-1]; stats.setdefault(('~'+n[0]+'|'+ln,cat),[]).append(v)
def look(p,mk):
    if (p,mk) in stats: return stats[(p,mk)]
    p=p.replace(' ',' ').split(); k=('~'+p[0][0]+'|'+p[-1],mk); v=stats.get(k)
    return v[0] if v and len(v)==1 else None
def dec(a): return 1+a/100 if a>0 else 1+100/-a
rows=[]
for pull in sorted(os.listdir('raw')):
    for f in glob.glob(f'raw/{pull}/*.json'):
        d=json.load(open(f)); game=f"{d['away_team']} @ {d['home_team']}"
        q={}
        for b in d['bookmakers']:
            for m in b['markets']:
                mk=m['key'].replace('player_','')
                for o in m['outcomes']:
                    q.setdefault((nm(o['description']),mk,o.get('point')),{}).setdefault(b['key'],{})[o['name']]=o['price']
        for (p,mk,ln),bk in q.items():
            nv={k:(1/dec(v['Over']))/(1/dec(v['Over'])+1/dec(v['Under'])) for k,v in bk.items() if 'Over' in v and 'Under' in v}
            for book in ('draftkings','fliff'):
                if book not in nv: continue
                oth=[v for k,v in nv.items() if k!=book]
                if not oth: continue
                import statistics; po=statistics.median(oth)
                for side,pf in (('Over',po),('Under',1-po)):
                    pr=bk[book][side]; rows.append(dict(pull=pull,kick=d['commence_time'],game=game,player=p,market=mk,line=ln,side=side,book=book,price=pr,n_oth=len(oth),
                        nsharp=sum(k in('pinnacle','fanduel','circasports','betonlineag') for k in nv if k!=book),fair=pf,ev=100*(pf*dec(pr)-1)))
df=pd.DataFrame(rows)
# keep latest pull before kickoff per side
df['pt']=pd.to_datetime(df.pull,format='%Y%m%dT%H%M',utc=True); df['kt']=pd.to_datetime(df.kick)
df=df[df.pt<df.kt].sort_values('pt').drop_duplicates(['game','player','market','line','side','book'],keep='last')
def grade(r):
    a=look(r.player,r.market)
    if a is None: return pd.Series([None,'void',0.0])
    w=(a>r.line) if r.side=='Over' else (a<r.line)
    return pd.Series([a,'win' if w else 'loss',dec(r.price)-1 if w else -1.0])
df[['actual','res','u']]=df.apply(grade,axis=1)
print('sides',len(df)); print(df.ev.describe())
print(df.sort_values('ev',ascending=False).head(5)[['pull','game','player','market','line','side','book','price','n_oth','nsharp','ev','actual','res']].to_string())
print('ev>=2',(df.ev>=2).sum(),'ev>=2 & 2sharp',((df.ev>=2)&(df.nsharp>=2)).sum(),'ev>=0',(df.ev>=0).sum())
df.to_csv('mine_sides.csv',index=False)
# ledger
L=pd.read_csv('an_ledger.csv'); L=L[L.slate_date=='2026-11-01']
print('ledger',len(L),L.result.value_counts().to_dict(),round(L.units.sum(),2))
def g2(r):
    a=look(nm(r.player),r.market)
    if a is None: return pd.Series([None,'void',0.0])
    w=(a>r.line) if r.side=='Over' else (a<r.line)
    return pd.Series([a,'win' if w else 'loss',dec(r.price)-1 if w else -1.0])
L[['a2','r2','u2']]=L.apply(g2,axis=1)
print('my grade of ledger rows',L.r2.value_counts().to_dict(),round(L.u2.sum(),2),'result mismatches',(L.result!=L.r2).sum(), 'actual mism',((L.actual-L.a2).abs()>0).sum())
print(L[L.result!=L.r2][['player','market','line','side','actual','a2','result','r2']])
# best of DK/Fliff for ledger sides
best=[]
for _,r in L.iterrows():
    c=df[(df.player==nm(r.player))&(df.market==r.market)&(df.line==r.line)&(df.side==r.side)&(df.game==r.game)]
    pr=max(c.price,key=dec) if len(c) else r.price
    if r.r2=='void': continue
    best.append((r.game,r.r2,dec(pr)-1 if r.r2=='win' else -1, len(c)))
B=pd.DataFrame(best,columns=['game','res','u','n']); print('best',len(B),B.res.value_counts().to_dict(),round(B.u.sum(),2),'nomatch',(B.n==0).sum())
gg=B.groupby('game').u.sum(); print(gg.round(2)); print('profitable games',(gg>0).sum(),'of',len(gg))
