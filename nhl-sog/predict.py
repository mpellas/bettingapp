"""Score D-snapshot DK SOG lines with the frozen model; blend 0.95*books no-vig + 0.05*model; flag sides with blended EV>0.
Usage: python3 predict.py YYYYMMDD [TAG=D] [--out PATH] [--window-only] [--hhmm HHMM] [--now ISO] [--rescore]
  default      -> picks/<date>_<TAG>.csv. If that file already exists, rows of games it already holds (scored and posted by an
                  earlier pass) are kept byte-identical; only games not yet in it are scored and appended (2026-10-17), so a
                  later pass never swaps prices on posted picks. --rescore restores the old full rewrite.
  --window-only-> score only games whose puck drop is 150-210 min from now (210-240 allowed when a D snapshot exists and none
                  is newer than now), never games before 12:00 PM PT, and never games already in picks/<date>_<TAG>.csv
                  (unless --rescore). Merges them into picks/<date>_<TAG>.csv (other games' rows byte-identical) and writes
                  picks/<date>_<TAG>_<HHMM>.csv with just those games (HHMM = --hhmm or now in PT). Exit 3 if no game qualifies.
  --now ISO    -> testing: pretend it is this time (UTC if no offset).
History is always cut at games before the slate date (gameDate < date), so a re-run after the games is point-in-time (no lookahead).
--out writes elsewhere (used by audit/rebuild_stale.py for the rebuilt Oct 12-16 set; never overwrites the logged D files)."""
from features import *; import requests,re
from scipy import stats
if len(sys.argv)<2 or not re.fullmatch(r'\d{8}',sys.argv[1]): print(__doc__); sys.exit(1)
OUT=sys.argv.pop(sys.argv.index('--out')+1) if '--out' in sys.argv else None
if OUT: sys.argv.remove('--out')
def _opt(name, val=True):
    if name not in sys.argv: return None
    i=sys.argv.index(name); v=sys.argv.pop(i+1) if val else True; sys.argv.remove(name); return v
WINDOW=_opt('--window-only',False); RESCORE=_opt('--rescore',False); HHMM=_opt('--hhmm'); NOW=_opt('--now')
import window as WN
NOW=WN.ts(NOW) if NOW else pd.Timestamp.now(tz='UTC')
HHMM=HHMM or NOW.tz_convert(WN.PT).strftime('%H%M')
date=sys.argv[1]; TAG=sys.argv[2] if len(sys.argv)>2 else 'D'; W_BOOK=0.95
h=open('models/CURRENT').read().strip(); meta=json.load(open(f'models/model_{h}.json')); m=lgb.Booster(model_file=f'models/model_{h}.txt'); k=meta['k']
iso=f'{date[:4]}-{date[4:6]}-{date[6:]}'
games=requests.get(f'https://api-web.nhle.com/v1/score/{iso}',timeout=30).json()['games']
def gm(home):  # match ESPN home displayName to NHL game
    for g in games:
        if g['homeTeam']['name']['default'] in home: return g
import unicodedata
norm=lambda x:re.sub(r'[^a-z]','',unicodedata.normalize('NFKD',x or '').encode('ascii','ignore').decode().lower())
hist=load(); hist=hist[hist.gameDate<iso].reset_index(drop=True); rows=[]; lines=[]  # point-in-time cut (2026-10-17)
MAIN=f'picks/{date}_{TAG}.csv'; DONE=set() if (OUT or RESCORE) else WN.existing_ids(MAIN)  # games already scored by an earlier pass
kept_note=[]; win_note=[]
for f in sorted(glob.glob(f'captures/*/*_{TAG}.json')):
    d=json.load(open(f)); g=gm(d['home'])
    if not g or g['startTimeUTC'][:10]!=d['start_utc'][:10] and g['startTimeUTC'][:16]!=d['start_utc'][:16]: continue
    if not d['start_utc'].startswith(iso) and pd.Timestamp(d['start_utc']).tz_convert('America/Los_Angeles').strftime('%Y%m%d')!=date: continue
    if int(g['id']) in DONE: kept_note.append(d['name']); continue
    if WINDOW:
        st=g['startTimeUTC']; mins=WN.mins_to(st,NOW); lead=WN.mins_to(st,d['captured_utc'])
        why=('before 12:00 PM PT' if WN.pre_noon(st) else f'{mins:.0f} min to drop, outside {WN.WIN_LO}-{WN.WIN_HI} (or <={WN.WIN_MAX})' if not WN.in_window(st,NOW,True)
             else 'snapshot newer than now' if WN.ts(d['captured_utc'])>NOW else f'D snapshot {lead:.0f} min out (>{WN.WIN_MAX})' if lead>WN.WIN_MAX else '')
        win_note.append(f"{d['name']}: {why or f'IN WINDOW ({mins:.0f} min to drop, D snapshot {lead:.0f} min out)'}")
        if why: continue
    ha,aa=g['homeTeam']['abbrev'],g['awayTeam']['abbrev']
    for l in d['sog_lines']:
        if not l['nhl_id']: continue
        last=hist[hist.playerId==l['nhl_id']].tail(1)
        if last.empty: continue
        team=last.teamAbbrev.iloc[0]
        # current team: DailyFaceoff roster in this capture overrides last box-score team (trades)
        for tname,lu in d.get('lineups',{}).items():
            if any(norm(p['name'])==norm(l['player']) for p in lu.get('players',[])): team=ha if g['homeTeam']['name']['default'] in tname else aa if g['awayTeam']['name']['default'] in tname else team
        home=1 if team==ha else 0 if team==aa else None
        if home is None: continue  # traded / team mismatch -> skip
        rows.append(dict(playerId=l['nhl_id'],gameId=g['id'],gameDate=iso,date=pd.Timestamp(iso),teamAbbrev=team,opponentTeamAbbrev=aa if home else ha,
                         home=home,homeRoad='H' if home else 'R',D=int(last.D.iloc[0]),positionCode=last.positionCode.iloc[0],season=2026))
        lines.append(dict(l,event=d['event'],game=d['name'],gameId=g['id'],captured_utc=d['captured_utc'],side_method=l['side_method']))
