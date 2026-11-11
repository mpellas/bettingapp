import json,re,unicodedata,requests,pandas as pd
H={'User-Agent':'Mozilla/5.0'}
norm=lambda s:re.sub(r'[^a-z]','',unicodedata.normalize('NFKD',s or '').encode('ascii','ignore').decode().lower())
last=lambda s:norm(s.replace('.',' ').split()[-1])
TEAMS={'Columbus Blue Jackets':'CBJ','Winnipeg Jets':'WPG','New York Rangers':'NYR','Toronto Maple Leafs':'TOR','Washington Capitals':'WSH','Dallas Stars':'DAL','Tampa Bay Lightning':'TBL','Minnesota Wild':'MIN','Philadelphia Flyers':'PHI','Utah Mammoth':'UTA'}
G=pd.read_csv('picks/20261103_D_1239_GATE.csv')
out=[]
for team,ab in TEAMS.items():
    g=G[G.team_dfo==team].drop_duplicates('player')
    slug=re.sub(r'[^a-z0-9]+','-',team.lower()).strip('-')
    h=requests.get(f'https://www.dailyfaceoff.com/teams/{slug}/line-combinations',headers=H,timeout=20).text
    c=json.loads(re.search(r'__NEXT_DATA__" type="application/json">(.*?)</script>',h).group(1))['props']['pageProps']['combinations']
    N={}
    for p in c['players']:
        r=N.setdefault(p['name'],{'ev':None,'pp':None,'inj':p.get('injuryStatus')})
        r[p['categoryIdentifier']]=p.get('groupIdentifier')
    Nn={norm(k):v for k,v in N.items()}
    drift=[f"{r.player} {r.ev_now}/{r.pp_now}->{Nn.get(norm(r.player),{}).get('ev')}/{Nn.get(norm(r.player),{}).get('pp')}" for r in g.itertuples()
           if (str(r.ev_now),str(r.pp_now) if pd.notna(r.pp_now) else 'None')!=(str(Nn.get(norm(r.player),{}).get('ev')),str(Nn.get(norm(r.player),{}).get('pp')))]
    sch=requests.get(f'https://api-web.nhle.com/v1/club-schedule-season/{ab}/20262027',timeout=20).json()['games']
    lg=[x for x in sch if x['gameState'] in ('OFF','FINAL')][-1]
    bx=requests.get(f"https://api-web.nhle.com/v1/gamecenter/{lg['id']}/boxscore",timeout=20).json()
    sd='homeTeam' if bx['homeTeam']['abbrev']==ab else 'awayTeam'
    dressed={last(p['name']['default']):p for k in ('forwards','defense') for p in bx['playerByGameStats'][sd][k]}
    sk={last(k):(k,v) for k,v in N.items() if v['ev'] and v['ev'][0] in 'fd' and v['ev']!='d4'}
    out_now=[f"{n}({v['ev']})" for l,(n,v) in sk.items() if l not in dressed]
    in_box=[p['name']['default'] for l,p in dressed.items() if l not in sk]
    out.append(dict(team=team,dfo_updated_used=g.dfo_updated.iloc[0],dfo_updated_now=c.get('updatedAt'),
      last_game=f"{lg['gameDate']} {lg['awayTeam']['abbrev']}@{lg['homeTeam']['abbrev']} ({lg['id']})",
      dfo_skaters_not_dressed_last_game='; '.join(out_now) or '-',dressed_last_game_not_in_dfo='; '.join(in_box) or '-',
      gate_slot_vs_dfo_now='; '.join(drift) or 'identical'))
D=pd.DataFrame(out); D.to_csv('/workspace/tester2-review/20261103_stale_impact/lineup_compare.csv',index=False)
for r in out: print(r)
