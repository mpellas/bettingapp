import json,os,time,datetime as dt,urllib.request as U
S='https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates=%s'
C='https://sports.core.api.espn.com/v2/sports/hockey/leagues/nhl/events/%s/competitions/%s/odds/100/propBets?limit=1000&page=%d'
def g(u):
  for a in range(3):
    try: return json.load(U.urlopen(u,timeout=30))
    except Exception as e:
      if '404' in str(e): return None
      time.sleep(2)
d=dt.date(2025,10,7)
while d<=dt.date(2026,10,31):
  s=g(S%d.strftime('%Y%m%d')) or {}
  for e in s.get('events',[]):
    f='nhl_raw/%s_%s.json'%(d,e['id'])
    if os.path.exists(f): continue
    items=[];p=1
    while True:
      r=g(C%(e['id'],e['id'],p))
      if not r: break
      items+=r['items']
      if p>=r.get('pageCount',1): break
      p+=1
    keep=[i for i in items if 'Shots on Goal' in i.get('type',{}).get('name','')]
    json.dump({'event':e['id'],'date':str(d),'name':e['name'],'start':e['date'],'items':keep},open(f,'w'))
  d+=dt.timedelta(1)
print('done')