if kept_note: print('kept unchanged (already scored by an earlier pass):', '; '.join(kept_note))
if WINDOW: print('window check at', NOW.tz_convert(WN.PT).strftime('%H:%M PT')); print('  '+'\n  '.join(win_note) if win_note else '  no unscored D snapshots for this slate')
if not rows:
    print('NO_WINDOW_GAMES' if WINDOW else 'no new lines to score' if kept_note else 'no lines to score'); sys.exit(3 if WINDOW else 0)
syn=pd.DataFrame(rows).drop_duplicates(['playerId','gameId'])
X=feats(pd.concat([hist,syn],ignore_index=True)); X=X[X.gameId.isin(syn.gameId)&X.shots.isna()].set_index('playerId')
L=pd.DataFrame(lines); L['mu']=m.predict(X.loc[L.nhl_id,meta['features']])
for c in ['n_prior','toi_r5','toi_r30','pptoi_r5','pptoi_r30','opp_sa_r20','sog60_r10']: L[c]=X.loc[L.nhl_id,c].values
lg_sa=hist.groupby(['gameId','opponentTeamAbbrev']).shots.sum().tail(3000).mean(); L['opp_sa_vs_lg']=L.opp_sa_r20-lg_sa
last10={pid:hist[hist.playerId==pid].shots.tail(10).values for pid in L.nhl_id.unique()}
L['l10_over_rate']=[np.mean(last10[p]>ln) for p,ln in zip(L.nhl_id,L.line)]
L['p_model_over']=1-stats.nbinom.cdf(np.floor(L.line),k,k/(k+L.mu))
L['p_blend_over']=W_BOOK*L.nv_over+(1-W_BOOK)*L.p_model_over
dec=lambda a:np.where(a.astype(float)<0,1+100/-a.astype(float),1+a.astype(float)/100)
L['ev_over']=L.p_blend_over*dec(L.over)-1; L['ev_under']=(1-L.p_blend_over)*dec(L.under)-1
L['books']=1; L['flag']='DK-only'
# ---- slot veto data (not a model input): opponent SOG allowed to the player's slot vs league, shrunk ----
cur=hist.season.max(); H=hist[hist.season>=cur-1].copy()
H['frk']=H[H.D==0].groupby(['gameId','teamAbbrev']).toi.rank(ascending=False,method='first')
H['pprk']=H.groupby(['gameId','teamAbbrev']).pptoi.rank(ascending=False,method='first')
H['slot']=np.where(H.D==1,'D',np.where(H.frk<=6,'F_top6',np.where(H.frk<=9,'F_3rd','F_4th')))
H['pp1']=(H.pprk<=5)&(H.pptoi>0.5)
def slot_ratio(mask,opp,M=20.0,w_prior=0.5):
    pg=H[mask].groupby(['gameId','opponentTeamAbbrev','season']).shots.sum().reset_index()
    lg=pg.shots.mean(); o=pg[pg.opponentTeamAbbrev==opp]; wt=np.where(o.season==cur,1.0,w_prior)
    n=wt.sum(); obs=(o.shots*wt).sum()/n if n else lg
    return (n*obs+M*lg)/(n+M)/lg, n
sl,ratios,ns=[],[],[]
for pid,opp in zip(L.nhl_id,X.loc[L.nhl_id,'opponentTeamAbbrev']):
    me=H[H.playerId==pid].tail(10)
    slot='D' if me.D.iloc[-1]==1 else ('F_top6' if me.frk.mean()<=6.5 else 'F_3rd' if me.frk.mean()<=9.5 else 'F_4th')
    r,n=slot_ratio(H.slot==slot,opp)
    if me.pp1.tail(5).mean()>=0.6: r2,_=slot_ratio(H.pp1,opp); r=(r+r2)/2; slot+='+PP1'
    sl.append(slot); ratios.append(round(r,3)); ns.append(round(n,1))
L['slot']=sl; L['opp_slot_ratio']=ratios; L['opp_slot_n_eff']=ns
L['slot_veto']=np.where(L.opp_slot_ratio<0.92,'OVER',np.where(L.opp_slot_ratio>1.08,'UNDER',''))  # side vetoed
L['pick']=np.where(L.ev_over>0,'OVER',np.where(L.ev_under>0,'UNDER',''))
L.loc[L.pick==L.slot_veto,'pick']=''
L['model_hash']=h
if OUT or (RESCORE and not WINDOW): out=OUT or MAIN; L.to_csv(out,index=False)
else:
    kept,new=WN.merge_keep(MAIN,L,set(L.gameId.astype(int))); out=MAIN
    print(MAIN,f'merged: {len(new)} game(s) written, {len(kept)} game(s) kept byte-identical')
if WINDOW: out=f'picks/{date}_{TAG}_{HHMM}.csv'; L.to_csv(out,index=False)
print(out, len(L),'lines;',(L.pick!='').sum(),'with blended EV>0'); print(L[['player','line','over','under','nv_over','mu','p_model_over','ev_over','ev_under','slot','opp_slot_ratio','slot_veto','pick']].round(3).to_string(index=False))
