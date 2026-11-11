"""Shadow predictions of the frozen challenger for one slate. 0 credits; read-only w.r.t. the champion.
Usage: .venv/bin/python challenger/predict_challenger.py YYYYMMDD [--hash H]
Lines = picks/<date>_D.csv (the champion's D file: same DK lines, same no-vig). Inputs are CUT at the day before the
slate (player and team game logs with gameDate < date), so the output is identical whenever it is run (before or
after the games) - late runs are flagged 'late' but are not leaky. Team = player's last box-score team; a player whose
team is not in the game is skipped (logged). Writes challenger/shadow/<date>_D_<hash>.csv and appends
challenger/shadow/pred_log.jsonl (created_utc, sha256, n, late flag, inputs-through dates)."""
from common import *
import hashlib, datetime as dt, requests, argparse
ap = argparse.ArgumentParser(); ap.add_argument('date'); ap.add_argument('--hash', default=open(os.path.join(HERE, 'CHALLENGER')).read().strip())
ap.add_argument('--window-only', action='store_true'); ap.add_argument('--picks'); ap.add_argument('--rescore', action='store_true'); a = ap.parse_args()
date = a.date; iso = f'{date[:4]}-{date[4:6]}-{date[6:]}'; h = a.hash
meta = json.load(open(os.path.join(HERE, 'models', f'model_{h}.json'))); m = lgb.Booster(model_file=os.path.join(HERE, 'models', f'model_{h}.txt'))
import glob, re
sys.path.insert(0, ROOT); import window as WN
OUTF = os.path.join(HERE, 'shadow', f'{date}_D_{h}.csv'); HHMM = None
if a.window_only:
    PF = a.picks or (sorted(f for f in glob.glob(os.path.join(ROOT, 'picks', f'{date}_D_[0-9][0-9][0-9][0-9].csv')))[-1:] or [None])[0]
    if not PF: sys.exit(f'--window-only: no picks/{date}_D_<HHMM>.csv found')
    mm = re.search(r'_D_(\d{4})\.csv$', PF); HHMM = mm.group(1) if mm else dt.datetime.now(WN.PT).strftime('%H%M')
else: PF = os.path.join(ROOT, 'picks', f'{date}_D.csv')
D = pd.read_csv(PF)
DONE = set() if (a.rescore or a.window_only) else WN.existing_ids(OUTF)
if DONE: print('kept unchanged (already in shadow file):', sorted(DONE)); D = D[~D.gameId.astype(int).isin(DONE)]
if D.empty: print('no new games to score'); sys.exit(0)
# refresh inputs if they stop before yesterday (both fetchers are free and idempotent)
import subprocess
yday0 = (pd.Timestamp(iso) - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
if pd.read_pickle(os.path.join(ROOT, 'data', 's2026.pkl')).gameDate.max() < yday0:
    subprocess.run([sys.executable, 'fetch.py'], cwd=ROOT, capture_output=True, timeout=600)
if pd.read_pickle(os.path.join(HERE, 'team_games.pkl')).gameDate.max() < yday0:
    subprocess.run([sys.executable, os.path.join(HERE, 'fetch_team.py')], cwd=ROOT, capture_output=True, timeout=600)
cwd = os.getcwd(); os.chdir(ROOT); hist = F.load(); os.chdir(cwd)
hist = hist[hist.gameDate < iso]
tg = pd.read_pickle(os.path.join(HERE, 'team_games.pkl')); tg = tg[tg.gameDate < iso]
inputs_through = dict(players=hist.gameDate.max(), teams=tg.gameDate.max())
yday = (pd.Timestamp(iso) - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
stale = inputs_through['players'] < yday or inputs_through['teams'] < yday  # no games yesterday also triggers this: checked below
sched = {g['id']: g for g in requests.get(f'https://api-web.nhle.com/v1/score/{iso}', timeout=30).json()['games']}
if stale:
    yg = requests.get(f'https://api-web.nhle.com/v1/score/{yday}', timeout=30).json().get('games', [])
    stale = len(yg) > 0 and (inputs_through['players'] < yday or inputs_through['teams'] < yday)
rows, skipped = [], []
for r in D.drop_duplicates(['nhl_id', 'gameId']).itertuples():
    g = sched.get(r.gameId); last = hist[hist.playerId == r.nhl_id].tail(1)
    if g is None or last.empty: skipped.append((r.player, 'no schedule/history')); continue
    ha, aa = g['homeTeam']['abbrev'], g['awayTeam']['abbrev']; team = last.teamAbbrev.iloc[0]
    if team not in (ha, aa): skipped.append((r.player, f'team {team} not in {aa}@{ha}')); continue
    home = int(team == ha)
    rows.append(dict(playerId=r.nhl_id, gameId=r.gameId, gameDate=iso, date=pd.Timestamp(iso), teamAbbrev=team, opponentTeamAbbrev=aa if home else ha,
                     home=home, homeRoad='H' if home else 'R', D=int(last.D.iloc[0]), positionCode=last.positionCode.iloc[0], season=int(last.season.iloc[0])))
syn = pd.DataFrame(rows)
X = C.add(F.feats(pd.concat([hist, syn], ignore_index=True)), tg)
X = X[X.gameId.isin(syn.gameId) & X.shots.isna()].set_index(['playerId', 'gameId'])
D = D[[ (p, g) in X.index for p, g in zip(D.nhl_id, D.gameId)]].copy()
XR = X.loc[list(zip(D.nhl_id, D.gameId))]
D['mu_chal'] = m.predict(XR[meta['features']]); D['k_chal'] = meta['k']
D['p_chal_over'] = p_over(D.line.values, D.mu_chal.values, meta['k'])
D['chal_hash'] = h; D['inputs_players_through'] = inputs_through['players']; D['inputs_teams_through'] = inputs_through['teams']
now = dt.datetime.now(dt.timezone.utc)
first_drop = min(pd.Timestamp(sched[g]['startTimeUTC']) for g in D.gameId.unique())
D['created_utc'] = now.isoformat(timespec='seconds'); D['late'] = now > first_drop.to_pydatetime(); D['stale_inputs'] = stale
os.makedirs(os.path.join(HERE, 'shadow'), exist_ok=True)
keep = ['player', 'nhl_id', 'gameId', 'game', 'line', 'nv_over', 'p_model_over', 'mu', 'mu_chal', 'k_chal', 'p_chal_over', 'chal_hash',
        'inputs_players_through', 'inputs_teams_through', 'created_utc', 'late', 'stale_inputs']
if a.rescore and not a.window_only: D[keep].to_csv(OUTF, index=False)
else: kept, new = WN.merge_keep(OUTF, D[keep], set(D.gameId.astype(int))); print(OUTF, f'merged: {len(new)} game(s) written, {len(kept)} kept byte-identical')
out = OUTF
if a.window_only: out = os.path.join(HERE, 'shadow', f'{date}_D_{h}_{HHMM}.csv'); D[keep].to_csv(out, index=False)
sha = hashlib.sha256(open(out, 'rb').read()).hexdigest()
open(os.path.join(HERE, 'shadow', 'pred_log.jsonl'), 'a').write(json.dumps(dict(date=date, file=os.path.basename(out), sha256=sha, n=len(D), skipped=skipped,
    created_utc=now.isoformat(timespec='seconds'), late=bool(D.late.any()), stale_inputs=bool(stale), inputs_through=inputs_through)) + '\n')
print(out, len(D), 'lines; skipped', skipped, '; late' if D.late.any() else '', '; STALE INPUTS' if stale else '')
