import json,urllib.request,concurrent.futures as cf,datetime as dt,csv
def get(u):
    for _ in range(3):
        try:
            with urllib.request.urlopen(u,timeout=30) as r: return json.load(r)
        except Exception: pass
    return {}
jobs=[]
for y in (2019,2021,2022,2023,2024,2025):
    d=dt.date(y,8,20)
    while d<=dt.date(y+1,1,25):
        jobs.append(d.strftime('%Y%m%d')); d+=dt.timedelta(days=1)
def one(ds):
    j=get(f'https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?dates={ds}&groups=80&limit=400')
    out=[]
    for e in j.get('events',[]):
        c=e['competitions'][0]
        if c['status']['type'].get('state')!='post': continue
        t={x['homeAway']:x for x in c['competitors']}
        out.append([e['id'],ds,e['season']['year'],t['home']['team']['abbreviation'],t['away']['team']['abbreviation'],int(t['home']['score']),int(t['away']['score']),c.get('neutralSite')])
    return out
rows={}
with cf.ThreadPoolExecutor(16) as ex:
    for r in ex.map(one,jobs):
        for x in r: rows[x[0]]=x
w=csv.writer(open('fbs_results.csv','w',newline=''));w.writerow(['event_id','date','season','home','away','hs','as','neutral'])
w.writerows(rows.values());print(len(rows))
