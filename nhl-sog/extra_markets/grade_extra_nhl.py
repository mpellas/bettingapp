"""Raw grading of the EXTRA NHL prop markets (data-only, paper; added 2026-11-15). No model, no tests, no picks.
Input:  captures/<date>/extra/<eid>_<D|C>_HHMMSS.json, written by capture.py from the SAME free ESPN/DraftKings propBets
        response it already pulls for SOG (no extra feed calls at capture time).
Prices: D = the latest D snapshot (150-210 min out). CLOSE = per line, the latest price in a snapshot 0-30 min out
        (same window as close.py). A missing D or close price stays blank; nothing is backfilled or invented.
Results: ESPN public game summary boxscore (free), keyed by the same ESPN athlete id; final games only, cached in box_cache/.
Markets graded (both sides for two-sided O/U, 'over' only for one-sided milestone/yes props):
  points (Total Points O/U + Points Milestones), assists (Total Assists + Assists Milestones),
  goals (Anytime Goalscorer = 1+, Goals Milestones, To Score 2+/3+ Goals), blocked_shots (Total Blocked Shots + Milestones),
  saves (Total Saves O/U + Goalkeeper Saves Milestones).
Captured but NOT graded: Powerplay Points Milestones (ESPN boxscore has no PP assists), First/Last/First Team Goalscorer.
O/U side: confirmed by the matching milestone price when one exists, else first-listed=over (capture.sides() rule; flagged
side_method=order_fallback, e.g. saves, whose milestones are even numbers only). Summary splits by side_method.
Player not in the boxscore (or goalie with 0:00 TOI) -> VOID_dnp. Truncated/corrupt extra snapshots are skipped (not backfilled).
Game lines (from 2026-11-22): puckline cover/push/loss at captured D/close price, plus game total and moneyline, from
  captures/<date>/gamelines/; final scores from ESPN summary (official score, OT included, SO winner +1).
Output is rebuilt each run (idempotent): extra_markets/graded/nhl_<market>.csv and extra_markets/graded/nhl_summary.csv
Usage: python3 extra_markets/grade_extra_nhl.py [YYYYMMDD ...]   (default: every captures/<date>/extra dir)"""
import json,glob,os,sys,math,time
import requests
import pandas as pd
HERE=os.path.dirname(os.path.abspath(__file__)); ROOT=os.path.dirname(HERE)
OUT=os.path.join(HERE,'graded'); BOX=os.path.join(HERE,'box_cache'); os.makedirs(OUT,exist_ok=True); os.makedirs(BOX,exist_ok=True)
SUM='https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary'; H={'User-Agent':'Mozilla/5.0'}
WIN=(0,30)
TWO={'Total Points':('points','Points Milestones'),'Total Assists':('assists','Assists Milestones'),
     'Total Blocked Shots':('blocked_shots','Blocked Shots Milestones'),'Total Saves':('saves','Goalkeeper Saves Milestones')}
ONE={'Points Milestones':'points','Assists Milestones':'assists','Goals Milestones':'goals','Blocked Shots Milestones':'blocked_shots',
     'Goalkeeper Saves Milestones':'saves','Anytime Goalscorer':'goals','To Score 2+ Goals':'goals','To Score 3+ Goals':'goals'}
FIXED_T={'Anytime Goalscorer':1,'To Score 2+ Goals':2,'To Score 3+ Goals':3}
def load_json(f):
    """Load a snapshot; skip truncated/corrupt files (e.g. 8192-byte cut mid-write) instead of crashing."""
    try:
        with open(f) as fh: return json.load(fh)
    except Exception as e:
        print(f'skip bad snapshot {f}: {e}')
        return None
def am2p(a): a=float(a); return -a/(-a+100) if a<0 else 100/(a+100)
def units(price,res):
    if price in (None,'') or res not in ('win','loss','push'): return None
    a=float(price); return 0.0 if res=='push' else -1.0 if res=='loss' else (a/100 if a>0 else 100/-a)
