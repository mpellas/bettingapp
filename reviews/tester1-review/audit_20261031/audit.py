import csv,glob,json,os,re,urllib.request
N='/workspace/nhl-sog'
def rows(f): return list(csv.DictReader(open(f)))
# actuals + closes from graded
act={};clo={}
for f in glob.glob(N+'/graded/2026102*.csv'):
  if not re.search(r'/\d{8}\.csv$',f): continue
  for r in rows(f):
    k=(r['gameId'],r['nhl_id'],r['line'])
    if r.get('actual') not in (None,''): act[(r['gameId'],r['nhl_id'])]=float(r['actual'])
    if r.get('nv_over_C') and r.get('line_C')==r['line']: clo[k]=float(r['nv_over_C'])
for f in glob.glob(N+'/captures/2026102*/*_CLOSE.json')+glob.glob(N+'/captures/2026103*/*_CLOSE.json'):
  d=json.load(open(f))
  for c in d.get('closed',[]):
    clo.setdefault((None,str(c['nhl_id']),str(c['line'])),c['nv_over'])
box={}
def fetch(g,pid):
  if (g,pid) in act: return act[(g,pid)]
  if g not in box:
    try:
      j=json.load(urllib.request.urlopen(urllib.request.Request(f'https://api-web.nhle.com/v1/gamecenter/{g}/boxscore',headers={'User-Agent':'x'}),timeout=20))
      m={}
      if j.get('gameState') in ('OFF','FINAL'):
        for t in ('awayTeam','homeTeam'):
          for grp in j['playerByGameStats'][t].values():
            for p in grp:
              if 'sog' in p: m[str(p['playerId'])]=p['sog']
      box[g]=m
    except Exception as e: box[g]={}
  return box[g].get(pid)
def dec(a): a=float(a); return a/100 if a>0 else 100/-a
def gate(pas):
  return rows(f'{N}/picks/{pas[:8]}_D_{pas[9:]}_GATE.csv')
def grade(pas,player,side,bucket,tag,shop=None,src=''):
  g=[r for r in gate(pas) if r['player']==player]
  if not g: return dict(pass_id=pas,player=player,side=side,bucket=bucket,tag=tag,status='NOT_IN_GATE')
  r=g[0]; line=r['line']; price=r['over' if side=='OVER' else 'under']
  a=fetch(r['gameId'],r['nhl_id'])
  c=clo.get((r['gameId'],r['nhl_id'],line)); c=c if c is not None else clo.get((None,r['nhl_id'],line))
  nv=float(r['nv_over']); res=''; u=''; su=''
  if a is not None:
    a=float(a); win=(a>float(line)) if side=='OVER' else (a<float(line))
    res='W' if win else 'L'; u=round(dec(price),3) if win else -1
    if shop: su=round(dec(shop),3) if win else -1
  clv='' if c is None else round(((c-nv) if side=='OVER' else (nv-c))*100,1)
  pb=float(r['p_blend_over']); edge=round(((pb-nv) if side=='OVER' else (nv-pb))*100,1)
  return dict(pass_id=pas,player=player,game=r['game'],gameId=r['gameId'],side=side,line=line,dk_price=price,shop_at=shop or '',
    nv_pick=nv,blend_edge_pts=edge,actual=a if a is not None else '',result=res or 'UNGRADED',units_dk=u,units_shop=su,
    nv_close=c if c is not None else '',clv_pts=clv,bucket=bucket,tag=tag,source=src)
out=[]
B1=[('20261026_1311','Trevor Moore','OVER','-123','over_bias'),('20261026_1311','Alex Laferriere','UNDER','-123','rising_toi_under'),
('20261026_1438','Darren Raddysh','UNDER','-107','other'),('20261026_1516','Kasperi Kapanen','UNDER','+105','rising_toi_under'),
('20261027_1305','Travis Sanheim','OVER','+124','over_bias'),('20261027_1305','Christian Dvorak','UNDER','-105','rising_toi_under'),('20261027_1305','Alex Bump','UNDER','+107','other'),
('20261027_1339','Logan Stankoven','OVER','+125','over_bias'),('20261027_1432','Dylan Guenther','UNDER','+133','market_move'),
('20261027_1533','Tomas Hertl','UNDER','','other'),('20261027_1533','Jackson LaCombe','UNDER','','rising_toi_under'),('20261027_1533','Cutter Gauthier','UNDER','','rising_toi_under'),
('20261027_1609','Jack Quinn','UNDER','+109','rising_toi_under'),
('20261028_1304','Travis Sanheim','OVER','+129','over_bias'),('20261028_1304','Trevor Zegras','OVER','-107','over_bias'),('20261028_1304','Aliaksei Protas','UNDER','-103','cleared_unpriced'),
('20261028_1509','Sam Malinski','UNDER','-121','cleared_unpriced'),('20261028_1535','William Nylander','OVER','+101','falling_toi_over'),('20261028_1535','Darren Raddysh','UNDER','-112','cleared_unpriced'),
('20261029_1233','Gage Goncalves','UNDER','-121','rising_toi_under'),('20261029_1233','MacKenzie Weegar','OVER','-103','over_bias'),('20261029_1233','Dylan Guenther','UNDER','+129','market_move'),
('20261029_1233','Nikolaj Ehlers','OVER','-145','over_bias'),('20261029_1233','Sebastian Aho','OVER','-103','over_bias')]
for p,n,s,sh,t in B1: out.append(grade(p,n,s,'1_fliff_skip',t,sh or None,'room+card_decisions'))
B2=[('20261027_1305','Zach Werenski','UNDER','-137'),('20261027_1339','Timo Meier','OVER','+109'),('20261027_1339','Jesper Bratt','OVER','-121'),('20261027_1339','Jack Hughes','OVER','-127'),
('20261027_1432','Blake Coleman','OVER','-117'),('20261027_1533','Jake DeBrusk','UNDER','-117'),("20261027_1533","Drew O'Connor",'UNDER','-132')]
for p,n,s,sh in B2: out.append(grade(p,n,s,'2_stale_lineup','stale_12h',sh,'room'))
# bucket 3 from GATE: latest pass per player/game/side
seen={}
for f in sorted(glob.glob(N+'/picks/2026102[6-9]_D_*_GATE.csv')):
  pas=os.path.basename(f)[:8]+'_'+os.path.basename(f).split('_')[2]
  for r in rows(f):
    for side,flag,kind in (('OVER',r.get('role_veto_over')=='True','role_demotion'),('UNDER',r.get('role_veto_under')=='True','role_promotion'),
                           (r.get('slot_veto'),bool(r.get('slot_veto')),'slot')):
      if flag: seen[(r['gameId'],r['player'],side,kind)]=(pas,r['player'],side,kind)
for p,n,s,k in seen.values(): out.append(grade(p,n,s,'3_role_slot_veto',k,None,'GATE'))
keys=list(dict.fromkeys(k for o in out for k in o))
w=csv.DictWriter(open('skipped_sides.csv','w'),fieldnames=keys);w.writeheader();w.writerows(out)
