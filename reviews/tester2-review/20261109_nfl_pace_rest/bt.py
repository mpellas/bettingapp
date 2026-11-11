import os, sys, glob, numpy as np, pandas as pd
EV='/workspace/nfl-props/sidecars/evidence'; sys.path.insert(0, EV); import nfl_evidence as E
D = E.load(max_age_h=1e9); G = D['games'].set_index('game_id'); rows=[]
for f in sorted(glob.glob('/workspace/nfl-props/data/track/2026_wk[0-9][0-9].parquet')):
    W=int(f[-10:-8]); t=pd.read_parquet(f)
    t=t[(t.status=='settled') & t.in_scope & t.p_over_model.notna() & t.actual.notna()]
    for r in t.itertuples():
        g=G.loc[r.game_id]; h=D['by_player'].get(r.player_id)
        if h is None: continue
        h=h[h.k<2026*100+W]
        if not len(h): continue
        team=h.team.iloc[-1]
        if team not in (g.home_team,g.away_team) or r.actual==r.line_D: continue
        oppt=g.away_team if team==g.home_team else g.home_team
        for side in ('over','under'):   # both sides: tests are side-symmetric, so this checks direction
            hit=int((r.actual>r.line_D)==(side=='over'))
            pv,pw=E.x_pace(D,team,oppt,side,2026,W); rv,rw=E.x_rest(g,team,side)
            rows.append(dict(week=W,game_id=r.game_id,player=r.player_name,market=r.market,side=side,line=r.line_D,hit=hit,pace=pv,why_pace=pw,rest=rv,why_rest=rw))
X=pd.DataFrame(rows); X.to_csv(os.path.join(os.path.dirname(__file__),'rows.csv'),index=False)
O=X[X.side=='over']
print('lines',len(O),'games',O.game_id.nunique(),'weeks',sorted(O.week.unique()),'over hit',round(O.hit.mean(),3))
for k in ('pace','rest'):
    for v in (1,0,-1):
        s=X[X[k]==v]
        if len(s): print(k, {1:'+',0:'0',-1:'-'}[v], 'sides',len(s), 'hit', round(s.hit.mean(),3), 'ci', [round(x,3) for x in E.boot((s.hit-0.5).values, s.game_id.values)[1:]] if len(s)>4 else '')
