"""Raw grading of EXTRA NFL prop markets (data-only, paper; added 2026-11-15). No model, no tests, no picks.
Input: the raw ESPN/DraftKings propBets pages ALREADY saved by the pinned capture loop (data/snapshots/, listed in
capture_log.jsonl, sha256 re-checked). No new feed calls for lines; read-only on every pinned file.
IMPORTANT: DraftKings-via-ESPN player props carry NO PRICES in 2026 (targets only). Those rows are graded over/under
AT THE LINE with price left blank; no units are computed (nothing is assumed). Hit rates only; -110 break-even (52.4%)
is a reference.
SPREAD (added 2026-11-22): the same loop already saves the game-level DraftKings odds file (spread + moneyline + total,
WITH American prices). BOTH SIDES of every game are graded ATS (cover/push/loss) at the captured price; units are computed.
Because both sides are graded, cover and loss counts are always symmetric (they differ only when some rows are still
pending) and the units total is just the juice. nfl_spread.csv is raw ATS data, not a model result. It only means
something once a side-picking spread model exists. No Odds API / Fliff. Windows are the same as the player extras.
Windows (same definitions as snaplines.py): D = last capture <= reported kickoff - 3 h with lines for the market;
CLOSE = last capture in [actual kickoff - 30 min, kickoff) with lines (actual kickoff = earliest reported). No fallback.
A (player, market) with 2+ distinct lines in one snapshot -> VOID_duplicate_line (no main-line flag; none preferred).
Results: ESPN public game summary boxscore (free), same ESPN athlete ids; final games only; cached in box_cache/.
Markets (full game only): receptions, rush_att (Total Carries), pass_cmp, pass_att, pass_td, pass_int, rush_rec_yds,
pass_rush_yds, longest_rec, longest_rush, tackles_solo (Total Tackles), tackle_assists (Total Assists),
tackles_total (Total Tackles Plus Assists), sacks, fg_made, xp_made, kicking_pts, plus game spread (ATS, both sides).
NOT graded: Anytime/First/Last TD scorer (no line and no price in the feed), milestones (one-sided, no price),
Longest Passing Completion (not in ESPN boxscore), 1st-half/quarter markets, and pass/rush/rec yards (graded by track.py).
Output (rebuilt each run): sidecars/extra_markets/graded/nfl_<market>.csv and nfl_summary.csv
Usage: .venv/bin/python sidecars/extra_markets/grade_extra_nfl.py [--season 2026] [--week N]"""
import argparse,datetime as dt,hashlib,json,os,re,sys,time
from pathlib import Path
import pandas as pd, requests
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]; SNAP=ROOT/'data'/'snapshots'; LOG=SNAP/'capture_log.jsonl'
OUT=HERE/'graded'; BOX=HERE/'box_cache'; OUT.mkdir(exist_ok=True); BOX.mkdir(exist_ok=True)
SUM='https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary'; H={'User-Agent':'Mozilla/5.0'}
from zoneinfo import ZoneInfo; PT=ZoneInfo('America/Los_Angeles')
MK={'Total Receptions':'receptions','Total Carries':'rush_att','Total Pass Completions':'pass_cmp','Total Passing Attempts':'pass_att',
    'Total Passing Touchdowns':'pass_td','Total Passing Interceptions':'pass_int','Total Rushing Plus Receiving Yards':'rush_rec_yds',
    'Total Passing Plus Rushing Yards':'pass_rush_yds','Longest Reception':'longest_rec','Longest Rush':'longest_rush',
    'Total Tackles':'tackles_solo','Total Assists':'tackle_assists','Total Tackles Plus Assists':'tackles_total','Total Sacks':'sacks',
    'Total Field Goals Made':'fg_made','Total Extra Points Made':'xp_made','Total Kicking Points':'kicking_pts'}
def clean(n): return re.sub(r'\s*\(incl\.? overtime\)\s*$','',n or '',flags=re.I).strip()
def parse(items):
    """{(espn_id, market): set(lines)} for the extra markets (targets only; no prices exist)."""
    out={}
    for it in items:
        mk=MK.get(clean((it.get('type') or {}).get('name'))); m=re.search(r'/athletes/(\d+)',(it.get('athlete') or {}).get('$ref',''))
        t=((it.get('current') or {}).get('target') or {}).get('value')
        if mk and m and t is not None: out.setdefault((m.group(1),mk),set()).add(float(t))
    return out