def lines_of(snap):
    """{(espn_id, market, bet_type, side, line): (price, player)} from one extra snapshot."""
    out={}; it=snap.get('items') or []
    by={}
    for p in it: by.setdefault(p['espn_id'],[]).append(p)
    for aid,ps in by.items():
        for tot,(mk,ms) in TWO.items():
            T=[p for p in ps if p['type']==tot and p.get('line') is not None]; M={p['target']:p['american'] for p in ps if p['type']==ms}
            for line in sorted({float(p['line']) for p in T}):
                pair=[p for p in T if float(p['line'])==line]
                if len(pair)!=2: continue
                m=M.get(line+0.5)
                if m is not None and (pair[0]['american']==m)!=(pair[1]['american']==m):
                    ov,un=(pair[0],pair[1]) if pair[0]['american']==m else (pair[1],pair[0]); how='milestone'
                else: ov,un=pair; how='order_fallback'  # same rule as capture.sides(); first-listed=over held in 1309/1324 milestone-confirmed SOG pairs
                out[(aid,mk,'ou','over',line)]=(ov['american'],ov.get('player'),how)
                out[(aid,mk,'ou','under',line)]=(un['american'],un.get('player'),how)
        for p in ps:
            mk=ONE.get(p['type'])
            if not mk: continue
            t=FIXED_T.get(p['type'],p.get('target'))
            if t is None or p.get('american') is None: continue
            bt='anytime' if p['type']=='Anytime Goalscorer' else 'milestone'
            out[(aid,mk,bt,'over',float(t)-0.5)]=(p['american'],p.get('player'),'one_sided')
    return out
def box(eid):
    f=os.path.join(BOX,f'{eid}.json')
    if os.path.exists(f): return json.load(open(f))
    try: d=requests.get(SUM,params={'event':eid},headers=H,timeout=(10,20)).json()
    except Exception as e: print(f'box fetch failed {eid}: {e}'); return None
    st=d.get('header',{}).get('competitions',[{}])[0].get('status',{}).get('type',{})
    if not st.get('completed'): return None
    S={}
    for t in d.get('boxscore',{}).get('players',[]):
        for s in t.get('statistics',[]):
            ks=s.get('keys') or []
            for a in s.get('athletes',[]):
                v=dict(zip(ks,a.get('stats',[]))); aid=str(a['athlete']['id']); r=S.setdefault(aid,{'name':a['athlete'].get('displayName'),'team':t['team'].get('abbreviation')})
                def num(k):
                    try: return float(v[k])
                    except Exception: return None
                if s.get('name')=='goalies':
                    toi=v.get('timeOnIce','0:00'); r['saves']=num('saves') if toi not in ('0:00','0','') else None; r['goalie_dnp']=toi in ('0:00','0','')
                else:
                    g,a_,b=num('goals'),num('assists'),num('blockedShots')
                    if g is not None: r.update(goals=g,assists=a_,points=(g or 0)+(a_ or 0),blocked_shots=b)
    json.dump(S,open(f,'w')); return S

def game_score(eid):
    """Final home/away scores from ESPN summary (free). Cached in box_cache/<eid>_score.json.
    Uses the official posted score (includes OT; shootout winner is +1 goal, matching US book rules
    for puckline/total/ML). Missing or not-yet-final -> None."""
    f=os.path.join(BOX,f'{eid}_score.json')
    if os.path.exists(f):
        try: return json.load(open(f))
        except Exception: pass
    try: d=requests.get(SUM,params={'event':eid},headers=H,timeout=(10,20)).json()
    except Exception as e:
        print(f'score fetch failed {eid}: {e}'); return None
    comp=(d.get('header',{}).get('competitions') or [{}])[0]
    st=(comp.get('status') or {}).get('type') or {}
    if not st.get('completed'): return None
    sides={}
    for c in comp.get('competitors') or []:
        try: sc=int(c.get('score'))
        except Exception: return None
        sides[c.get('homeAway')]={'score':sc,'abbr':((c.get('team') or {}).get('abbreviation')),
                                  'name':((c.get('team') or {}).get('displayName'))}
    if 'home' not in sides or 'away' not in sides: return None
    out={'home_score':sides['home']['score'],'away_score':sides['away']['score'],
         'home_abbr':sides['home']['abbr'],'away_abbr':sides['away']['abbr'],
         'home_name':sides['home']['name'],'away_name':sides['away']['name'],
         'period_detail':st.get('detail') or st.get('description'),
         'completed':True}
    json.dump(out,open(f,'w')); return out

