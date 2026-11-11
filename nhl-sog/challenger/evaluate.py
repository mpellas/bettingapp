"""Stage B (walk-forward, seasons never used in selection) and Stage C (real DraftKings lines, Oct 11-16 2026).
B: for test season S in {2025-26, 2026-27 to date}: train on seasons < S (trees by early stopping on S-1 with a
   model trained on < S-1; k fit out-of-sample on S-1 predictions), compare
     champ_recipe  = champion features, champion recipe (k fit in-sample on training rows, as freeze.py does)
     champ_koos    = champion features, k out-of-sample
     challenger    = selection.json features, k out-of-sample
   on NB log-likelihood per row and on P(over) log-loss / Brier at the row's synthetic line L = floor(mu_champ)+0.5.
   Differences are paired, 95% CIs game-clustered (2000 bootstrap draws).
C: graded D lines (status OK) Oct 11-16 2026 vs DK no-vig: champion as logged (stale inputs), champion c3ab760178
   re-predicted on fresh as-of features (frozen booster, read-only), challenger trained through 2026-10-10.
   Log-loss / Brier of P(over at the DK line), lean hit vs market-implied, mean z-CLV of the lean side.
Writes challenger/evaluation.json and prints tables."""
from common import *
import glob
sel = json.load(open(os.path.join(HERE, 'selection.json'))); CH = sel['features']
DF = build(); df = DF[DF.n_prior >= 5]
def ll01(p, o): p = np.clip(p, 1e-6, 1 - 1e-6); return -(o * np.log(p) + (1 - o) * np.log(1 - p))
OUT = {'stageB': {}, 'stageC': {}}
def recipe(train_mask_outer, inner_val_season, feats):
    tr_all = df[train_mask_outer]; tr2 = tr_all[tr_all.season < inner_val_season]; va = tr_all[tr_all.season == inner_val_season]
    m2, it = fit(tr2, va, feats); k_oos = fit_k(va.shots.values, m2.predict(va[feats]))
    m, _ = fit(tr_all, None, feats, it); k_ins = fit_k(tr_all.shots.values, m.predict(tr_all[feats]))
    return m, it, k_oos, k_ins
for S in (2025, 2026):
    te = df[df.season == S]; y = te.shots.values; gid = te.gameId.values
    mc, itc, kc_oos, kc_ins = recipe(df.season < S, S - 1, CHAMP)
    mx, itx, kx_oos, _ = recipe(df.season < S, S - 1, CH)
    muc, mux = mc.predict(te[CHAMP]), mx.predict(te[CH])
    L = np.floor(muc) + 0.5; o = (y > L).astype(int)
    rows = {'champ_recipe': (muc, kc_ins), 'champ_koos': (muc, kc_oos), 'challenger': (mux, kx_oos)}
    res = {}
    for name, (mu, k) in rows.items():
        nll = -nb_ll(y, mu, k); p = p_over(L, mu, k)
        res[name] = dict(k=k, nb_nll=float(nll.mean()), logloss=float(ll01(p, o).mean()), brier=float(((p - o) ** 2).mean()), _nll=nll, _ll=ll01(p, o), _br=(p - o) ** 2)
    diffs = {}
    for a, b in (('challenger', 'champ_recipe'), ('challenger', 'champ_koos'), ('champ_koos', 'champ_recipe')):
        diffs[f'{a} - {b}'] = {met: boot_diff(res[a][f'_{met}'] - res[b][f'_{met}'], gid) for met in ('nll', 'll', 'br')}
    OUT['stageB'][S] = dict(rows=len(te), games=int(te.gameId.nunique()), trees=dict(champ=itc, challenger=itx),
                            models={n: {k: v for k, v in r.items() if not k.startswith('_')} for n, r in res.items()}, diffs=diffs)
    print(f'\n== Stage B test season {S}-{S+1-2000}: {len(te)} rows, {te.gameId.nunique()} games; trees champ {itc} challenger {itx}')
    for n, r in OUT['stageB'][S]['models'].items(): print(f'  {n:13s} k={r["k"]:.2f}  NB-NLL {r["nb_nll"]:.5f}  logloss {r["logloss"]:.5f}  brier {r["brier"]:.5f}')
    for n, d in diffs.items(): print(f'  {n:28s} ' + '  '.join(f'{met} {v[0]:+.5f} [{v[1]:+.5f},{v[2]:+.5f}]' for met, v in d.items()))
