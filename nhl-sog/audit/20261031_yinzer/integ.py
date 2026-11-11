import pandas as pd,glob,json,requests,os
g=pd.concat([pd.read_csv(f).assign(f=f) for f in glob.glob('../../graded/2026102[678].csv')])
bad=[];cache={}
def box(gid):
  if gid not in cache:
    fn=f'box_{gid}.json'
    if not os.path.exists(fn): open(fn,'w').write(requests.get(f'https://api-web.nhle.com/v1/gamecenter/{gid}/boxscore',timeout=30).text)
    b=json.load(open(fn));cache[gid]={p['playerId']:p['sog'] for s in('awayTeam','homeTeam') for k in('forwards','defense') for p in b['playerByGameStats'][s][k]}
  return cache[gid]
n=0
for r in g.itertuples():
  o=box(r.gameId).get(int(r.nhl_id)) if pd.notna(r.nhl_id) else None
  n+=1
  if (o is None) != pd.isna(r.actual) or (o is not None and pd.notna(r.actual) and o!=r.actual): bad.append((r.f,r.player,r.gameId,r.actual,o,r.status))
print('rows',n,'games',len(cache),'mismatch',bad)
d=pd.read_csv('../../picks/20261029_D_1233.csv');print('oct29 rows',len(d))
m=[];k=0
for r in d.itertuples():
  if pd.isna(r.nhl_id): continue
  k+=1;o=box(r.gameId).get(int(r.nhl_id))
  if o is None: m.append(r.player)
print('oct29 lined players',k,'not in box',m)
