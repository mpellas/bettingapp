import csv,json,requests,collections,math
S='/workspace/nhl-sog/'
gid={'UTA':2026020236,'TOR':2026020236,'WPG':2026020237,'MTL':2026020237,'DET':2026020238,'TBL':2026020238,'STL':2026020240,'NYR':2026020240,'MIN':2026020241,'PHI':2026020241,'VGK':2026020242,'PIT':2026020242,'DAL':2026020243,'WSH':2026020243,'COL':2026020244,'CBJ':2026020244,'EDM':2026020239,'NJD':2026020239,'CAR':2026020245,'NSH':2026020245,'ANA':2026020246,'VAN':2026020246}
ab={'Tampa Bay Lightning':'TBL','Minnesota Wild':'MIN','Philadelphia Flyers':'PHI','Washington Capitals':'WSH','Colorado Avalanche':'COL','New Jersey Devils':'NJD','Nashville Predators':'NSH','Vancouver Canucks':'VAN'}
cache={}
def game(g):
  if g in cache: return cache[g]
  t=requests.get(f'https://api.nhle.com/stats/rest/en/skater/timeonice?isGame=true&limit=-1&cayenneExp=gameId={g}').json()['data']
  b=requests.get(f'https://api-web.nhle.com/v1/gamecenter/{g}/boxscore').json()
  sog={};pos={}
  for side in ('homeTeam','awayTeam'):
    for grp in ('forwards','defense'):
      for p in b['playerByGameStats'][side][grp]: sog[p['playerId']]=p['sog'];pos[p['playerId']]='F' if grp=='forwards' else 'D'
  sh=requests.get(f'https://api.nhle.com/stats/rest/en/shiftcharts?cayenneExp=gameId={g}').json()['data']
  cache[g]=(t,sog,pos,sh);return cache[g]
def secs(s):m,x=s.split(':');return int(m)*60+int(x)
def linemates(sh,pid,team,pos,names):
  iv=collections.defaultdict(list)
  for s in sh:
    if s.get('typeCode')!=517 or not s['startTime'] or not s['endTime']:continue
    iv[s['playerId']].append((s['period'],secs(s['startTime']),secs(s['endTime'])))
  mine=iv[pid];ov=collections.Counter()
  for q,L in iv.items():
    if q==pid or q not in names or pos.get(q)!=pos.get(pid):continue
    for a in mine:
      for c in L:
        if a[0]==c[0]: ov[q]+=max(0,min(a[2],c[2])-max(a[1],c[1]))
  return [names[q] for q,_ in ov.most_common(2 if pos.get(pid)=='F' else 1)]
picks={}
for ps in ('1239','1307','1335','1436'):
  for r in csv.DictReader(open(S+f'picks/20261103_D_{ps}.csv')): picks[(ps,r['player'])]=r
rows=[]
for ps in ('1239','1307','1335','1436'):
  for r in csv.DictReader(open(S+f'shadow/xlineup/20261103_{ps}.csv')):
    if r['would_skip']!='yes':continue
    tm=ab[r['team']];g=gid[tm];t,sog,pos,sh=game(g)
    team=[x for x in t if x['teamAbbrev']==tm]
    me=[x for x in team if x['skaterFullName'].replace('-',' ').lower()==r['player'].replace('-',' ').lower() or x['lastName'].lower() in r['player'].lower()]
    pk=picks.get((ps,r['player']),{})
    if not me: rows.append(dict(r,pass_=ps,dressed='NO',actual='-',evr='-',totr='-',pp='-',mates='',cls='',side='',line=pk.get('line',''),sog=''));continue
    m=me[0];P=pos[m['playerId']];grp=[x for x in team if pos.get(x['playerId'])==P]
    evr=sorted(grp,key=lambda x:-x['evTimeOnIce']).index(m)+1
    totr=sorted(grp,key=lambda x:-x['timeOnIce']).index(m)+1
    n=3 if P=='F' else 2;act=math.ceil(evr/n)
    names={x['playerId']:x['lastName'] for x in grp}
    mates=linemates(sh,m['playerId'],tm,pos,names)
    rows.append(dict(r,pass_=ps,dressed='yes',actual=('f' if P=='F' else 'd')+str(act),evr=evr,totr=totr,pp=f"{m['ppTimeOnIce']//60}:{m['ppTimeOnIce']%60:02d}",ev=f"{m['evTimeOnIce']//60}:{m['evTimeOnIce']%60:02d}",mates='/'.join(mates),side=pk.get('pick',''),line=pk.get('line',''),sog=sog[m['playerId']]))
json.dump(rows,open('rows.json','w'),indent=1,default=str)
for x in rows: print(x['pass_'],x['player'],x['team'][:10],'DFO',x['gate_ev'],'X',x['x_ev'],'act',x['actual'],'evr',x['evr'],'totr',x['totr'],'ev',x.get('ev'),'pp',x['pp'],x['mates'],'| side',x['side'],x['line'],'sog',x['sog'])
