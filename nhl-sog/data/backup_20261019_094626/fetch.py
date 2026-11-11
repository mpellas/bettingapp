import requests,pandas as pd,datetime as dt,time,sys,os
B='https://api.nhle.com/stats/rest/en/skater/'
REP={'summary':['shots','timeOnIcePerGame','positionCode','teamAbbrev','opponentTeamAbbrev','homeRoad','gameDate','skaterFullName'],
     'timeonice':['ppTimeOnIce','shTimeOnIce'],'realtime':['totalShotAttempts']}
SEAS={2021:('2021-10-01','2022-05-01'),2022:('2022-10-01','2023-04-20'),2023:('2023-10-01','2024-04-20'),2024:('2024-10-01','2025-04-20'),2025:('2025-10-01','2026-04-20'),2026:('2026-09-01',(dt.date.today()-dt.timedelta(1)).isoformat())}  # current season: Sep 1 (2026-27 opened Sep 29; was Oct 1 -> Sep 29-30 games missing, fixed 2026-10-17) through yesterday (box clock = PT). Was hard-coded '2026-10-11' -> inputs stale Oct 11-16 (fixed 2026-10-17, approved)
def get(rep,s,a,b):
    e=f'seasonId={s}{s+1} and gameTypeId=2 and gameDate>="{a}" and gameDate<"{b}"'
    for t in range(4):
        try:
            r=requests.get(B+rep,params={'isAggregate':'false','isGame':'true','limit':-1,'cayenneExp':e},timeout=60);d=r.json()['data'];break
        except Exception as x: time.sleep(3)
    assert len(d)<10000,(rep,a)
    return d
out=[]
for s,(a,b) in SEAS.items():
    f=f'data/s{s}.pkl'
    if os.path.exists(f) and s!=2026: continue
    d0=dt.date.fromisoformat(a);end=dt.date.fromisoformat(b)+dt.timedelta(1);parts={}
    while d0<end:
        d1=min(d0+dt.timedelta(10),end)
        for rep,cols in REP.items():
            parts.setdefault(rep,[]).extend([{k:r[k] for k in ['playerId','gameId']+cols} for r in get(rep,s,d0,d1)])
        d0=d1
    df=pd.DataFrame(parts['summary'])
    for rep in ['timeonice','realtime']: df=df.merge(pd.DataFrame(parts[rep]).drop_duplicates(['playerId','gameId']),on=['playerId','gameId'],how='left')
    if s==2021 and df.totalShotAttempts.isna().all() and os.path.exists('audit/attempts_2021.pkl'):  # NHL realtime report has no 2021-22 attempts; filled from play-by-play (audit/attempts_pbp.py, 2026-10-17)
        df=df.drop(columns='totalShotAttempts').merge(pd.read_pickle('audit/attempts_2021.pkl').rename(columns={'att_pbp':'totalShotAttempts'}),on=['gameId','playerId'],how='left'); df['totalShotAttempts']=df.totalShotAttempts.fillna(0).astype(int)
    df['season']=s; df.to_pickle(f); print(s,len(df),flush=True)
