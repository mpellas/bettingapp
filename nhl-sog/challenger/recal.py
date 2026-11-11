"""RECALIBRATED-CHAMPION challenger candidate (2026-10-17). Stage 2 on top of stage-1 LightGBM means; the evidence
'agreement' signals enter as continuous features, not a vote.
  stage 1 : champion recipe (champion features) -> mu_c; challenger 3386583f18 recipe (selection.json) -> mu_x
  stage 2 : NB mean  log mu = b0 + b1 log mu_c + b2 (log mu_x - log mu_c) + b3 (log shr_mu - log mu_c)
                              + b4 toi_trend + b5 log opp_slot_ratio_r20 + b6 D + b7 D*log mu_c
            fit by Poisson maximum likelihood on season S-1 rows predicted OUT OF SAMPLE by stage-1 models trained on
            seasons < S-1; NB k fit on those same held-out rows (stage-1 predictions are held-out; stage 2 has 8 params
            on ~45k rows).
  test    : stage 1 retrained on seasons < S exactly as challenger/evaluate.py does (inner early stopping on S-1),
            stage-2 coefficients and k from S-1 applied unchanged to season S.
Test seasons 2025-26 and 2026-27 to date (same as 3386583f18's Stage B). Metrics: NB NLL per row, log-loss / Brier at
L = floor(mu_champ) + 0.5; paired game-clustered 95% CIs vs challenger 3386583f18 (k out-of-sample) and vs champion recipe.
FREEZE RULE (stated before running): freeze only if recal beats 3386583f18 on NB NLL AND log-loss with the 95% CI
upper bound < 0 in BOTH test seasons. Otherwise no freeze and no second shadow track."""
from common import *
from scipy import optimize
sel = json.load(open(os.path.join(HERE, 'selection.json'))); CH = sel['features']
DF = build(); df = DF[DF.n_prior >= 5]
def ll01(p, o): p = np.clip(p, 1e-6, 1 - 1e-6); return -(o * np.log(p) + (1 - o) * np.log(1 - p))
def recipe(cut, feats):
    tr_all = df[df.season < cut]; tr2 = tr_all[tr_all.season < cut - 1]; va = tr_all[tr_all.season == cut - 1]
    m2, it = fit(tr2, va, feats); k_oos = fit_k(va.shots.values, m2.predict(va[feats]))
    m, _ = fit(tr_all, None, feats, it); k_ins = fit_k(tr_all.shots.values, m.predict(tr_all[feats]))
    return m, k_oos, k_ins
def design(t, muc, mux):
    lc = np.log(muc); D_ = t.D.values.astype(float)
    shr = t.shr_mu.fillna(pd.Series(muc, index=t.index)).clip(lower=0.05).values
    return np.column_stack([np.ones(len(t)), lc, np.log(mux) - lc, np.log(shr) - lc, t.toi_trend.fillna(0).clip(-8, 8).values,
                            np.log(t.opp_slot_ratio_r20.fillna(1).clip(0.5, 2)).values, D_, D_ * lc])
def fit_glm(X, y):
    f = lambda b: (np.exp(X @ b) - y * (X @ b)).mean()
    g = lambda b: X.T @ (np.exp(X @ b) - y) / len(y)
    b0 = np.zeros(X.shape[1]); b0[1] = 1
    return optimize.minimize(f, b0, jac=g, method='L-BFGS-B').x
NAMES = ['b0', 'log mu_c', 'chal-champ', 'shrunk-champ', 'toi_trend', 'log opp_slot', 'D', 'D*log mu_c']
OUT = {}; M = {}
for cut in (2024, 2025, 2026):
    M[cut] = {n: recipe(cut, f) for n, f in (('c', CHAMP), ('x', CH))}; print('stage-1 fitted for cut', cut, flush=True)
for S in (2025, 2026):
    va = df[df.season == S - 1]; mc_, kc_, _ = M[S - 1]['c']; mx_, kx_, _ = M[S - 1]['x']
    Xv = design(va, mc_.predict(va[CHAMP]), mx_.predict(va[CH])); b = fit_glm(Xv, va.shots.values)
    k2 = fit_k(va.shots.values, np.exp(Xv @ b))
    te = df[df.season == S]; y = te.shots.values; gid = te.gameId.values
    (mc, kc_oos, kc_ins), (mx, kx_oos, _) = M[S]['c'], M[S]['x']
    muc, mux = mc.predict(te[CHAMP]), mx.predict(te[CH]); mur = np.exp(design(te, muc, mux) @ b)
    L = np.floor(muc) + 0.5; o = (y > L).astype(int)
    res = {}
    for name, (mu, k) in {'champ_recipe': (muc, kc_ins), 'challenger_3386583f18': (mux, kx_oos), 'recal': (mur, k2)}.items():
        nll = -nb_ll(y, mu, k); p = p_over(L, mu, k)
        res[name] = dict(k=float(k), nb_nll=float(nll.mean()), logloss=float(ll01(p, o).mean()), brier=float(((p - o) ** 2).mean()),
                         _nll=nll, _ll=ll01(p, o), _br=(p - o) ** 2)
    diffs = {f'recal - {b_}': {met: boot_diff(res['recal'][f'_{met}'] - res[b_][f'_{met}'], gid) for met in ('nll', 'll', 'br')}
             for b_ in ('challenger_3386583f18', 'champ_recipe')}
    OUT[S] = dict(rows=len(te), games=int(te.gameId.nunique()), coef=dict(zip(NAMES, map(float, b))), k_recal=float(k2),
                  models={n: {k: v for k, v in r.items() if not k.startswith('_')} for n, r in res.items()}, diffs=diffs)
    print(f'\n== test season {S}-{S+1-2000}: {len(te)} rows, {te.gameId.nunique()} games; stage-2 fit on {len(va)} held-out {S-1} rows')
    print('  coef ' + ', '.join(f'{n} {v:+.3f}' for n, v in zip(NAMES, b)) + f'; k {k2:.2f}')
    for n, r in OUT[S]['models'].items(): print(f'  {n:22s} k={r["k"]:.2f}  NB-NLL {r["nb_nll"]:.5f}  logloss {r["logloss"]:.5f}  brier {r["brier"]:.5f}')
    for n, d in diffs.items(): print(f'  {n:34s} ' + '  '.join(f'{met} {v[0]:+.5f} [{v[1]:+.5f},{v[2]:+.5f}]' for met, v in d.items()))
ok = all(OUT[S]['diffs']['recal - challenger_3386583f18'][m][2] < 0 for S in (2025, 2026) for m in ('nll', 'll'))
OUT['freeze_rule_met'] = bool(ok); print('\nFREEZE RULE MET:', ok)
json.dump(OUT, open(os.path.join(HERE, 'recal_evaluation.json'), 'w'), indent=1, default=float)