def items_of(rec):
    day=SNAP/pd.Timestamp(rec['captured_at_utc']).tz_convert(PT).strftime('%Y-%m-%d'); it=[]
    for f in rec['files']:
        if '_odds_' in f['file']: continue
        p=day/f['file']
        if not p.exists(): continue
        b=p.read_bytes()
        if hashlib.sha256(b).hexdigest()!=f['sha256']: raise ValueError(f'hash mismatch {f["file"]}')
        try: it+=json.loads(b).get('items',[])
        except Exception: pass
    return it
def _amer(v):
    """Parse an American-odds value from ESPN odds JSON (string '+170'/'-116' or numeric)."""
    if v is None or v=='': return None
    if isinstance(v,str):
        v=v.strip().replace('−','-')
        if v in ('','PK','even','EVEN'): return None
        try: return int(float(v))
        except Exception: return None
    try:
        x=float(v)
        return int(x) if x==int(x) else x
    except Exception: return None
def _line(v):
    if v is None or v=='': return None
    if isinstance(v,str):
        v=v.strip().replace('−','-')
        if v in ('','PK','pk','Pick','PICK'): return 0.0
        try: return float(v)
        except Exception: return None
    try: return float(v)
    except Exception: return None
def parse_odds(rec):
    """Both sides of the DK game spread from the already-saved _odds_ file. None if missing/empty."""
    day=SNAP/pd.Timestamp(rec['captured_at_utc']).tz_convert(PT).strftime('%Y-%m-%d')
    for f in rec.get('files') or []:
        if '_odds_' not in f['file']: continue
        p=day/f['file']
        if not p.exists(): return None
        b=p.read_bytes()
        if hashlib.sha256(b).hexdigest()!=f['sha256']: raise ValueError(f'hash mismatch {f["file"]}')
        try: d=json.loads(b)
        except Exception: return None
        items=d.get('items') or []
        if not items: return None
        it=items[0]
        out={}
        for side in ('away','home'):
            s=it.get(f'{side}TeamOdds') or {}
            cur=s.get('current') or {}
            line=_line((cur.get('pointSpread') or {}).get('american') or (cur.get('pointSpread') or {}).get('alternateDisplayValue'))
            price=_amer((cur.get('spread') or {}).get('american') or (cur.get('spread') or {}).get('alternateDisplayValue') or s.get('spreadOdds'))
            href=((s.get('team') or {}).get('$ref')) or ''
            m=re.search(r'/teams/(\d+)',href)
            if line is None: return None
            out[side]={'team_id':m.group(1) if m else None,'line':line,'price':price}
        return out
    return None
def box(ev):
    f=BOX/f'{ev}.json'
    if f.exists(): return json.loads(f.read_text())
    try: d=requests.get(SUM,params={'event':ev},headers=H,timeout=(10,25)).json()
    except Exception as e: print(f'box fetch failed {ev}: {e}'); return None
    if not d.get('header',{}).get('competitions',[{}])[0].get('status',{}).get('type',{}).get('completed'): return None
    S={}
    for t in d.get('boxscore',{}).get('players',[]):
        for s in t.get('statistics',[]):
            ks=s.get('keys') or []
            for a in s.get('athletes',[]):
                v=dict(zip(ks,a.get('stats',[]))); r=S.setdefault(str(a['athlete']['id']),{'name':a['athlete'].get('displayName'),'team':t['team'].get('abbreviation')})
                def n(k):
                    try: return float(str(v[k]).split('/')[0].split('-')[0])
                    except Exception: return None
                def n2(k):
                    try: return float(str(v[k]).split('/')[1])
                    except Exception: return None
                c=s.get('name')
                if c=='passing': r.update(pass_cmp=n('completions/passingAttempts'),pass_att=n2('completions/passingAttempts'),pass_yds=n('passingYards'),pass_td=n('passingTouchdowns'),pass_int=n('interceptions'))
                elif c=='rushing': r.update(rush_att=n('rushingAttempts'),rush_yds=n('rushingYards'),longest_rush=n('longRushing'))
                elif c=='receiving': r.update(receptions=n('receptions'),rec_yds=n('receivingYards'),longest_rec=n('longReception'))
                elif c=='defensive':
                    tt,so=n('totalTackles'),n('soloTackles'); r.update(tackles_total=tt,tackles_solo=so,tackle_assists=None if tt is None or so is None else tt-so,sacks=n('sacks'))
                elif c=='kicking': r.update(fg_made=n('fieldGoalsMade/fieldGoalAttempts'),xp_made=n('extraPointsMade/extraPointAttempts'),kicking_pts=n('totalKickingPoints'))
    for r in S.values():  # combos: a player with any rushing/receiving/passing row; missing component = 0 only if he has some offensive row
        if any(k in r for k in ('rush_att','receptions')): r['rush_rec_yds']=(r.get('rush_yds') or 0)+(r.get('rec_yds') or 0)
        if any(k in r for k in ('pass_att','rush_att')): r['pass_rush_yds']=(r.get('pass_yds') or 0)+(r.get('rush_yds') or 0)
    f.write_text(json.dumps(S)); _scores_from_summary(ev,d); return S
