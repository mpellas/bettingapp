import sys,os,json,csv,datetime as dt,glob
sys.path.insert(0,'/workspace/nhl-sog'); os.chdir('/workspace/nhl-sog')
import fliff_prices as fp, fliff_repull as fr
PT=fp.PT; date='20261103'; log=f'fliff_credits_{date}.csv'
sides=[('Wyatt Johnston','Dallas Stars at Washington Capitals','UNDER',2.5,105,'3/7'),
       ('Oliver Bonk','Minnesota Wild at Philadelphia Flyers','UNDER',1.5,-134,'4/7 low conf (11 GP)')]
events,_=fp.get(f'{fp.BASE}/events?apiKey={fp.key()}')
rows=[]
for p,g,side,line,shop,note in sides:
    e=fp.match_event(g,events); ev=e and e['id']
    if not ev: print(p,'event not found'); continue
    mk=os.path.join(fr.MARK,f'{date}_{ev}_manual_T2R1239')
    tot,_=fp.spent(log)
    if os.path.exists(mk) or tot+1>10: print(p,'skip',tot); continue
    now=dt.datetime.now(PT)
    d,h=fp.get(f'{fp.BASE}/events/{ev}/odds?apiKey={fp.key()}&markets=player_shots_on_goal&bookmakers=fliff,draftkings&oddsFormat=american')
    json.dump(d,open(f"captures/fliff_{date}_{now:%H%M}_{ev}.json",'w'))
    with open(log,'a',newline='') as f: csv.writer(f).writerow([now.isoformat(timespec='seconds'),ev,h.get('x-requests-last',''),h.get('x-requests-remaining','')])
    os.makedirs(fr.MARK,exist_ok=True); open(mk,'w').write(now.isoformat()+' manual_T2R1239\n')
    book={}
    for bk in d.get('bookmakers',[]):
        for m in bk['markets']:
            if m['key']!='player_shots_on_goal': continue
            for o in m['outcomes']: book.setdefault(bk['key'],{}).setdefault(fp.norm(o.get('description','')),[]).append((o['name'].upper(),float(o['point']),int(o['price'])))
    def find(b):
        o=[x for x in book.get(b,{}).get(fp.norm(p),[]) if x[0]==side]; return ([x for x in o if x[1]==line] or o or [None])[0]
    fl,dk=find('fliff'),find('draftkings')
    if fl is None: st='not offered'; beats=None
    elif fl[1]!=line: st='different line'; beats=None
    else: st='offered'; beats=fp.dec(fl[2])>=fp.dec(shop)
    cred,_=fp.spent(log)
    r=dict(run_time_pt=now.isoformat(timespec='seconds'),date=date,player=p,game=g,side=side,line=line,odds_event=ev,puck_drop_pt=e['commence_time'],
      mins_to_drop=round((dt.datetime.fromisoformat(e['commence_time'].replace('Z','+00:00'))-now).total_seconds()/60),first_status=note,source='manual_T2R1239',
      repull_status=st,fliff_line=fl and fl[1],fliff_price=fl and fl[2],fliff_shop_at=shop,beats_shop_at=beats,dk_line_now=dk and dk[1],dk_price_now=dk and dk[2],credits_after=cred,dry_run=False)
    rows.append(r); print(r, 'fliff books:',list(book))
with open(fr.LOG,'a',newline='') as f: csv.DictWriter(f,fieldnames=fr.COLS,extrasaction='ignore').writerows(rows)