def _gl_am(side):
    if not side: return None
    return side.get('american')

def gameline_sides(snap):
    """Return list of (market, side, team, line, price) from one gamelines snapshot."""
    out=[]
    if not snap: return out
    home,away=snap.get('home_abbr') or snap.get('home'), snap.get('away_abbr') or snap.get('away')
    pl=snap.get('puckline') or {}
    for which,team in (('home',home),('away',away)):
        s=pl.get(which) or {}
        if s.get('american') is None or s.get('line') is None: continue
        out.append(('puckline',which,team,float(s['line']),s['american']))
    tot=snap.get('total') or {}
    tline=tot.get('line')
    for which in ('over','under'):
        s=tot.get(which) or {}
        if s.get('american') is None or tline is None: continue
        out.append(('game_total',which,None,float(tline),s['american']))
    ml=snap.get('moneyline') or {}
    for which,team in (('home',home),('away',away)):
        s=ml.get(which) or {}
        if s.get('american') is None: continue
        out.append(('moneyline',which,team,0.0,s['american']))
    return out

def _cover(market, side, line, hs, aws):
    """Return win/loss/push from official scores."""
    if market=='puckline':
        # home line applied to home_score - away_score
        margin=(hs-aws) if side=='home' else (aws-hs)
        x=margin+float(line)
        return 'win' if x>0 else 'loss' if x<0 else 'push'
    if market=='game_total':
        tot=hs+aws
        if tot>float(line): o='win' if side=='over' else 'loss'
        elif tot<float(line): o='win' if side=='under' else 'loss'
        else: o='push'
        return o
    if market=='moneyline':
        if hs==aws: return 'push'
        won=(hs>aws)
        return 'win' if (side=='home' and won) or (side=='away' and not won) else 'loss'
    return None

