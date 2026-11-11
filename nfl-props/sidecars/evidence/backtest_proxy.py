"""PROXY backtest of the NFL evidence block on 2024 and 2025 (no usable real prop prices: 2024 has none, 2025 has only
ESPN BET lines of uncertain timing which the prereg keeps out of any re-scoring, so they are NOT used here).
Reference = champion recipe walk-forward predictions (2024: aa4d70b859; 2025: 557e6ab3e4, same model config, the
frozen-holdout run). P_champ(over L) from the model's own standardized residuals pooled on earlier seasons.
Synthetic line L = floor(mkt_proj) + 0.5 (the pipeline's public-projection proxy, not a market). Side = champion lean,
candidate if |P - 0.5| >= 1 pt. Five market-free signals: usage, opp, injury, script, weather (champ is + by
construction; move needs line history). Ex-ante gate analogue of 'K=4 of 7': >= 3 of these 5 agree.
Question: is hit - P_champ(side) higher when more signals agree? Game-clustered bootstrap 95% CIs."""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE); import nfl_evidence as E
P = os.path.join(ROOT, 'data', 'cache', 'preds')
RUNS = {2024: ('aa4d70b859_6ddb05f9_f78fc34e', range(2019, 2024)), 2025: ('557e6ab3e4_f9247893', range(2019, 2025))}
boot = E.boot
D = E.load(max_age_h=1e9); G = D['games'].set_index('game_id'); rows = []
for S, (h, zs) in RUNS.items():
    te = pd.read_parquet(f'{P}/preds_{h}_{S}.parquet')
    hist = pd.concat([pd.read_parquet(f'{P}/preds_{h}_{s}.parquet') for s in zs])
    Z = {mk: np.sort(((g.actual - g.mu) / g.s).dropna().values) for mk, g in hist.groupby('market')}
    te = te[te.mkt_proj.notna() & te.actual.notna()].copy(); te['L'] = np.floor(te.mkt_proj) + 0.5
    te['p_over'] = [1 - np.searchsorted(Z[m], (L - mu) / s, 'right') / len(Z[m]) for m, L, mu, s in zip(te.market, te.L, te.mu, te.s)]
    for r in te.itertuples():
        g = G.loc[r.game_id]; ov = r.p_over >= 0.5; ps = r.p_over if ov else 1 - r.p_over
        if ps - 0.5 < 0.01 or r.actual == r.L: continue
        sig = E.over_signals(D, r.player_id, r.market, r.position, r.team, r.opponent, S, r.week, g.home_team, g.away_team,
                             g.spread_line, g.total_line, g.roof, g.temp, g.wind)
        s = 1 if ov else -1; v = {k: sig[k][0] * s for k in ('usage', 'opp', 'injury', 'script', 'weather')}
        rows.append(dict(season=S, week=r.week, game_id=r.game_id, player_id=r.player_id, market=r.market, side='over' if ov else 'under',
                         L=r.L, p_side=ps, hit=int((r.actual > r.L) == ov), **{f's_{k}': x for k, x in v.items()},
                         agree=sum(x > 0 for x in v.values()), against=sum(x < 0 for x in v.values())))
X = pd.DataFrame(rows); X['res'] = X.hit - X.p_side
X.to_csv(os.path.join(HERE, 'backtest_proxy_rows.csv'), index=False)
f = lambda t: f'{t[0]*100:+.1f} [{t[1]*100:+.1f}, {t[2]*100:+.1f}]'
print(f'PROXY 2024-2025: {len(X)} candidate sides, {X.game_id.nunique()} games; overs {(X.side=="over").mean():.0%}; '
      f'by market {X.market.value_counts().to_dict()}')
print('| agreeing (of 5 market-free) | n | games | hit | champion P(side) | hit - P (pts) | overs |'); print('|---|---|---|---|---|---|---|')
for a in range(6):
    s = X[X.agree == a]
    if len(s) < 40: print(f'| {a} | {len(s)} | | too few | | | |'); continue
    print(f'| {a} | {len(s)} | {s.game_id.nunique()} | {s.hit.mean():.3f} | {s.p_side.mean():.3f} | {f(boot(s.res.values, s.game_id.values))} | {(s.side=="over").mean():.0%} |')
for lab, s in [('>= 3 agree (ex-ante gate)', X[X.agree >= 3]), ('< 3 agree', X[X.agree < 3]), ('all candidates', X)]:
    print(f'| {lab} | {len(s)} | {s.game_id.nunique()} | {s.hit.mean():.3f} | {s.p_side.mean():.3f} | {f(boot(s.res.values, s.game_id.values))} | {(s.side=="over").mean():.0%} |')
print('\nby season / market / side, >=3 agree minus <3 agree (hit - P, pts):')
for keys in (['season'], ['market'], ['side']):
    for k, g in X.groupby(keys):
        a, b = g[g.agree >= 3], g[g.agree < 3]
        if len(a) > 20 and len(b) > 20:
            print(f'  {keys[0]}={k if not isinstance(k, tuple) else k[0]}: >=3 n={len(a)} {f(boot(a.res.values, a.game_id.values))} | <3 n={len(b)} {f(boot(b.res.values, b.game_id.values))}')
print('\nper signal (hit - P when + / 0 / -):')
for k in ('usage', 'opp', 'injury', 'script', 'weather'):
    out = []
    for v, c in ((1, '+'), (0, '0'), (-1, '-')):
        s = X[X[f's_{k}'] == v]; out.append(f'{c} n={len(s)} ' + (f(boot(s.res.values, s.game_id.values)) if len(s) >= 40 else 'too few'))
    print(f'  {k:8s} ' + ' | '.join(out))
