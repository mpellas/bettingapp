import pandas as pd,json,glob
t=pd.read_csv('/workspace/tester1-review/audit_20261031/skipped_sides.csv',dtype={'shop_at':str,'dk_price':str})
g=pd.concat([pd.read_csv(f) for f in glob.glob('../../graded/2026102[678].csv')])
d29=pd.concat([pd.read_csv(f) for f in glob.glob('../../picks/20261029_D*.csv')])
ids={(r.player,r.gameId):r.nhl_id for r in pd.concat([g,d29]).itertuples() if pd.notna(r.nhl_id)}
box={}
for gid in [2026020204,2026020205,2026020206]:
  b=json.load(open(f'box_{gid}.json'))['playerByGameStats']
  for s in ('awayTeam','homeTeam'):
    for grp in ('forwards','defense'):
      for p in b[s][grp]: box[(gid,p['playerId'])]=p['sog']
ga={(r.player,r.gameId):r.actual for r in g.itertuples()}
def pay(p):
  p=float(p); return p/100 if p>0 else 100/-p
out=[]
for r in t.itertuples():
  a=ga.get((r.player,r.gameId))
  if (a is None or pd.isna(a)) and r.gameId>=2026020204: a=box.get((r.gameId,ids.get((r.player,r.gameId))))
  if a is None or pd.isna(a): res='UNGRADED';u=us=None
  else:
    win=(a>r.line) if r.side=='OVER' else (a<r.line)
    res='W' if win else 'L'; u=round(pay(r.dk_price),3) if win else -1
    us=(round(pay(r.shop_at),3) if win else -1) if isinstance(r.shop_at,str) and r.shop_at else None
  out.append(dict(pass_id=r.pass_id,player=r.player,gameId=r.gameId,side=r.side,line=r.line,dk=r.dk_price,shop=r.shop_at,actual_mine=a,actual_t1=r.actual,res_mine=res,res_t1=r.result,u_mine=u,u_t1=r.units_dk,us_mine=us,us_t1=r.units_shop,bucket=r.bucket,tag=r.tag,clv=r.clv_pts))
o=pd.DataFrame(out);o.to_csv('t1_rebuild.csv',index=False)
diff=o[(o.res_mine!=o.res_t1)|((o.u_mine.fillna(0)-o.u_t1.fillna(0)).abs()>0.002)]
print('DIFFS\n',diff.to_string())
def s(x,col='u_mine'):
  x=x[x.res_mine!='UNGRADED'];return f"n={len(x)} {(x.res_mine=='W').sum()}-{(x.res_mine=='L').sum()} {x[col].sum():+.2f}u"
B=o.bucket
print('skip calls',s(o[B=='1_fliff_skip']),'shop',s(o[(B=='1_fliff_skip')&o.us_mine.notna()],'us_mine'))
print('stale',s(o[B=='2_stale_lineup']),'shop',s(o[B=='2_stale_lineup'],'us_mine'))
v=o[B=='3_role_slot_veto'];print('veto rows',len(v),s(v))
vu=v.drop_duplicates(['pass_id','player','side','line']);print('veto unique',s(vu))
for tg in ['role_demotion','role_promotion','slot']: print(tg,s(v[v.tag==tg]))
for tg in ['over_bias','rising_toi_under']: print(tg,s(o[(B=='1_fliff_skip')&(o.tag==tg)]))
print('clv skip mean',o[B=='1_fliff_skip'].clv.mean().round(2),'stale',o[B=='2_stale_lineup'].clv.mean().round(2))
