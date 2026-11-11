import json,urllib.request,concurrent.futures as cf,csv
rows=list(csv.DictReader(open('fbs_results.csv')))
def one(r):
    i=r['event_id']
    for _ in range(3):
        try:
            with urllib.request.urlopen(f'https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/events/{i}/competitions/{i}/odds',timeout=30) as f: d=json.load(f)
            for x in d.get('items',[]):
                n=x.get('provider',{}).get('name','')
                if 'Live' in n: continue
                return [i,n,x.get('spread'),x.get('overUnder')]
            return [i,'',None,None]
        except Exception: pass
    return [i,'ERR',None,None]
with cf.ThreadPoolExecutor(24) as ex: out=list(ex.map(one,rows))
w=csv.writer(open('fbs_odds.csv','w',newline=''));w.writerow(['event_id','provider','home_spread','total']);w.writerows(out)
import collections;print(collections.Counter(o[1] for o in out))