def grade_gamelines(dates, t0):
    rows=[]
    for date in dates:
        fs=sorted(glob.glob(os.path.join(ROOT,'captures',date,'gamelines','*.json')))
        ev={}
        for f in fs: ev.setdefault(os.path.basename(f).split('_')[0],[]).append(f)
        for eid,ff in ev.items():
            raw=[s for s in (load_json(f) for f in ff) if s]
            S=sorted((s for s in raw if s.get('tag') in ('D','C')), key=lambda s:s['captured_utc'])
            if not S: continue
            Ds=[s for s in S if s['tag']=='D']; dsnap=Ds[-1] if Ds else None
            dl={}
            if dsnap:
                for m,side,team,line,price in gameline_sides(dsnap):
                    dl[(m,side,line)]=(price,team,dsnap['captured_utc'])
            cl={}
            for s in S:
                if WIN[0]<=s['minutes_to_start']<=WIN[1]:
                    for m,side,team,line,price in gameline_sides(s):
                        cl[(m,side,line)]=(price,team,s['captured_utc'])
            sc=game_score(eid)
            for k in sorted(set(dl)|set(cl), key=lambda x:(x[0],x[1],x[2])):
                m,side,line=k
                dp=dl.get(k,(None,None,None)); cp=cl.get(k,(None,None,None))
                team=dp[1] or cp[1]
                r={'date':date,'event':eid,'game':S[0].get('name'),'start_utc':S[0].get('start_utc'),
                   'market':m,'bet_type':'game','side':side,'team':team,'line':line,'side_method':'game_line',
                   'price_D':dp[0],'D_captured_utc':dp[2] if dp[0] is not None else None,
                   'price_close':cp[0],'close_captured_utc':cp[2] if cp[0] is not None else None,
                   'home_score':None,'away_score':None,'actual':None,'result':'PENDING'}
                if sc is not None:
                    r['home_score']=sc['home_score']; r['away_score']=sc['away_score']
                    r['period_detail']=sc.get('period_detail')
                    if m=='puckline':
                        r['actual']=(sc['home_score']-sc['away_score']) if side=='home' else (sc['away_score']-sc['home_score'])
                    elif m=='game_total':
                        r['actual']=sc['home_score']+sc['away_score']
                    else:
                        r['actual']=1 if ((side=='home' and sc['home_score']>sc['away_score']) or (side=='away' and sc['away_score']>sc['home_score'])) else 0
                    r['result']=_cover(m,side,line,sc['home_score'],sc['away_score'])
                r['units_D']=units(r['price_D'],r['result']); r['units_close']=units(r['price_close'],r['result'])
                rows.append(r)
    if not rows:
        print('gamelines: nothing captured yet')
        return
    df=pd.DataFrame(rows)
    for mk,g in df.groupby('market'):
        g.to_csv(os.path.join(OUT,f'nhl_{mk}.csv'),index=False)
    gr=df[df.result.isin(['win','loss','push'])]
    summ=[]
    for (mk,bt,side,sm_),g in gr.groupby(['market','bet_type','side','side_method']):
        d=g[g.price_D.notna()]; c=g[g.price_close.notna()]
        w=(g.result=='win').sum(); l=(g.result=='loss').sum()
        summ.append({'market':mk,'bet_type':bt,'side':side,'side_method':sm_,'n_graded':len(g),'wins':w,'losses':l,'pushes':(g.result=='push').sum(),
          'hit_rate':round(w/(w+l),4) if w+l else None,'n_at_D':len(d),'units_D':round(d.units_D.sum(),2) if len(d) else None,'roi_D':round(d.units_D.mean(),4) if len(d) else None,
          'n_at_close':len(c),'units_close':round(c.units_close.sum(),2) if len(c) else None,'roi_close':round(c.units_close.mean(),4) if len(c) else None,
          'avg_breakeven_D':round(d.price_D.map(am2p).mean(),4) if len(d) else None})
    sm=pd.DataFrame(summ)
    # append to existing summary if present
    sp=os.path.join(OUT,'nhl_summary.csv')
    if len(sm):
        if os.path.exists(sp):
            prev=pd.read_csv(sp)
            prev=prev[~prev.market.isin(['puckline','game_total','moneyline'])]
            sm=pd.concat([prev,sm],ignore_index=True)
        sm.to_csv(sp,index=False)
    print(f'gamelines: {len(df)} rows, {len(gr)} graded, {(df.result=="PENDING").sum()} pending; {time.time()-t0:.1f}s')
    if len(sm):
        gls=sm[sm.market.isin(['puckline','game_total','moneyline'])]
        if len(gls): print(gls.to_string(index=False))

