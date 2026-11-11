import os, sys, json, numpy as np, pandas as pd, lightgbm as lgb
from scipy import stats, optimize
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE); sys.path.insert(0, ROOT)
import features as F, cfeatures as C
P = dict(objective='poisson', learning_rate=0.03, num_leaves=15, min_data_in_leaf=200, feature_fraction=0.8,
         bagging_fraction=0.8, bagging_freq=1, verbose=-1, seed=7, num_threads=8)   # champion's params, unchanged
CHAMP = json.load(open(os.path.join(ROOT, 'models', 'model_c3ab760178.json')))['features']
def build():
    cwd = os.getcwd(); os.chdir(ROOT)
    try: df = C.add(F.feats(F.load()))
    finally: os.chdir(cwd)
    return df
def fit(tr, va, feats, rounds=None):
    if rounds is None:
        m = lgb.train(P, lgb.Dataset(tr[feats], tr.shots), 3000, valid_sets=[lgb.Dataset(va[feats], va.shots)],
                      callbacks=[lgb.early_stopping(100, verbose=False)])
        return m, m.best_iteration
    return lgb.train(P, lgb.Dataset(tr[feats], tr.shots), rounds), rounds
def nb_ll(y, mu, k):  # per-row log-likelihood; k scalar or array
    return stats.nbinom.logpmf(y, k, k / (k + mu))
def fit_k(y, mu, by=None):
    f = lambda yy, mm: optimize.minimize_scalar(lambda k: -nb_ll(yy, mm, k).mean(), bounds=(0.5, 300), method='bounded').x
    if by is None: return float(f(y, mu))
    return {int(b): float(f(y[by == b], mu[by == b])) for b in np.unique(by)}
def karr(kk, by):
    return np.array([kk[int(b)] for b in by]) if isinstance(kk, dict) else np.full(len(by), kk)
def p_over(L, mu, k):
    return 1 - stats.nbinom.cdf(np.floor(L), k, k / (k + mu))
def boot_diff(d, games, B=2000, seed=0):
    """mean of per-row d with a game-clustered bootstrap 95% CI."""
    s = pd.DataFrame(dict(d=d, g=games)).groupby('g').d.agg(['sum', 'count'])
    rng = np.random.default_rng(seed); n = len(s); S, N = s['sum'].values, s['count'].values
    idx = rng.integers(0, n, (B, n)); m = S[idx].sum(1) / N[idx].sum(1)
    return float(d.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)), int(len(d)), int(n)