# ---- Stage C
G = pd.concat([pd.read_csv(f).assign(date=os.path.basename(f)[:8]) for f in sorted(glob.glob(os.path.join(ROOT, 'graded', '2026101[1-6].csv')))], ignore_index=True)
G = G[(G.status == 'OK') & G.actual.notna()].copy()
cut = pd.Timestamp('2026-10-10')
trc = df[df.date <= cut]
mx, itx, kx_oos, _ = recipe(df.date <= cut, 2025, CH)
champ = lgb.Booster(model_file=os.path.join(ROOT, 'models', 'model_c3ab760178.txt')); kch = json.load(open(os.path.join(ROOT, 'models', 'model_c3ab760178.json')))['k']
X = DF.set_index(['playerId', 'gameId']); key = list(zip(G.nhl_id, G.gameId))
miss = [k for k in key if k not in X.index]; assert not miss, miss[:5]
XR = X.loc[key]
G['p_champ_fresh'] = p_over(G.line.values, champ.predict(XR[CHAMP]), kch)
G['p_chal'] = p_over(G.line.values, mx.predict(XR[CH]), kx_oos)
o = (G.actual > G.line).astype(int).values; gid = G.gameId.values
lg = lambda p: np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
zc = lg(G.nv_over_C.values) - lg(G.nv_over.values)
C_ = {}
for name, col in (('market no-vig', 'nv_over'), ('champion as logged (stale)', 'p_model_over'), ('champion fresh inputs', 'p_champ_fresh'), ('challenger', 'p_chal')):
    p = G[col].values; r = dict(logloss=boot_diff(ll01(p, o), gid), brier=boot_diff((p - o) ** 2, gid))
    if col != 'nv_over':
        over = p > G.nv_over.values; hit = np.where(over, o, 1 - o); imp = np.where(over, G.nv_over, 1 - G.nv_over)
        r['logloss_minus_market'] = boot_diff(ll01(p, o) - ll01(G.nv_over.values, o), gid)
        r['lean_hit_minus_implied'] = boot_diff(hit - imp, gid); r['lean_hit'] = float(hit.mean()); r['implied'] = float(imp.mean())
        r['zclv_lean'] = boot_diff(np.where(over, zc, -zc), gid); r['n_over'] = int(over.sum())
    C_[name] = r
OUT['stageC'] = dict(rows=len(G), games=int(G.gameId.nunique()), challenger_trees=itx, challenger_k=kx_oos, models=C_)
print(f'\n== Stage C: {len(G)} DK lines, {G.gameId.nunique()} games (Oct 11-16 2026)')
for n, r in C_.items():
    s = f'  {n:28s} logloss {r["logloss"][0]:.4f}  brier {r["brier"][0]:.4f}'
    if 'zclv_lean' in r:
        s += (f'  LL-mkt {r["logloss_minus_market"][0]:+.4f} [{r["logloss_minus_market"][1]:+.4f},{r["logloss_minus_market"][2]:+.4f}]'
              f'  hit {r["lean_hit"]:.3f} vs {r["implied"]:.3f} [{r["lean_hit_minus_implied"][1]:+.3f},{r["lean_hit_minus_implied"][2]:+.3f}]'
              f'  zCLV {r["zclv_lean"][0]:+.4f} [{r["zclv_lean"][1]:+.4f},{r["zclv_lean"][2]:+.4f}]')
    print(s)
G.to_csv(os.path.join(HERE, 'stageC_rows.csv'), index=False)
json.dump(OUT, open(os.path.join(HERE, 'evaluation.json'), 'w'), indent=1, default=float)