def _scores_from_summary(ev,d):
    """Cache home/away final scores from an already-fetched summary (no extra request)."""
    comps=(d.get('header',{}) or {}).get('competitions') or []
    if not comps: return None
    if not (comps[0].get('status') or {}).get('type',{}).get('completed'): return None
    out={}
    for c in comps[0].get('competitors') or []:
        side=c.get('homeAway')
        tm=c.get('team') or {}
        try: sc=float(c.get('score'))
        except Exception: return None
        if side in ('home','away'):
            out[side]={'team_id':str(tm.get('id') or ''),'abbr':tm.get('abbreviation'),'name':tm.get('displayName') or tm.get('shortDisplayName'),'score':sc}
    if 'home' not in out or 'away' not in out: return None
    (BOX/f'game_{ev}.json').write_text(json.dumps(out)); return out
def scores(ev):
    f=BOX/f'game_{ev}.json'
    if f.exists(): return json.loads(f.read_text())
    raw=BOX/f'{ev}.json'
    # Need the summary header; player cache does not include scores, so fetch once and reuse for player box if missing.
    try: d=requests.get(SUM,params={'event':ev},headers=H,timeout=(10,25)).json()
    except Exception as e: print(f'score fetch failed {ev}: {e}'); return None
    g=_scores_from_summary(ev,d)
    if g is not None and not raw.exists():
        # populate player cache too so a later box() call does not refetch
        box(ev)
    return g
def stat(B,aid,mk):
    """Actual stat. Player absent from the boxscore -> None (VOID_dnp). Present but no row for this stat type -> 0 for
    count stats (DK grades a player who played with zero catches as 0), None for 'longest' markets."""
    r=B.get(aid)
    if r is None: return None
    if mk in r: return r[mk]
    return None if mk.startswith('longest') else 0.0
def ats(margin, line):
    """cover / push / loss from (team_score - opp_score) and the team's spread line."""
    if margin is None or line is None: return None
    x=margin+line
    return 'cover' if x>0 else 'loss' if x<0 else 'push'
def units(result, price):
    """Profit on 1 unit at American odds. Push = 0; missing price or result = None."""
    if result is None or result=='push': return 0.0 if result=='push' else None
    if price is None: return None
    if result=='loss': return -1.0
    if result!='cover': return None
    p=float(price)
    if p<0: return round(100.0/abs(p),4)
    return round(p/100.0,4)
