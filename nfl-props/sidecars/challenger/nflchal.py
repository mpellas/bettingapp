"""NFL challenger: RECALIBRATED champion + pre-game context (sidecar; pinned code and prereg untouched).
Base: champion aa4d70b859 predictive mean mu and scale s (pregame.py output live; walk-forward cache files in training -
557e6ab3e4 files are byte-identical in mu/s to aa4d70b859, verified 2024: max |diff| 0).
Stage 2, per market (pass_yds, rush_yds, rec_yds): standardized residual z = (y - mu)/s regressed (ridge) on
  itt_dev   implied team total from the OPENING spread/total minus 22.5 (ESPN core odds 'open'; never close/current)
  fav       points the team is favoured by at the open (clipped +/-14)
  unit_out  meaningful same-unit teammates Out/Doubtful on the nflverse weekly report (pass: WR/TE; rec: WR/TE or RB unit;
            rush: RB), clipped 0-3; meaningful = snap >= 50% last 3 or top-3 targets / top-2 carries (as-of, prior games)
  qb_out    team's starting QB (most attempts so far) Out/Doubtful (rec, rush)
  self_q, self_d   the player himself Questionable / Doubtful
  wind_x    max(forecast wind mph - 10, 0) outdoors; cold = max(45 - forecast temp F, 0)/10; precip = forecast mm in the
            3 h from kickoff (Open-Meteo historical-forecast archive in training, live forecast in shadow); 0 indoors/missing
mu' = mu + s * zhat; P(over L) = 1 - F((L - mu')/s), F = empirical CDF of the training residuals z - zhat (this also
recalibrates the champion's scale and skew). 'recal_only' = intercept-only version (no context features)."""
import os, sys, json, hashlib
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); EV = os.path.abspath(os.path.join(HERE, '..', 'evidence'))
sys.path.insert(0, EV); import nfl_evidence as E
CACHE = os.path.join(EV, 'cache')
FEATS = ['itt_dev', 'fav', 'unit_out', 'qb_out', 'self_q', 'self_d', 'wind_x', 'cold', 'precip']
LAMBDA = 30.0   # ridge strength in units of rows (features are standardized on the training set)

def context(rows, D, odds=None, wx=None):
    """rows: season, week, game_id, player_id, team, position, market. odds: {game_id: (open_home_fav, open_total)};
    wx: {game_id: (wind, temp, precip)}. Defaults read the cached historical files."""
    G = D['games'].set_index('game_id')
    if odds is None:
        O = pd.read_csv(os.path.join(CACHE, 'open_lines.csv'), dtype={'espn': str}); e2g = dict(zip(G.espn.astype('Int64').astype(str), G.index))
        odds = {e2g.get(r.espn): (r.open_home_fav, r.open_total) for r in O.itertuples()}
    if wx is None:
        W = pd.read_csv(os.path.join(CACHE, 'wx_fc.csv')); wx = {r.game_id: (r.wind_fc, r.temp_fc, r.precip_fc) for r in W.itertuples()}
    if 'inj_by' not in D:
        D['inj_by'] = {k: {r.gsis_id: str(r.report_status or '') for r in g.itertuples()} for k, g in D['inj'].groupby(['season', 'week', 'team'])}
    out = []
    for r in rows.itertuples():
        g = G.loc[r.game_id]; home = r.team == g.home_team
        hf, tot = odds.get(r.game_id, (np.nan, np.nan))
        fav = (hf if home else -hf) if pd.notna(hf) else np.nan
        itt = (tot + fav) / 2 if pd.notna(tot) and pd.notna(fav) else np.nan
        st = D['inj_by'].get((r.season, r.week, r.team), {}); m, qb = E._meaningful(D, r.team, r.season, r.week)
        outp = {p for p, s in st.items() if s.lower() in ('out', 'doubtful') and p != r.player_id}
        unit = {'pass_yds': ('WR', 'TE'), 'rec_yds': ('WR', 'TE') if r.position in ('WR', 'TE') else ('RB',), 'rush_yds': ('RB',)}[r.market]
        uo = sum(1 for p in outp if p in m and m[p][0] in unit)
        me = st.get(r.player_id, '').lower()
        w, t, pr = wx.get(r.game_id, (np.nan, np.nan, np.nan))
        outdoor = isinstance(g.roof, str) and g.roof in ('outdoors', 'open')
        out.append(dict(itt_dev=(itt - 22.5) if pd.notna(itt) else 0.0, fav=float(np.clip(fav, -14, 14)) if pd.notna(fav) else 0.0,
                        unit_out=min(uo, 3), qb_out=int(r.market != 'pass_yds' and qb in outp), self_q=int(me == 'questionable'),
                        self_d=int(me == 'doubtful'), wind_x=max(w - 10, 0) if outdoor and pd.notna(w) else 0.0,
                        cold=max(45 - t, 0) / 10 if outdoor and pd.notna(t) else 0.0, precip=min(pr, 5) if outdoor and pd.notna(pr) else 0.0,
                        has_open=int(pd.notna(itt)), has_wx=int(outdoor and pd.notna(w))))
    return pd.concat([rows.reset_index(drop=True), pd.DataFrame(out)], axis=1)

def fit(X, feats=FEATS, lam=LAMBDA):
    P = {'feats': feats, 'lambda': lam, 'markets': {}}
    for mk, g in X.groupby('market'):
        z = ((g.actual - g.mu) / g.s).values; A = g[feats].values.astype(float) if feats else np.zeros((len(g), 0))
        mu_, sd_ = A.mean(0) if feats else [], (A.std(0) + 1e-9) if feats else []
        Az = np.column_stack([np.ones(len(g)), (A - mu_) / sd_]) if feats else np.ones((len(g), 1))
        R = np.eye(Az.shape[1]) * lam; R[0, 0] = 0
        b = np.linalg.solve(Az.T @ Az + R, Az.T @ z); res = z - Az @ b
        P['markets'][mk] = dict(b=b.tolist(), mean=list(map(float, mu_)), sd=list(map(float, sd_)), n=int(len(g)),
                                res_q=np.quantile(res, np.linspace(0, 1, 2001)).tolist())
    return P

def predict(P, X, line_col='L'):
    mu2, p = np.full(len(X), np.nan), np.full(len(X), np.nan)
    for mk, g in X.groupby('market'):
        q = P['markets'].get(mk)
        if q is None: continue
        f = P['feats']; A = g[f].values.astype(float) if f else np.zeros((len(g), 0))
        Az = np.column_stack([np.ones(len(g)), (A - np.array(q['mean'])) / np.array(q['sd'])]) if f else np.ones((len(g), 1))
        zh = Az @ np.array(q['b']); m2 = g.mu.values + g.s.values * zh; idx = X.index.get_indexer(g.index)
        mu2[idx] = m2
        if line_col in g:
            u = (g[line_col].values - m2) / g.s.values; Q = np.array(q['res_q'])
            p[idx] = 1 - np.interp(u, Q, np.linspace(0, 1, len(Q)), left=0, right=1)
    return mu2, p

def champ_p(Zs, X, line_col='L'):
    """champion: P(over) from its own standardized residuals (pooled earlier seasons), no shift."""
    p = np.full(len(X), np.nan)
    for mk, g in X.groupby('market'):
        Z = Zs[mk]; u = (g[line_col].values - g.mu.values) / g.s.values
        p[X.index.get_indexer(g.index)] = 1 - np.searchsorted(Z, u, 'right') / len(Z)
    return p

def sha(P): return hashlib.sha256(json.dumps(P, sort_keys=True).encode()).hexdigest()[:10]
