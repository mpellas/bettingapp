"""Leakage test for challenger features: corrupt every outcome on/after a cutoff day (player shots/toi/pp/att and
team goals/shots); features ON the cutoff day must not change. Three cutoffs. Exit 1 on failure."""
import sys, os, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.dirname(HERE)); os.chdir(os.path.dirname(HERE))
import features as F, cfeatures as C
base = F.load(); tg = pd.read_pickle(os.path.join(HERE, 'team_games.pkl'))
cols = list(dict.fromkeys(F.FEATS(F.feats(base.copy())) + sum(C.GROUPS.values(), [])))
A = C.add(F.feats(base.copy()), tg)
ok = True
for q in (0.3, 0.6, 0.9):
    cut = base.date.sort_values().iloc[int(len(base) * q)]
    b = base.copy(); fut = b.date >= cut
    for c in ['shots', 'timeOnIcePerGame', 'ppTimeOnIce', 'totalShotAttempts']: b.loc[fut, c] = 999
    t = tg.copy(); tf = pd.to_datetime(t.gameDate) >= cut
    for c in ['goalsFor', 'goalsAgainst', 'shotsForPerGame', 'shotsAgainstPerGame']: t.loc[tf, c] = 999
    Bf = C.add(F.feats(F.load.__globals__['pd'].DataFrame(b).pipe(lambda d: (d.assign(toi=d.timeOnIcePerGame/60, pptoi=d.ppTimeOnIce.fillna(0)/60, att=d.totalShotAttempts)))), t)
    k = ['playerId', 'gameId']
    a = A[A.date == cut].set_index(k)[cols].sort_index(); bb = Bf[Bf.date == cut].set_index(k)[cols].sort_index()
    bad = [c for c in cols if not np.allclose(a[c].astype(float).fillna(-1), bb[c].astype(float).fillna(-1))]
    print(cut.date(), len(a), 'rows;', 'PASS' if not bad else f'FAIL {bad}'); ok &= not bad
sys.exit(0 if ok else 1)
