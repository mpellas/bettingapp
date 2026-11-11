import pandas as pd,numpy as np
W=pd.read_csv('/workspace/prop-finder/data/raw/nfl/stats_player_week_2025.csv',low_memory=False)
P=pd.read_csv('/workspace/prop-finder/output/backtest_2025/nfl_projections_vs_actual.csv',low_memory=False)
col={'pass_yds':'passing_yards','rush_yds':'rushing_yards','rec_yds':'receiving_yards'}
P=P[P.stat.isin(col)]
s=P.sample(400,random_state=1); ok=bad=0; badrows=[]
for r in s.itertuples():
  g=W[(W.player_id==r.player_id)&(W.season_type=='REG')]
  prior=g[g.week<r.week][col[r.stat]]; incl=g[g.week<=r.week][col[r.stat]]
  act=g[g.week==r.week][col[r.stat]]
  m=round(prior.mean(),2) if len(prior) else np.nan
  if (len(prior)==r.games_season) and (np.isnan(m) or abs(m-r.season_avg)<0.02): ok+=1
  else: bad+=1; badrows.append((r.player,r.week,r.stat,r.season_avg,r.games_season,m,len(prior),round(incl.mean(),2)))
  if len(act) and abs(act.iloc[0]-r.actual)>0.5: badrows.append(('ACT',r.player,r.week,r.actual,act.iloc[0]))
print('ok',ok,'bad',bad); [print(b) for b in badrows[:15]]
# kickoff vs week check
print((pd.to_datetime(P.kickoff_utc).groupby(P.week).agg(['min','max'])).head(20))
b=[x for x in badrows if x[0]!='ACT']
print('QB-only?', set(P[P.player.isin([x[0] for x in b])].pos), 'games_season<=prior all:', all(x[4]<=x[6] for x in b), 'any equals incl-current:', any(abs(x[3]-x[7])<0.02 for x in b), 'actual mismatches:', sum(1 for x in badrows if x[0]=='ACT'))
