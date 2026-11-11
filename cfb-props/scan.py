import json,os,sys,csv,urllib.request
from datetime import datetime,timezone,timedelta
K=os.environ.get('ODDS_API_KEY') or open('/workspace/nfl-props/data/secrets/odds_api_key').read().strip()
M='player_pass_yds,player_rush_yds,player_reception_yds'
ids=sys.argv[1:]; rows=[]
os.makedirs('raw',exist_ok=True)
for i in ids:
    u=f'https://api.the-odds-api.com/v4/sports/americanfootball_ncaaf/events/{i}/odds?apiKey={K}&regions=us&markets={M}&oddsFormat=american'
    try:
        r=urllib.request.urlopen(u); d=json.load(r)
        print(i,'used',r.headers['x-requests-used'],'rem',r.headers['x-requests-remaining'],'last',r.headers['x-requests-last'],'books',len(d.get('bookmakers',[])))
    except Exception as e: print(i,'ERR',e); continue
    json.dump(d,open(f'raw/{i}.json','w'))
