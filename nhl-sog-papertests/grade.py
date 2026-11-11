"""Grade paper logs from NHL.com box scores (final games only). Usage: python3 grade.py
Writes graded_challenger.csv, graded_lineup_changed.csv, grade_summary.md; prints totals (graded side counts for 100 gate).
Stake 1u per side at logged DK price. Hit rate vs break-even = mean implied prob of logged prices. Pushes impossible (x.5 lines); DNP -> VOID."""
import os,glob,json,requests,pandas as pd,numpy as np
H='/workspace/nhl-sog-papertests'; LIVE='/workspace/nhl-sog'; BOX={}
def box(gid):
    if gid not in BOX:
        b=requests.get(f'https://api-web.nhle.com/v1/gamecenter/{gid}/boxscore',timeout=30).json()
        s={}
        if b.get('gameState') in ('OFF','FINAL'):
            for side in ('awayTeam','homeTeam'):
                for grp in ('forwards','defense'):
                    for p in b.get('playerByGameStats',{}).get(side,{}).get(grp,[]): s[int(p['playerId'])]=p.get('sog')
        BOX[gid]=(b.get('gameState'),s)
    return BOX[gid]
imp=lambda a:np.where(a<0,-a/(-a+100),100/(a+100)); pay=lambda a:np.where(a<0,100/-a,a/100)
def grade(df,side_col,price_col):
    out=[]
    for _,r in df.iterrows():
        st,s=box(int(r.gameId))
        if st not in ('OFF','FINAL'): out.append(dict(r,result='PENDING')); continue
        sog=s.get(int(r.nhl_id))
        if sog is None: out.append(dict(r,result='VOID_dnp')); continue
        win=(sog>r.line) if r[side_col]=='OVER' else (sog<r.line)
        out.append(dict(r,sog=sog,result='W' if win else 'L'))
    g=pd.DataFrame(out)
    if len(g) and 'sog' in g:
        m=g.result.isin(['W','L']); p=g.loc[m,price_col].astype(float)
        g.loc[m,'units']=np.where(g.loc[m,'result']=='W',pay(p),-1.0); g.loc[m,'implied']=imp(p)
    return g
def summ(g,name):
    if not len(g) or 'units' not in g: return f'- {name}: 0 graded'
    m=g.result.isin(['W','L']); w=(g.result=='W').sum(); l=(g.result=='L').sum(); n=w+l
    if n==0: return f'- {name}: 0 graded'
    return f"- {name}: {w}-{l} ({n} graded), hit {w/n:.1%} vs break-even {g.loc[m,'implied'].mean():.1%}, {g.loc[m,'units'].sum():+.2f}u at logged prices"
lines=['# Paper tests grade summary','']
f=f'{H}/challenger_picks.csv'
if os.path.exists(f):
    C=pd.read_csv(f).drop_duplicates(['gameId','nhl_id','line','side'],keep='first')   # first log before puck drop counts
    gC=grade(C,'side','dk_price'); gC.to_csv(f'{H}/graded_challenger.csv',index=False)
    lines.append(summ(gC,'Challenger A (all edge>=5 in band)'))
    if len(gC) and 'edge_pts' in gC:
        lines.append(summ(gC[gC.edge_pts>=8],'Challenger A edge>=8')); lines.append(summ(gC[gC.side==gC.frozen_side],'Challenger A agrees with frozen side'))
        lines.append(summ(gC[gC.side!=gC.frozen_side],'Challenger A disagrees with frozen side'))
f=f'{H}/lineup_changed_sides.csv'
if os.path.exists(f):
    L=pd.read_csv(f).drop_duplicates(['gameId','nhl_id','line'],keep='first'); L=L[L.in_band==True]
    gL=grade(L,'frozen_side','frozen_price'); gL.to_csv(f'{H}/graded_lineup_changed.csv',index=False)
    lines.append(summ(gL,'Lineup-changed frozen sides (in band)'))
# live list sides for comparison
live=[]
for gf in sorted(glob.glob(f'{LIVE}/picks/2026110[2-9]_D_*_GATE.csv')+glob.glob(f'{LIVE}/picks/202611[1-3]?_D_*_GATE.csv')):
    G=pd.read_csv(gf,dtype={'over':str,'under':str})
    for _,r in G.iterrows():
        for sd,col,pc in (('OVER','dk_listable_over','over'),('UNDER','dk_listable_under','under')):
            if r.get(col)==True: live.append(dict(gameId=r.gameId,nhl_id=r.nhl_id,player=r.player,line=r.line,side=sd,price=float(r[pc])))
if live:
    gV=grade(pd.DataFrame(live).drop_duplicates(['gameId','nhl_id','line','side']),'side','price'); lines.append(summ(gV,'Live list DK-listable sides (since Nov 2)'))
else: lines.append('- Live list DK-listable sides (since Nov 2): none')
# social timing
f=f'{H}/social_log.csv'
if os.path.exists(f):
    S=pd.read_csv(f); lines.append(f"- Social posts logged: {len(S)} ({(S.source=='x').sum()} X, {(S.source=='reddit').sum()} Reddit); before DailyFaceoff reflected it: {(S.dfo_reflected.astype(str).str.lower()=='false').sum()}")
f=f'{H}/x_calls.csv'
if os.path.exists(f):
    X=pd.read_csv(f); d=X.x_day_utc.max(); lines.append(f"- X calls: {int(X[X.x_day_utc==d].calls.sum())} on X day {d} (cap 800; 1000/day limit)")
open(f'{H}/grade_summary.md','w').write('\n'.join(lines)+'\n'); print('\n'.join(lines))