def main(dates):
    ath=json.load(open(os.path.join(ROOT,'captures','athletes.json'))) if os.path.exists(os.path.join(ROOT,'captures','athletes.json')) else {}
    rows=[]; t0=time.time()
    for date in dates:
        fs=sorted(glob.glob(os.path.join(ROOT,'captures',date,'extra','*.json')))
        ev={}
        for f in fs: ev.setdefault(os.path.basename(f).split('_')[0],[]).append(f)
        for eid,ff in ev.items():
            S=sorted((s for s in (load_json(f) for f in ff) if s),key=lambda s:s['captured_utc'])
            S=[s for s in S if s.get('tag') in ('D','C')]
            if not S: continue
            Ds=[s for s in S if s['tag']=='D']; dsnap=Ds[-1] if Ds else None
            dl=lines_of(dsnap) if dsnap else {}
            cl={}
            for s in S:
                if WIN[0]<=s['minutes_to_start']<=WIN[1]:
                    for k,v in lines_of(s).items(): cl[k]=(v,s['captured_utc'])
            B=box(eid)
            for k in sorted(set(dl)|set(cl)):
                aid,mk,bt,side,line=k
                dp=dl.get(k,(None,None,None)); cp=cl.get(k,((None,None,None),None))
                player=dp[1] or cp[0][1] or (ath.get(aid) or {}).get('name') or (B or {}).get(aid,{}).get('name')
                r={'date':date,'event':eid,'game':S[0].get('name'),'start_utc':S[0].get('start_utc'),'player':player,'espn_id':aid,
                   'team':(B or {}).get(aid,{}).get('team'),'market':mk,'bet_type':bt,'side':side,'line':line,'side_method':dp[2] or cp[0][2],
                   'price_D':dp[0],'D_captured_utc':dsnap['captured_utc'] if dp[0] is not None else None,
                   'price_close':cp[0][0],'close_captured_utc':cp[1],'actual':None,'result':'PENDING'}
                if B is not None:
                    pb=B.get(aid); y=None if pb is None else pb.get(mk)
                    if y is None: r['result']='VOID_dnp'
                    else:
                        r['actual']=y; o='win' if y>line else 'loss' if y<line else 'push'
                        r['result']=o if side=='over' else {'win':'loss','loss':'win','push':'push'}[o]
                r['units_D']=units(r['price_D'],r['result']); r['units_close']=units(r['price_close'],r['result'])
                rows.append(r)
    df=pd.DataFrame(rows)
    if df.empty: print('extra NHL: nothing captured yet'); return
    for mk,g in df.groupby('market'): g.to_csv(os.path.join(OUT,f'nhl_{mk}.csv'),index=False)
    gr=df[df.result.isin(['win','loss','push'])]
    summ=[]
    for (mk,bt,side,sm_),g in gr.groupby(['market','bet_type','side','side_method']):
        d=g[g.price_D.notna()]; c=g[g.price_close.notna()]
        w=(g.result=='win').sum(); l=(g.result=='loss').sum()
        summ.append({'market':mk,'bet_type':bt,'side':side,'side_method':sm_,'n_graded':len(g),'wins':w,'losses':l,'pushes':(g.result=='push').sum(),
          'hit_rate':round(w/(w+l),4) if w+l else None,'n_at_D':len(d),'units_D':round(d.units_D.sum(),2),'roi_D':round(d.units_D.mean(),4) if len(d) else None,
          'n_at_close':len(c),'units_close':round(c.units_close.sum(),2),'roi_close':round(c.units_close.mean(),4) if len(c) else None,
          'avg_breakeven_D':round(d.price_D.map(am2p).mean(),4) if len(d) else None})
    sm=pd.DataFrame(summ); sm.to_csv(os.path.join(OUT,'nhl_summary.csv'),index=False)
    print(f'extra NHL: {len(df)} rows, {len(gr)} graded, {(df.result=="PENDING").sum()} pending, {(df.result=="VOID_dnp").sum()} void; {time.time()-t0:.1f}s')
    if len(sm): print(sm.to_string(index=False))
    # Game lines (puckline / total / ML) captured from 2026-11-22 on. Same D/close rules; no backfill.
    try:
        grade_gamelines(dates, t0)
    except Exception as e:
        print(f'gamelines grading skipped: {e}')

    # Shadow paper models (added 2026-11-22): points/puckline/saves, off the real card. Cannot break raw grading.
    try:
        import subprocess
        _py=os.path.join(ROOT,'.venv','bin','python')
        _r=subprocess.run([_py if os.path.exists(_py) else sys.executable, os.path.join(ROOT,'models_extra','grade_shadow.py')],
                          capture_output=True,text=True,timeout=120,cwd=ROOT)
        print(((_r.stdout or '').strip().splitlines() or [f'shadow models: no output (rc={_r.returncode})'])[0])
    except Exception as _se:
        print(f'shadow models skipped: {_se}')
if __name__=='__main__':
    ds=sys.argv[1:] or sorted(os.path.basename(os.path.dirname(p.rstrip('/'))) for p in glob.glob(os.path.join(ROOT,'captures','2*','extra/')))
    main(ds)
