"""Rebuild the Oct 12-16 2026 pick-time predictions point-in-time on gap-free data (2026-10-17, yinzerduck: 'no gaps').
For each slate date: champion c3ab760178 (predict.py) and challenger 3386583f18 (challenger/predict_challenger.py)
re-scored on the DK lines actually captured that day (captures/*/<event>_D.json), with history cut at gameDate < slate
date (no lookahead), then graded with grade.py (same voids, same C close, same z-CLV).
Runs in a sandbox copy so the logged files (picks/<date>_D.csv, graded/<date>.csv, challenger/shadow/) are NEVER touched.
Outputs: rebuilt/picks/<date>_D_rebuilt.csv, rebuilt/challenger/<date>_D_rebuilt_<hash>.csv, rebuilt/graded/<date>.csv (logged closes; see bottom) and rebuilt/graded_closepy_now/<date>.csv (strict re-grade with today's close.py).
These are RETRO-COMPUTED, not live decisions. Usage: .venv/bin/python audit/rebuild_stale.py [dates...]"""
import os, sys, shutil, subprocess, glob
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); PY = os.path.join(ROOT, '.venv', 'bin', 'python')
DATES = sys.argv[1:] or ['20261012', '20261013', '20261014', '20261015', '20261016']
SB = '/tmp/nhl_rebuild_sandbox'; shutil.rmtree(SB, ignore_errors=True)
os.makedirs(f'{SB}/picks'); os.makedirs(f'{SB}/graded'); os.makedirs(f'{SB}/challenger/shadow')
for n in ('data', 'models', 'captures'): os.symlink(f'{ROOT}/{n}', f'{SB}/{n}')
for f in glob.glob(f'{ROOT}/*.py'): shutil.copy(f, SB)
for f in glob.glob(f'{ROOT}/challenger/*.py'): shutil.copy(f, f'{SB}/challenger/')
for n in ('models', 'team_games.pkl', 'CHALLENGER'): os.symlink(f'{ROOT}/challenger/{n}', f'{SB}/challenger/{n}')
H = open(f'{ROOT}/challenger/CHALLENGER').read().strip()
for d in ('picks', 'challenger', 'graded_closepy_now'): os.makedirs(f'{ROOT}/rebuilt/{d}', exist_ok=True)
run = lambda *a: print(subprocess.run([PY, *a], cwd=SB, capture_output=True, text=True, timeout=900).stdout.splitlines()[:1])
for d in DATES:
    run('predict.py', d)                                  # -> SB/picks/<d>_D.csv (history cut at gameDate < d)
    run('challenger/predict_challenger.py', d)            # reads SB/picks/<d>_D.csv, inputs cut at gameDate < d
    run('grade.py', d)                                    # -> SB/graded/<d>.csv
    shutil.copy(f'{SB}/picks/{d}_D.csv', f'{ROOT}/rebuilt/picks/{d}_D_rebuilt.csv')
    shutil.copy(f'{SB}/challenger/shadow/{d}_D_{H}.csv', f'{ROOT}/rebuilt/challenger/{d}_D_rebuilt_{H}.csv')
    shutil.copy(f'{SB}/graded/{d}.csv', f'{ROOT}/rebuilt/graded_closepy_now/{d}.csv')
shutil.copy(f'{SB}/challenger/shadow/pred_log.jsonl', f'{ROOT}/rebuilt/challenger/pred_log.jsonl')
print('done', DATES)

# ---- Same-close grading (primary rebuilt record) ----------------------------------------------------------------
# Oct 12-14 captures have no snapshot archive; today's close.py (archive-based, d2a1b6e) finds fewer in-window closes
# for events 401892486/492/493 than the original grading did. To compare rebuilt vs logged on IDENTICAL lines and
# closes, rebuilt/graded/<date>.csv = the logged graded/<date>.csv (status, actual, nv_over_C, line_C unchanged) with
# every prediction column replaced by the rebuilt value. rebuilt/graded_closepy_now/ keeps the strict re-grade.
import pandas as pd
os.makedirs(f'{ROOT}/rebuilt/graded', exist_ok=True)
KEEP = ['espn_id', 'player', 'nhl_id', 'line', 'over', 'under', 'over_open', 'under_open', 'nv_over', 'side_method', 'order_matches',
        'event', 'game', 'gameId', 'captured_utc', 'actual', 'status', 'nv_over_C', 'line_C']
for d in DATES:
    g = pd.read_csv(f'{ROOT}/graded/{d}.csv'); r = pd.read_csv(f'{ROOT}/rebuilt/picks/{d}_D_rebuilt.csv')
    pred = [c for c in r.columns if c not in KEEP]
    m = g[KEEP].merge(r[['nhl_id', 'gameId', 'line'] + pred], on=['nhl_id', 'gameId', 'line'], how='left')
    assert m.mu.notna().all() and len(m) == len(g), (d, m.mu.isna().sum())
    # actuals: official boxscore today (audit/boxscores.pkl). 4 logged actuals predate NHL stat corrections (Benson, Cozens, Skjei, Kindel).
    B = pd.read_pickle(f'{ROOT}/audit/boxscores.pkl').set_index(['playerId', 'gameId']).sog
    off = [B.get((p, g)) for p, g in zip(m.nhl_id, m.gameId)]
    m['actual_logged'] = m.actual; m['actual'] = [o if o is not None else a for o, a in zip(off, m.actual)]
    m['rebuilt'] = 'retro-computed 2026-10-17, point-in-time, gap-free data; not a live decision'
    m.to_csv(f'{ROOT}/rebuilt/graded/{d}.csv', index=False)
print('same-close rebuilt grading written')
