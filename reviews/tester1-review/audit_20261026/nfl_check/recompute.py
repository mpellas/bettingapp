import sys,json,glob; sys.path.insert(0,'/workspace/props-finder'); import find as F
Q=[('20261011T1237','Malik Willis','rush_attempts',5.5,'Under'),('20261011T1237','Drake Maye','rush_attempts',5.5,'Under'),('20261011T1237','Omarion Hampton','rush_attempts',11.5,'Over'),('20261011T1237','Jacory Croskey-Merritt','rush_attempts',13.5,'Under'),('20261011T1237','Calvin Ridley','receptions',0.5,'Under'),('20261012T2133','Ty Johnson','rush_yds',5.5,'Under'),('20261018T1440','Omarion Hampton','reception_yds',5.5,'Under')]
cache={}
for raw,p,m,l,s in Q:
    if raw not in cache: cache[raw]=F.analyze([json.load(open(f)) for f in glob.glob(f'/workspace/props-finder/raw/{raw}/*.json')],books_allow={'draftkings','fliff'})
    r=[x for x in cache[raw] if x['player']==p and x['market']==m and x['line']==l and x['side']==s]
    print(raw,p,m,l,s,[(x['book'],x['price'],x['fair_prob'],x['ev_pct'],x['n_books']) for x in r])
