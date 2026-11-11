import sys, os, glob, json
import pandas as pd, numpy as np
W = os.path.dirname(os.path.abspath(__file__)); C = os.path.join(W, 'nhl-sog')
sys.path.insert(0, C); os.chdir(C)
import evidence, evidence_extra, shrink
DATE, ISO = '20261105', '2026-11-05'
picks = pd.read_csv('picks/20261105_D_1239.csv'); gate = pd.read_csv('picks/20261105_D_1239_GATE.csv')
# --- THEIR output (copied code, unmodified)
A = evidence.annotate(picks, DATE, gate=gate)
X = evidence_extra.annotate(picks, DATE, base=A)
T = A.merge(X, on=['nhl_id', 'line', 'side'])
T.to_csv(os.path.join(W, 'their_nhl_20261105_1239_extra.csv'), index=False)
# --- MINE: raw pickles, own code
parts = [pd.read_pickle(f) for f in sorted(glob.glob('data/s202[1-5].pkl'))] + [pd.read_pickle('data/s2026.pkl'), pd.read_pickle('shadow/s2026_live.pkl')]
L = pd.concat([p[['playerId', 'gameId', 'gameDate', 'shots']] for p in parts]).drop_duplicates(['playerId', 'gameId'])
# check s2026 vs live agree on shots for overlapping games
a = pd.read_pickle('data/s2026.pkl'); b = pd.read_pickle('shadow/s2026_live.pkl')
m = a.merge(b, on=['playerId', 'gameId']); print('s2026 vs live shots mismatches:', (m.shots_x != m.shots_y).sum(), 'of', len(m))
def am2p(x): x = float(x); return -x/(-x+100) if x < 0 else 100/(x+100)
rows = []
for r in picks.itertuples():
    g = L[(L.playerId == r.nhl_id) & (L.gameDate < ISO)].sort_values(['gameDate', 'gameId'])
    leak = L[(L.playerId == r.nhl_id) & (L.gameDate >= ISO)]
    cur = g[(g.gameDate >= '2026-09-01')]
    po, pu = am2p(r.over), am2p(r.under); nvo = po/(po+pu)
    for side in ('over', 'under'):
        nv = nvo if side == 'over' else 1-nvo; vig = po if side == 'over' else pu
        hit = (cur.shots > r.line) if side == 'over' else (cur.shots < r.line)
        l10 = g.tail(10); h10 = (l10.shots > r.line) if side == 'over' else (l10.shots < r.line)
        hs, h1 = hit.mean() if len(cur) else np.nan, h10.mean() if len(l10) else np.nan
        def sg(p):
            if len(cur) < 5: return 0
            if hs >= p+0.05 and h1 >= p+0.05: return 1
            if hs <= p-0.05 and h1 <= p-0.05: return -1
            return 0
        rows.append(dict(nhl_id=r.nhl_id, player=r.player, line=r.line, side=side, n_season=len(cur), hits_season=int(hit.sum()),
                         n_l10=len(l10), hits_l10=int(h10.sum()), l10_from_last_season=int((l10.gameDate < '2026-09-01').sum()),
                         nv_mine=round(nv, 4), nv_col=r.nv_over if side == 'over' else 1-r.nv_over, my_hit=sg(nv), my_hit_vig=sg(vig),
                         games_on_or_after_date=len(leak), max_gamedate_used=g.gameDate.max()))
M = pd.DataFrame(rows)
sym = {'+': 1, '-': -1, '0': 0}
J = M.merge(T[['nhl_id', 'line', 'side', 'sig_x_hit', 'sig_x_books', 'agrees_n', 'agrees_all_n', 'tests_all_n', 'evidence_all_summary']], on=['nhl_id', 'line', 'side'], how='left')
J['their_hit'] = J.sig_x_hit.map(sym)
J.to_csv(os.path.join(W, 'nhl_hit_compare.csv'), index=False)
print('sides', len(J), 'hit mismatches', (J.their_hit != J.my_hit).sum())
print(J[J.their_hit != J.my_hit][['player', 'side', 'line', 'their_hit', 'my_hit']].to_string())
print('nv col vs mine max abs diff', (J.nv_mine - J.nv_col).abs().max())
print('would change under vig-implied:', (J.my_hit != J.my_hit_vig).sum(), J.groupby(['my_hit','my_hit_vig']).size().to_dict())
print('their hit dist', J.sig_x_hit.value_counts().to_dict(), 'books dist', J.sig_x_books.value_counts().to_dict())
print('max gamedate used', J.max_gamedate_used.max(), '| sides with <5 season games', (J.n_season < 5).sum(), '| l10 containing last-season games', (J.l10_from_last_season > 0).sum())
print('integer lines', (J.line % 1 == 0).sum())
# --- check 3: X of 7 vs original sheet, and X of 9 arithmetic
S = pd.read_excel('sheets/20261105_D_1239_picks.xlsx', 'Picks')
S['side_l'] = S.side.str.lower()
K = J.merge(S[['player', 'side_l', 'line', 'agrees_n', 'game']].rename(columns={'side_l': 'side', 'agrees_n': 'sheet_agrees_n'}), on=['player', 'side', 'line'], how='outer', indicator=True)
print('sheet merge', K._merge.value_counts().to_dict())
K['n7_diff'] = K.agrees_n != K.sheet_agrees_n
K['plus_new'] = (K.sig_x_hit == '+').astype(int) + (K.sig_x_books == '+').astype(int)
K['n9_ok'] = K.agrees_all_n == K.agrees_n + K.plus_new
print('X of 7 mismatches vs sheet:', K.n7_diff.sum(), '| X of 9 arithmetic failures:', (~K.n9_ok).sum(), '| tests_all_n values', K.tests_all_n.unique())
print(K[K.n7_diff][['player','side','line','agrees_n','sheet_agrees_n']].to_string())
K.to_csv(os.path.join(W, 'nhl_count_compare.csv'), index=False)
# rebuilt sheet (build_sheet copy) also vs original
R = pd.read_excel(os.path.join(W, 'rebuilt_20261105_D_1239_picks.xlsx'), 'Picks')
cols = [c for c in S.columns if c in R.columns]
print('rebuilt sheet has new cols:', [c for c in R.columns if c not in S.columns])
diff = {c: int((S[c].astype(str) != R[c].astype(str)).sum()) for c in cols}
print('rebuilt vs original sheet, differing cells per col:', {k: v for k, v in diff.items() if v})
print('majority lists: 4+/7', int((K.agrees_n >= 4).sum()), ' 5+/9', int((K.agrees_all_n >= 5).sum()))
