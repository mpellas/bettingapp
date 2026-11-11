"""Sample on the Nov 5 12:39 pass: X of 7 (sheet, unchanged), X of 10 (current nhl-sog EXTRA: hit, books, rest; vendored copy,
unmodified), X of 12 (+ Tester1 att, total). Majorities: 4+ of 7, 6+ of 10, 7+ of 12."""
import os, sys
import pandas as pd, numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'vendor'))
NHL = '/workspace/nhl-sog'
import evidence_extra as EE, tester1_extra as T1
from att_signal import _norm
from sample_nov5_logs import yinzer_logs
EE.HERE = NHL   # read fliff captures from nhl-sog (read only)
date = '20261105'
G = pd.read_csv(f'{NHL}/picks/20261105_D_1239_GATE.csv')
S = pd.read_excel(f'{NHL}/sheets/20261105_D_1239_picks.xlsx', sheet_name='Picks'); S['side'] = S.side.str.lower()
idm = {(_norm(p), float(l)): int(i) for p, l, i in zip(G.player, G.line, G.nhl_id)}
S['nhl_id'] = [idm[(_norm(p), float(l))] for p, l in zip(S.player, S.line)]
base = S[['nhl_id', 'line', 'side', 'agrees_n']]
L = yinzer_logs()
cur = list(EE.EXTRA)
y10 = EE.annotate(G, date, base=base, logs=L)
EE.EXTRA.update(T1.EXTRA_T1)
y12 = EE.annotate(G, date, base=base, logs=L)
for k in T1.EXTRA_T1: EE.EXTRA.pop(k)
assert list(EE.EXTRA) == cur
# explicit n/a display for Tester1 tests
ctx = dict(logs=L, iso='2026-11-05'); disp = []
for _, r in G.iterrows():
    for side in ('over', 'under'):
        d = dict(nhl_id=r.nhl_id, line=r.line, side=side)
        for k, f in T1.EXTRA_T1.items():
            s, why = f(r, side, ctx); d[f'{k}_show'] = 'n/a' if why.startswith('n/a') else {1: '+', -1: '-', 0: '0'}[s]; d[f'{k}_why'] = why
        disp.append(d)
D = pd.DataFrame(disp)
k = ['nhl_id', 'line', 'side']
xs = [c for c in y10 if c.startswith('sig_x_')]
M = (S[['game', 'player', 'side', 'line', 'dk_price', 'status', 'agrees_n', 'nhl_id']]
     .merge(y10[k + xs + ['agrees_all_n', 'tests_all_n']].rename(columns={'agrees_all_n': 'of_10', 'tests_all_n': 'n_tests_10'}), on=k)
     .merge(y12[k + ['sig_x_att', 'sig_x_total', 'agrees_all_n', 'tests_all_n']].rename(columns={'agrees_all_n': 'of_12', 'tests_all_n': 'n_tests_12'}), on=k)
     .merge(D, on=k).rename(columns={'agrees_n': 'of_7'}))
assert len(M) == 250 and (M.n_tests_10 == 10).all() and (M.n_tests_12 == 12).all()
M.to_csv(os.path.join(HERE, 'out', '20261105_D_1239_of7_of10_of12.csv'), index=False)
print('current EXTRA:', cur, '| sides', len(M))
for c in xs + ['att_show', 'total_show']:
    print(c, 'all:', M[c].value_counts().to_dict(), '| among 4+ of 7:', M[M.of_7 >= 4][c].value_counts().to_dict())
m4 = M[M.of_7 >= 4]
print('4+ of 7:', len(m4), '| 6+ of 10:', (M.of_10 >= 6).sum(), '| 7+ of 12:', (M.of_12 >= 7).sum(),
      '| of the 67: 6+ of 10', (m4.of_10 >= 6).sum(), ', 7+ of 12', (m4.of_12 >= 7).sum())
print(pd.crosstab(M.of_7, M.of_12))
print(m4.sort_values(['of_12', 'of_10', 'of_7'], ascending=False)[['player', 'side', 'line', 'game', 'of_7', 'of_10', 'of_12'] + xs + ['att_show', 'total_show']].to_string(index=False))
