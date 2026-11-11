"""Walk-forward test of the NFL challenger (train on 2024, test on 2025: the only seasons with ESPN opening lines;
weather forecasts exist 2022+). Champion = aa4d70b859-recipe walk-forward predictions (557e6ab3e4 cache files, identical).
Metrics on 2025 (paired, game-clustered 95% CIs, 2000 draws):
  log-loss at the REAL 2025 ESPN BET lines (uncertain timing, ~99% last-updated after kickoff -> treat as close-ish)
  log-loss at the synthetic line floor(mkt_proj)+0.5 (public-projection proxy, all rows), MAE of the mean
Models: champion (own residual CDF from 2019-2024), recal_only (intercept + residual CDF refit on 2024),
        challenger (recal + context features, fit on 2024).
FREEZE RULE (stated before running): freeze as a SHADOW challenger if, on 2025, challenger minus champion log-loss at
the real lines has point estimate <= 0 AND the CI upper bound on synthetic-line log-loss is < +0.002 (no material harm).
Shadow scoring is only on weeks after the freeze; the walk-forward is not evidence of a betting edge."""
import os, sys, json, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE); import nflchal as N; E = N.E
PR = os.path.join(ROOT, 'data', 'cache', 'preds'); H = '557e6ab3e4_f9247893'
D = E.load(seasons=(2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026), max_age_h=1e9)
def rows(S):
    # 2025: the cfe6d96714 cache file has the same mu/s (verified max |diff| 0) and the REAL ESPN BET lines (line_source csv);
    # the 557e6ab3e4_f9247893 2025 file carries SIMULATED lines and must not be used for line metrics.
    f = f'{PR}/preds_cfe6d96714_6ddb05f9_f78fc34e_2025.parquet' if S == 2025 else f'{PR}/preds_{H}_{S}.parquet'
    p = pd.read_parquet(f); p = p[p.actual.notna()].copy()
    if S != 2025: p['line'] = np.nan
    else: assert (p.line_source == 'csv').all() and not p.line_simulated.any()
    p['L'] = np.floor(p.mkt_proj) + 0.5; return p.reset_index(drop=True)
tr, te = N.context(rows(2024), D), N.context(rows(2025), D)
print(f'train 2024: {len(tr)} rows, open lines on {tr.has_open.mean():.0%}, weather fc on {tr.has_wx.mean():.0%} | test 2025: {len(te)} rows, open {te.has_open.mean():.0%}, wx {te.has_wx.mean():.0%}')
Zs = {mk: np.sort(np.concatenate([((g.actual - g.mu) / g.s).values for g in [rows(s)[lambda x: x.market == mk] for s in range(2019, 2025)]])) for mk in ('pass_yds', 'rush_yds', 'rec_yds')}
Pc, P0 = N.fit(tr), N.fit(tr, feats=[])
def ll(p, o): p = np.clip(p, 1e-4, 1 - 1e-4); return -(o * np.log(p) + (1 - o) * np.log(1 - p))
R = {}
for lab, col in (('synthetic', 'L'), ('real2025', 'line')):
    t = te[te[col].notna() & (te.actual != te[col])].copy(); o = (t.actual > t[col]).astype(int).values
    pc = N.champ_p(Zs, t, col); _, p0 = N.predict(P0, t, col); m2, px = N.predict(Pc, t, col)
    R[lab] = dict(n=len(t), games=int(t.game_id.nunique()), ll_champ=ll(pc, o).mean(), ll_recal=ll(p0, o).mean(), ll_chal=ll(px, o).mean(),
                  d_chal=E.boot(ll(px, o) - ll(pc, o), t.game_id.values), d_recal=E.boot(ll(p0, o) - ll(pc, o), t.game_id.values),
                  d_chal_recal=E.boot(ll(px, o) - ll(p0, o), t.game_id.values))
    if lab == 'synthetic':
        mae_c, mae_x = np.abs(t.actual - t.mu).values, np.abs(t.actual - m2).values
        R[lab]['mae'] = (mae_c.mean(), mae_x.mean(), E.boot(mae_x - mae_c, t.game_id.values))
        for mk, g in t.groupby('market'):
            i = t.index.get_indexer(g.index); R[lab][mk] = E.boot((ll(px, o) - ll(pc, o))[i], g.game_id.values)
fz = lambda t: f'{t[0]:+.4f} [{t[1]:+.4f}, {t[2]:+.4f}]'
print('| 2025 test | lines | games | log-loss champion | recal only | challenger | challenger - champion | recal - champion | challenger - recal |')
print('|---|---|---|---|---|---|---|---|---|')
for lab, r in R.items():
    print(f"| {lab} | {r['n']} | {r['games']} | {r['ll_champ']:.4f} | {r['ll_recal']:.4f} | {r['ll_chal']:.4f} | {fz(r['d_chal'])} | {fz(r['d_recal'])} | {fz(r['d_chal_recal'])} |")
m = R['synthetic']['mae']; print(f"MAE of mean (synthetic rows): champion {m[0]:.2f}, challenger {m[1]:.2f}, diff {fz(m[2])}")
print('per market (synthetic, challenger - champion log-loss):', {mk: fz(R['synthetic'][mk]) for mk in ('pass_yds', 'rush_yds', 'rec_yds')})
print('2024-fit coefficients (standardized):')
for mk, q in Pc['markets'].items(): print(f'  {mk} n={q["n"]}: ' + ', '.join(f'{n} {b:+.3f}' for n, b in zip(['int'] + N.FEATS, q['b'])))
ok = R['real2025']['d_chal'][0] <= 0 and R['synthetic']['d_chal'][2] < 0.002
print('FREEZE RULE MET:', ok)
json.dump(dict(R={k: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in v.items()} for k, v in R.items()}, freeze_rule_met=bool(ok)),
          open(os.path.join(HERE, 'walkforward.json'), 'w'), indent=1, default=float)