def main(season,week):
    t0=time.time()
    recs=[json.loads(l) for l in LOG.read_text().splitlines()] if LOG.exists() else []
    recs=[r for r in recs if r.get('season')==season and r.get('season_type',2)==2 and (week is None or r.get('week')==week)]
    by={}
    for r in recs: by.setdefault(r['event_id'],[]).append(r)
    now=pd.Timestamp.now(tz='UTC'); rows=[]; sp_rows=[]
    for ev,R in by.items():
        kick=min(pd.Timestamp(r['kickoff_utc']) for r in R)
        if kick>now: continue
        R=sorted(R,key=lambda r:r['captured_at_utc'])
        P=[(r,pd.Timestamp(r['captured_at_utc']),pd.Timestamp(r['kickoff_utc'])) for r in R]
        dcand=[x for x in P if x[1]<=x[2]-pd.Timedelta(hours=3)]; ccand=[x for x in P if kick-pd.Timedelta(minutes=30)<=x[1]<kick]
        D={};C={}; dsrc={};csrc={}
        for x in dcand:   # last D capture WITH lines, per market (empty captures skipped)
            L=parse(items_of(x[0]))
            for mk in {k[1] for k in L}: D[mk]={k:v for k,v in L.items() if k[1]==mk}; dsrc[mk]=x[0]['captured_at_utc']
        for x in ccand:
            L=parse(items_of(x[0]))
            for mk in {k[1] for k in L}: C[mk]={k:v for k,v in L.items() if k[1]==mk}; csrc[mk]=x[0]['captured_at_utc']
        if D or C:
            B=box(ev)
            for mk in set(D)|set(C):
                for k in set(D.get(mk,{}))|set(C.get(mk,{})):
                    aid=k[0]; dl=D.get(mk,{}).get(k); cl=C.get(mk,{}).get(k)
                    r={'season':season,'week':R[0]['week'],'event':ev,'game':R[0].get('name'),'kickoff_utc':kick.isoformat(),'espn_id':aid,
                       'player':(B or {}).get(aid,{}).get('name'),'team':(B or {}).get(aid,{}).get('team'),'market':mk,
                       'line_D':(sorted(dl)[0] if dl and len(dl)==1 else None),'D_captured_utc':dsrc.get(mk) if dl else None,
                       'line_close':(sorted(cl)[0] if cl and len(cl)==1 else None),'close_captured_utc':csrc.get(mk) if cl else None,
                       'price':None,'price_note':'no price in free feed (DK via ESPN = targets only)','actual':None,'status':'PENDING'}
                    if (dl and len(dl)>1) or (cl and len(cl)>1): r['status']='VOID_duplicate_line'
                    elif dl and not cl and ccand: r['status']='pulled_before_close'
                    if B is not None and r['status'] in ('PENDING','pulled_before_close'):
                        y=stat(B,aid,mk)
                        if y is None: r['status']='VOID_dnp'
                        else:
                            r['actual']=y; r['status']='OK' if r['status']=='PENDING' else r['status']
                    for tag in ('D','close'):
                        ln=r[f'line_{tag}']; y=r['actual']
                        r[f'result_{tag}']=None if ln is None or y is None or r['status'].startswith('VOID') else ('over' if y>ln else 'under' if y<ln else 'push')
                    rows.append(r)
        Dsp=Csp=None; dsrc_s=csrc_s=None
        for x in dcand:
            s=parse_odds(x[0])
            if s: Dsp,dsrc_s=s,x[0]['captured_at_utc']
        for x in ccand:
            s=parse_odds(x[0])
            if s: Csp,csrc_s=s,x[0]['captured_at_utc']
        if Dsp or Csp:
            # nfl_spread.csv grades BOTH sides of every game. Cover/loss are therefore
            # always symmetric, and the units total is just the juice. This is raw ATS
            # data, not a model result; it needs a side-picking spread model before the
            # record means anything.
            G=scores(ev)
            for side in ('away','home'):
                dside=(Dsp or {}).get(side); cside=(Csp or {}).get(side)
                tid=(dside or cside or {}).get('team_id')
                abbr=None; opp_abbr=None; margin=None
                if G and side in G:
                    abbr=G[side].get('abbr') or G[side].get('name')
                    other='home' if side=='away' else 'away'
                    opp_abbr=(G[other].get('abbr') or G[other].get('name')) if other in G else None
                    if G[side].get('score') is not None and G[other].get('score') is not None:
                        margin=G[side]['score']-G[other]['score']
                elif G:
                    # team_id mismatch fallback: still record the line, leave names blank
                    abbr=tid
                r={'season':season,'week':R[0]['week'],'event':ev,'game':R[0].get('name'),'kickoff_utc':kick.isoformat(),
                   'side':side,'team_id':tid,'team':abbr,'opponent':opp_abbr,'market':'spread',
                   'line_D':(dside or {}).get('line'),'price_D':(dside or {}).get('price'),'D_captured_utc':dsrc_s if dside else None,
                   'line_close':(cside or {}).get('line'),'price_close':(cside or {}).get('price'),'close_captured_utc':csrc_s if cside else None,
                   'actual_margin':margin,'status':'PENDING' if G is None else 'OK'}
                if dside and not cside and ccand: r['status']='pulled_before_close' if G is None else 'pulled_before_close'
                r['result_D']=ats(margin,r['line_D']) if r['status'] in ('OK','pulled_before_close') else None
                r['result_close']=ats(margin,r['line_close']) if r['status'] in ('OK','pulled_before_close') else None
                r['units_D']=units(r['result_D'], r['price_D'])
                r['units_close']=units(r['result_close'], r['price_close'])
                sp_rows.append(r)
    df=pd.DataFrame(rows)
    new_n=len(df); ok_n=(df.status=='OK').sum() if len(df) else 0; pend_n=(df.status=='PENDING').sum() if len(df) else 0
    void_n=df.status.str.startswith('VOID').sum() if len(df) else 0
    if week is not None and not df.empty:  # one-week run: replace only that week's rows in the existing per-market CSVs
        old=[pd.read_csv(f,dtype={'espn_id':str,'event':str}) for f in OUT.glob('nfl_*.csv') if f.name not in ('nfl_summary.csv','nfl_spread.csv')]
        old=pd.concat(old,ignore_index=True) if old else pd.DataFrame()
        if len(old): old=old[~((old.season==season)&(old.week==week))]
        df=pd.concat([old,df.astype({'espn_id':str,'event':str})],ignore_index=True)
    if not df.empty:
        for mk,g in df.groupby('market'): g.sort_values(['kickoff_utc','event','player']).to_csv(OUT/f'nfl_{mk}.csv',index=False)
    sp=pd.DataFrame(sp_rows)
    new_sp=len(sp)
    if week is not None:
        sp_path=OUT/'nfl_spread.csv'
        if sp_path.exists():
            oldsp=pd.read_csv(sp_path,dtype={'event':str,'team_id':str})
            oldsp=oldsp[~((oldsp.season==season)&(oldsp.week==week))]
            if len(sp):
                sp=pd.concat([oldsp,sp.astype({'event':str,'team_id':str})],ignore_index=True)
            else:
                sp=oldsp
        elif sp.empty:
            sp=pd.DataFrame()
    if not sp.empty:
        sp.sort_values(['kickoff_utc','event','side']).to_csv(OUT/'nfl_spread.csv',index=False)
    S=[]
    if not df.empty:
        for mk,g in df.groupby('market'):
            for tag in ('D','close'):
                x=g[g[f'result_{tag}'].notna()]; o=(x[f'result_{tag}']=='over').sum(); u=(x[f'result_{tag}']=='under').sum()
                S.append({'market':mk,'at_line':tag,'n_graded':len(x),'covers':None,'losses':None,
                          'overs':o,'unders':u,'pushes':(x[f'result_{tag}']=='push').sum(),
                          'over_rate':round(o/(o+u),4) if o+u else None,'under_rate':round(u/(o+u),4) if o+u else None,
                          'cover_rate':None,'units':None,'note':'no free prices; hit rate only (52.4% = -110 break-even reference)'})
    if not sp.empty:
        for tag in ('D','close'):
            x=sp[sp[f'result_{tag}'].notna()]; c=(x[f'result_{tag}']=='cover').sum(); l=(x[f'result_{tag}']=='loss').sum(); p=(x[f'result_{tag}']=='push').sum()
            u=x[f'units_{tag}'].dropna()
            S.append({'market':'spread','at_line':tag,'n_graded':len(x),'covers':c,'losses':l,
                      'overs':None,'unders':None,'pushes':p,
                      'over_rate':None,'under_rate':None,
                      'cover_rate':round(c/(c+l),4) if c+l else None,
                      'units':round(float(u.sum()),2) if len(u) else None,
                      'note':'ATS both sides of every game at captured DK American price; 1u per side. Cover/loss are symmetric; units are the juice only. Raw data, not a model result.'})
    if S:
        pd.DataFrame(S).to_csv(OUT/'nfl_summary.csv',index=False)
    print(f'extra NFL ({"week %s" % week if week is not None else "all weeks"}): {new_n} prop rows, {ok_n} graded, {pend_n} pending, {void_n} void; spread {new_sp} rows; files hold {len(df) if not df.empty else 0} prop + {len(sp) if not sp.empty else 0} spread; {time.time()-t0:.1f}s')
if __name__=='__main__':
    ap=argparse.ArgumentParser(); ap.add_argument('--season',type=int,default=2026); ap.add_argument('--week',type=int,default=None); a=ap.parse_args()
    main(a.season,a.week)
