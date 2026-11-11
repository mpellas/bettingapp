"""Paper-only CFB power ratings: time-decayed ridge regression on game margins (spread) and
points scored (offense/defense, totals). Data: CollegeFootballData.com /games (FBS+FCS+lower).
Margin capped (MOV_CAP) to limit blowout noise. Prior season games kept with decay (carryover)."""
import json, math, datetime as dt, numpy as np, os
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
P = dict(HFA=2.0, MOV_CAP=40, HALF_LIFE_DAYS=90, RIDGE=1.0, PRIOR_SEASONS=1, RIDGE_TOT=6.0)  # tuned on 2024 only (tune.py)
P4 = {'SEC', 'Big Ten', 'Big 12', 'ACC'}

def level(conf, cls, team=''):
    if cls == 'fbs':
        return 'P4' if conf in P4 or team == 'Notre Dame' else 'G5'
    return (cls or 'other').upper()

def load_games(years):
    out = []
    for y in years:
        f = f'{D}/games_{y}.json'
        if os.path.exists(f): out += json.load(open(f))
    for g in out: g['_t'] = dt.datetime.fromisoformat(g['startDate'].replace('Z', '+00:00'))
    return sorted(out, key=lambda g: g['_t'])

def fit(games, asof, p=P):
    """Fit ratings using only completed games strictly before `asof`."""
    gs = [g for g in games if g['completed'] and g['homePoints'] is not None and g['_t'] < asof
          and g['season'] >= asof.year - p['PRIOR_SEASONS'] - (1 if asof.month < 7 else 0)]
    teams = sorted({g['homeTeam'] for g in gs} | {g['awayTeam'] for g in gs})
    ix = {t: i for i, t in enumerate(teams)}; n = len(teams)
    if not gs: return None
    # margin model: m = r_h - r_a + HFA*(not neutral)
    w = np.array([0.5 ** ((asof - g['_t']).days / p['HALF_LIFE_DAYS']) for g in gs])
    X = np.zeros((len(gs), n)); y = np.zeros(len(gs)); hf = np.array([0 if g['neutralSite'] else 1 for g in gs])
    for k, g in enumerate(gs):
        X[k, ix[g['homeTeam']]] = 1; X[k, ix[g['awayTeam']]] = -1
        y[k] = max(-p['MOV_CAP'], min(p['MOV_CAP'], g['homePoints'] - g['awayPoints'])) - p['HFA'] * hf[k]
    A = X.T @ (X * w[:, None]) + p['RIDGE'] * np.eye(n); r = np.linalg.solve(A, X.T @ (w * y))
    # points model: pts = mu + off_t - def_o + hfa/2 (two rows per game)
    Z = np.zeros((2 * len(gs), 2 * n)); yp = np.zeros(2 * len(gs)); w2 = np.repeat(w, 2)
    for k, g in enumerate(gs):
        h, a = ix[g['homeTeam']], ix[g['awayTeam']]
        Z[2*k, h] = 1; Z[2*k, n + a] = 1; yp[2*k] = g['homePoints']
        Z[2*k+1, a] = 1; Z[2*k+1, n + h] = 1; yp[2*k+1] = g['awayPoints']
    mu = np.average(yp, weights=w2); yp = np.minimum(yp, 70) - mu
    B = Z.T @ (Z * w2[:, None]) + p['RIDGE_TOT'] * np.eye(2 * n); od = np.linalg.solve(B, Z.T @ (w2 * yp))
    ngames = {t: 0 for t in teams}
    for g in gs:
        if g['season'] == asof.year: ngames[g['homeTeam']] += 1; ngames[g['awayTeam']] += 1
    return dict(r={t: r[ix[t]] for t in teams}, off={t: od[ix[t]] for t in teams},
                dfn={t: od[n + ix[t]] for t in teams}, mu=mu, n=ngames, p=p)

def predict(m, home, away, neutral=False):
    """Returns (fair home spread in betting convention: negative = home favored, fair total) or None."""
    if m is None or home not in m['r'] or away not in m['r']: return None
    margin = m['r'][home] - m['r'][away] + (0 if neutral else m['p']['HFA'])
    tot = 2 * m['mu'] + m['off'][home] + m['dfn'][away] + m['off'][away] + m['dfn'][home]
    return -margin, tot
