import pandas as pd, numpy as np, glob, json, re, urllib.request, os
N='nhl-sog_copy'
d=pd.read_csv('dated_rules/raw_pass_rows_dated.csv')
print('pass-rows',len(d),'unique player-game',d.groupby(['gameId','player']).ngroups)
d=d.sort_values('captured_utc').groupby(['gameId','nhl_id'],as_index=False).last()
act={};clo={}
for f in glob.glob(N+'/graded/2026*.csv'):
    if not re.search(r'/\d{8}\.csv$',f): continue
    g=pd.read_csv(f)
    for r in g.itertuples():
        if pd.notna(r.actual): act[(r.gameId,r.nhl_id)]=float(r.actual)
        if 'nv_over_C' in g and pd.notna(r.nv_over_C) and r.line_C==r.line: clo[(r.gameId,r.nhl_id,r.line)]=float(r.nv_over_C)
for f in glob.glob(N+'/captures/2026*/*_CLOSE.json'):
    try:
        for c in json.load(open(f)).get('closed',[]): clo.setdefault((None,int(c['nhl_id']),float(c['line'])),c['nv_over'])
    except Exception: pass
box={}
def sog(g,p):
    if (g,p) in act: return act[(g,p)],'graded'
    if g not in box:
        m={}
        try:
            j=json.load(urllib.request.urlopen(urllib.request.Request(f'https://api-web.nhle.com/v1/gamecenter/{g}/boxscore',headers={'User-Agent':'x'}),timeout=20))
            for t in('awayTeam','homeTeam'):
                for grp in j['playerByGameStats'][t].values():
                    for q in grp:
                        if 'sog' in q: m[int(q['playerId'])]=q['sog']
        except Exception as e: print('box fail',g,e)
        box[g]=m
    v=box[g].get(p); return (v,'nhl.com') if v is not None else (None,'missing')
dec=lambda a:(a/100 if a>0 else 100/-a)
R=[]
for r in d.itertuples():
    a,src=sog(r.gameId,r.nhl_id); c=clo.get((r.gameId,r.nhl_id,r.line), clo.get((None,r.nhl_id,r.line)))
    win=None if a is None else a<r.line
    R.append(dict(actual=a,actual_src=src,result='' if a is None else ('W' if win else 'L'),
      u_dk=np.nan if a is None else (dec(r.dk_price) if win else -1.0),
      u_shop=np.nan if a is None else (dec(r.shop_at) if win else -1.0),
      nv_close_under=np.nan if c is None else round(1-c,4), clv_pts=np.nan if c is None else round(((1-c)-r.nv_under)*100,1)))
d=pd.concat([d.reset_index(drop=True),pd.DataFrame(R)],axis=1)
d.to_csv('dated_rules/promo_under_sides_dated.csv',index=False)
def summ(x,lab):
    g=x[x.result!='']; n=len(g)
    if n==0: return f'{lab}: n=0'
    w=(g.result=='W').sum()
    return (f"{lab}: n={len(x)} graded={n} {w}-{n-w} DK {g.u_dk.sum():+.2f}u (ROI {g.u_dk.mean()*100:+.1f}%) "
            f"shop {g.u_shop.sum():+.2f}u | CLV avg {x.clv_pts.mean():+.2f} pts, no close {x.clv_pts.isna().sum()}")
def boot(x,col='u_dk',B=20000):
    v=x[x.result!=''][col].values
    if len(v)<2: return 'n/a'
    rng=np.random.default_rng(7); m=rng.choice(v,(B,len(v))).mean(1)
    return f'{col} ROI {v.mean()*100:+.1f}% 95% CI [{np.percentile(m,2.5)*100:+.1f}%, {np.percentile(m,97.5)*100:+.1f}%]'
L=d[d.makes_list]; out=[]
P=out.append
P(summ(d,'ALL promo-vetoed unders (latest pass)')); P(boot(d)); P(boot(d,'u_shop'))
P(summ(L,'Would make a list (veto removed)')); P(boot(L)); P(boot(L,'u_shop'))
P(summ(d[~d.makes_list],'Blocked by another gate'))
P('\nFirst blocker counts:'); P(d[~d.makes_list].blockers.str.split(' \\| ').str[0].str.replace(r'\(.*','',regex=True).str[:45].value_counts().to_string())
P('\nList status: '+L.new_status.value_counts().to_string().replace('\n','; '))
for lab,x in (('ALL',d),('LIST',L)):
    x=x.copy()
    x['edge_b']=pd.cut(x.edge_model_pts,[-99,0,5,10,99],labels=['<=0','0-5','5-10','10+'])
    x['toi_b']=pd.cut(x.toi_rise,[-99,0,1,2,99],labels=['<=0','0-1','1-2','2+'])
    x['period']=np.where(x.date<=20261025,'Oct15-25','Oct26-29')
    for col in ('edge_b','toi_b','period','date'):
        P(f'\n[{lab}] by {col}')
        for k,g in x.groupby(col,observed=True): P('  '+summ(g,str(k)))
open('dated_rules/summary_dated.txt','w').write('\n'.join(out)); print('\n'.join(out))
