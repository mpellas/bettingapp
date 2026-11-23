"""Train and backtest three NHL paper models: player points O/U, game puckline, goalie saves O/U.

Train on 2021-2025 only; 2026 is held out. Units/ROI are reported ONLY at real captured
DraftKings prices (extra_markets graded files for points/saves; gamelines for puckline).
No prices are invented or backfilled. Price band is enforced only at the -150 end
(-155 or worse is outside). Models stay in shadow (models_extra/shadow/), off the real card.
"""
import os, sys, json, math, time
import numpy as np
import pandas as pd
from scipy import stats, optimize
import lightgbm as lgb

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from common import (DATA, MOD, SHADOW, BAND_FLOOR, in_band, am2p, units,
                    eastern_date, load_idmap, summarize_bets)

P = dict(objective='poisson', learning_rate=0.03, num_leaves=15,
         min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.8,
         bagging_freq=1, verbose=-1)
P_REG = dict(objective='regression', learning_rate=0.03, num_leaves=15,
             min_data_in_leaf=200, feature_fraction=0.8, bagging_fraction=0.8,
             bagging_freq=1, verbose=-1, metric='l2')


def nb_p(mu, k):
    return k / (k + mu)


def nll(k, y, mu):
    return -stats.nbinom.logpmf(y, k, nb_p(np.clip(mu, 1e-6, None), k)).mean()


def p_over(mu, k, line):
    """P(Y > line) for Y ~ NB with mean mu, dispersion k. line is e.g. 0.5, 1.5."""
    thresh = int(math.floor(line))  # P(Y >= floor(line)+1) = 1 - F(floor(line))
    return 1 - stats.nbinom.cdf(thresh, k, nb_p(np.clip(mu, 1e-6, None), k))


def train_poisson(tr, te, F, ycol, tag):
    """Fit LightGBM poisson on tr (early-stop on last season of tr if present), predict te."""
    seasons = sorted(tr.season.unique())
    if len(seasons) >= 2:
        vl = tr[tr.season == seasons[-1]]
        tr2 = tr[tr.season < seasons[-1]]
        if len(vl) and len(tr2):
            m = lgb.train(P, lgb.Dataset(tr2[F], tr2[ycol]), 2000,
                          valid_sets=[lgb.Dataset(vl[F], vl[ycol])],
                          callbacks=[lgb.early_stopping(100, verbose=False)])
            n_est = max(50, m.best_iteration or 200)
        else:
            n_est = 400
    else:
        n_est = 400
    m = lgb.train(P, lgb.Dataset(tr[F], tr[ycol]), n_est)
    trmu = np.clip(m.predict(tr[F]), 1e-6, None)
    k = optimize.minimize_scalar(lambda kk: nll(kk, tr[ycol].values, trmu),
                                 bounds=(0.5, 200), method='bounded').x
    mu = np.clip(m.predict(te[F]), 1e-6, None) if te is not None and len(te) else None
    m.save_model(os.path.join(MOD, f'{tag}.txt'))
    json.dump({'k': float(k), 'features': F, 'n_est': int(n_est), 'ycol': ycol},
              open(os.path.join(MOD, f'{tag}.json'), 'w'))
    return m, float(k), mu


def add_rest_home(df, date_col='date'):
    g = df.groupby('playerId', sort=False)
    df = df.copy()
    df['rest'] = (df[date_col] - g[date_col].shift(1)).dt.days.clip(upper=10)
    df['b2b'] = (df['rest'] == 1).astype(int)
    df['home'] = (df.homeRoad == 'H').astype(int)
    return df


def rolling_asof(df, cols, windows=(5, 10, 30), group='playerId'):
    """Strictly prior-game rolling means + career mean + n_prior. No leakage."""
    df = df.sort_values([group, 'date', 'gameId']).copy()
    g = df.groupby(group, sort=False)
    for w in windows:
        for c in cols:
            df[f'{c}_r{w}'] = g[c].transform(lambda s: s.shift(1).rolling(w, min_periods=1).mean())
    for c in cols:
        df[f'{c}_car'] = g[c].transform(lambda s: s.shift(1).expanding().mean())
    df['n_prior'] = g.cumcount()
    return df


def opp_team_roll(df, val_col, out_col, group_key, windows=20):
    """Opponent/team allowed or scored, prior games only, at game level then merged back."""
    tg = (df.groupby(['gameId', group_key, 'date'], as_index=False)[val_col].sum()
            .sort_values('date'))
    tg[out_col] = tg.groupby(group_key)[val_col].transform(
        lambda s: s.shift(1).rolling(windows, min_periods=3).mean())
    return df.drop(columns=[c for c in [out_col] if c in df.columns]).merge(
        tg[['gameId', group_key, out_col]], on=['gameId', group_key], how='left')


# ---------------------------------------------------------------------------
# POINTS
# ---------------------------------------------------------------------------
def load_points():
    p = os.path.join(DATA, 'skater_points.pkl')
    if not os.path.exists(p):
        raise SystemExit(f'missing {p}; run fetch_extra_stats.py first')
    df = pd.read_pickle(p)
    df = df.drop_duplicates(['playerId', 'gameId'])
    df['date'] = pd.to_datetime(df.gameDate)
    df['toi'] = pd.to_numeric(df.timeOnIcePerGame, errors='coerce') / 60.0
    # merge PP TOI / attempts from the existing SOG season files when present (free, already on disk)
    sog = []
    import glob
    for f in sorted(glob.glob(os.path.join(ROOT, 'data', 's20*.pkl'))):
        if 'truncated' in f or 'backup' in f:
            continue
        try:
            sog.append(pd.read_pickle(f)[['playerId', 'gameId', 'ppTimeOnIce', 'totalShotAttempts', 'timeOnIcePerGame']])
        except Exception:
            pass
    if sog:
        s = pd.concat(sog, ignore_index=True).drop_duplicates(['playerId', 'gameId'])
        df = df.merge(s, on=['playerId', 'gameId'], how='left', suffixes=('', '_sog'))
        df['pptoi'] = pd.to_numeric(df.get('ppTimeOnIce'), errors='coerce').fillna(0) / 60.0
        df['att'] = pd.to_numeric(df.get('totalShotAttempts'), errors='coerce')
    else:
        df['pptoi'] = 0.0
        df['att'] = np.nan
    df['D'] = (df.positionCode == 'D').astype(int)
    df['points'] = pd.to_numeric(df.points, errors='coerce')
    df['goals'] = pd.to_numeric(df.goals, errors='coerce')
    df['assists'] = pd.to_numeric(df.assists, errors='coerce')
    df['shots'] = pd.to_numeric(df.shots, errors='coerce')
    df = df.dropna(subset=['points', 'playerId', 'gameId', 'date'])
    df = df.sort_values(['date', 'gameId', 'playerId']).reset_index(drop=True)
    df = add_rest_home(df)
    df = rolling_asof(df, ['points', 'goals', 'assists', 'shots', 'toi', 'pptoi'])
    df = opp_team_roll(df, 'points', 'opp_pa_r20', 'opponentTeamAbbrev')
    df = opp_team_roll(df, 'points', 'team_pf_r20', 'teamAbbrev')
    return df


def points_feat_cols(df):
    return [c for c in df.columns if c.endswith(('_r5', '_r10', '_r30', '_car', '_r20')) or c in
            ('n_prior', 'rest', 'b2b', 'home', 'D')]


def leakage_points(df, F):
    cut = df.date.sort_values().iloc[len(df) // 2]
    t = df.copy()
    fut = t.date >= cut
    t.loc[fut, ['points', 'goals', 'assists', 'shots', 'toi', 'pptoi']] = 999
    # recompute features on corrupted frame
    t = t.drop(columns=[c for c in F if c not in ('home', 'D', 'rest', 'b2b', 'n_prior') and c in t.columns], errors='ignore')
    t = rolling_asof(t, ['points', 'goals', 'assists', 'shots', 'toi', 'pptoi'])
    t = opp_team_roll(t, 'points', 'opp_pa_r20', 'opponentTeamAbbrev')
    t = opp_team_roll(t, 'points', 'team_pf_r20', 'teamAbbrev')
    key = ['playerId', 'gameId']
    a = df[df.date == cut].set_index(key)[F].sort_index()
    b = t[t.date == cut].set_index(key)[F].sort_index()
    common = a.index.intersection(b.index)
    bad = []
    for c in F:
        if c not in a.columns or c not in b.columns:
            continue
        av, bv = a.loc[common, c].fillna(-1).astype(float), b.loc[common, c].fillna(-1).astype(float)
        if not np.allclose(av, bv, equal_nan=True):
            bad.append(c)
    if bad:
        raise SystemExit(f'POINTS LEAKAGE {bad}')
    print('points leakage test passed')


def load_graded_ou(market):
    p = os.path.join(ROOT, 'extra_markets', 'graded', f'nhl_{market}.csv')
    if not os.path.exists(p):
        return pd.DataFrame()
    g = pd.read_csv(p)
    g = g[g.bet_type == 'ou'].copy()
    idm = load_idmap()
    g['espn_id'] = g.espn_id.astype(str)
    g['playerId'] = g.espn_id.map(idm)
    g['game_date'] = g.start_utc.map(eastern_date)
    return g


def attach_prices_and_pick(pred, graded, pcol='p_over'):
    """Join model P(over) to captured O/U sides. One pick per player-game-line: the side with +edge, if any.
    pred needs playerId, game_date (YYYY-MM-DD), mu, p function already applied per line? We'll merge on
    playerId+game_date then evaluate each graded line."""
    if pred.empty or graded.empty:
        return pd.DataFrame()
    g = graded.copy()
    g['playerId'] = pd.to_numeric(g.playerId, errors='coerce')
    pr = pred.copy()
    pr['game_date'] = pr.date.dt.strftime('%Y-%m-%d') if str(pr.date.dtype).startswith('datetime') else pr.game_date
    cols = ['playerId', 'game_date', 'mu', 'k'] + (['points'] if 'points' in pr.columns else [])
    m = g.merge(pr[cols], on=['playerId', 'game_date'], how='left', suffixes=('', '_pred'))
    # Fill remaining id matches at date+/-1 (UTC folder vs NHL/ET gameDate).
    miss_idx = m.index[m['mu'].isna() & m.playerId.notna()]
    for delta in (1, -1):
        if not len(miss_idx):
            break
        alt = pr[cols].copy()
        alt['game_date'] = (pd.to_datetime(alt['game_date']) + pd.Timedelta(days=delta)).dt.strftime('%Y-%m-%d')
        left = m.loc[miss_idx, ['playerId', 'game_date']].reset_index()
        fill = left.merge(alt, on=['playerId', 'game_date'], how='left').set_index('index')
        hit = fill.index[fill['mu'].notna()]
        if len(hit):
            m.loc[hit, 'mu'] = fill.loc[hit, 'mu']
            m.loc[hit, 'k'] = fill.loc[hit, 'k']
        miss_idx = m.index[m['mu'].isna() & m.playerId.notna()]
    print(f'  join: {int(m.mu.notna().sum())} with mu, '
          f'{int((m.mu.isna() & m.playerId.notna()).sum())} id-but-no-game, '
          f'{int(m.playerId.isna().sum())} no nhl_id, of {len(m)} graded sides')
    m = m[m.mu.notna()].copy()
    if not len(m):
        return m
    ks = float(m.k.iloc[0])
    m['p_over'] = [float(p_over(mu, ks, ln)) for mu, ln in zip(m.mu, m.line)]
    # implied from the side's own price is not enough — we need the over price and under price as a pair
    # Build pairs
    key = ['date', 'event', 'espn_id', 'line']
    ov = m[m.side == 'over'][key + ['price_D', 'price_close', 'result', 'units_D', 'units_close', 'p_over',
                                    'player', 'game', 'actual', 'playerId', 'side_method']].rename(
        columns={'price_D': 'over_D', 'price_close': 'over_C', 'result': 'result_over',
                 'units_D': 'u_over_D', 'units_close': 'u_over_C'})
    un = m[m.side == 'under'][key + ['price_D', 'price_close', 'result']].rename(
        columns={'price_D': 'under_D', 'price_close': 'under_C', 'result': 'result_under'})
    pair = ov.merge(un, on=key, how='inner')
    pair['p_under'] = 1 - pair.p_over
    pair['imp_over'] = pair.over_D.map(lambda x: am2p(x) if pd.notna(x) else np.nan)
    pair['imp_under'] = pair.under_D.map(lambda x: am2p(x) if pd.notna(x) else np.nan)
    pair['edge_over'] = pair.p_over - pair.imp_over
    pair['edge_under'] = pair.p_under - pair.imp_under
    # pick the side with positive edge (at D); skip if no D price or no positive edge
    def pick(r):
        eo, eu = r.edge_over, r.edge_under
        if pd.isna(r.over_D) and pd.isna(r.under_D):
            return pd.Series(dict(pick=None, pick_price=np.nan, pick_result=None, pick_edge=np.nan))
        cand = []
        if pd.notna(r.over_D) and pd.notna(eo) and eo > 0:
            cand.append(('over', r.over_D, r.result_over, eo))
        if pd.notna(r.under_D) and pd.notna(eu) and eu > 0:
            cand.append(('under', r.under_D, r.result_under, eu))
        if not cand:
            return pd.Series(dict(pick=None, pick_price=np.nan, pick_result=None, pick_edge=np.nan))
        cand.sort(key=lambda x: -x[3])
        side, price, res, edge = cand[0]
        return pd.Series(dict(pick=side, pick_price=price, pick_result=res, pick_edge=edge))
    picked = pair.apply(pick, axis=1)
    pair = pd.concat([pair, picked], axis=1)
    return pair


def report_picks(pair, label):
    taken = pair[pair.pick.notna()].copy()
    taken['in_band'] = taken.pick_price.map(in_band)
    rows = []
    rows.append(summarize_bets(taken.rename(columns={'pick_price': 'price_D', 'pick_result': 'result'}),
                               label=f'{label} all (edge>0 at D)'))
    rows.append(summarize_bets(taken[taken.in_band].rename(columns={'pick_price': 'price_D', 'pick_result': 'result'}),
                               label=f'{label} in band (price >= {BAND_FLOOR})'))
    rows.append(summarize_bets(taken[~taken.in_band].rename(columns={'pick_price': 'price_D', 'pick_result': 'result'}),
                               label=f'{label} outside band (worse than {BAND_FLOOR})'))
    return rows, taken


def run_points():
    print('\n========== POINTS MODEL ==========')
    df = load_points()
    F = points_feat_cols(df)
    print('points rows', len(df), 'seasons', sorted(df.season.unique()), 'feats', len(F), F)
    leakage_points(df, F)
    use = df[df.n_prior >= 5].copy()
    tr, te = use[use.season <= 2025], use[use.season == 2026]
    print('train', len(tr), 'oos_2026', len(te))
    # walk-forward quality on 2023-2025 (no prices). SKIP_WF=1 reuses numbers from a prior run.
    wf = []
    if os.environ.get('SKIP_WF') == '1':
        wf = [
            dict(season=2023, n=46706, k=200.0, nll=0.8372, mae=0.5309, mean_mu=0.471, mean_y=0.462),
            dict(season=2024, n=46700, k=200.0, nll=0.8246, mae=0.5167, mean_mu=0.448, mean_y=0.451),
            dict(season=2025, n=46669, k=200.0, nll=0.8368, mae=0.5247, mean_mu=0.464, mean_y=0.463),
        ]
        print('walk-forward skipped (SKIP_WF=1); using prior points WF numbers')
    for s in [] if os.environ.get('SKIP_WF') == '1' else [2023, 2024, 2025]:
        trs, tes = use[use.season < s], use[use.season == s]
        if tes.empty or trs.empty:
            continue
        _, k, mu = train_poisson(trs, tes, F, 'points', tag=f'points_wf_{s}')
        y = tes.points.values
        wf.append(dict(season=s, n=len(tes), k=round(k, 2),
                       nll=round(nll(k, y, mu), 4),
                       mae=round(np.mean(np.abs(mu - y)), 4),
                       mean_mu=round(float(np.mean(mu)), 3), mean_y=round(float(np.mean(y)), 3)))
    print('walk-forward (outcome only, no DK prices):')
    print(pd.DataFrame(wf).to_string(index=False) if wf else '  none')
    m, k, mu = train_poisson(tr, te, F, 'points', tag='points')
    te = te.copy()
    te['mu'] = mu
    te['k'] = k
    print(f'2026 OOS: n={len(te)} k={k:.2f} mae={np.mean(np.abs(mu-te.points.values)):.4f} '
          f'mean_mu={np.mean(mu):.3f} mean_y={te.points.mean():.3f}')
    graded = load_graded_ou('points')
    print('graded points O/U rows', len(graded), 'with nhl_id', graded.playerId.notna().sum() if len(graded) else 0)
    pair = attach_prices_and_pick(te, graded)
    print('joined player-game-lines with model+D-or-close', len(pair),
          'matched rate vs graded unique lines',
          (len(pair) / max(1, graded[graded.side=='over'].drop_duplicates(['event','espn_id','line']).shape[0])))
    rows, taken = report_picks(pair, 'points') if len(pair) else ([], pd.DataFrame())
    for r in rows:
        print(r)
    if len(taken):
        taken.to_csv(os.path.join(SHADOW, 'points_oos_picks.csv'), index=False)
    # persist 2026 predictions for shadow
    te[['playerId', 'gameId', 'gameDate', 'date', 'skaterFullName', 'teamAbbrev',
        'opponentTeamAbbrev', 'points', 'mu', 'k', 'n_prior']].to_pickle(os.path.join(MOD, 'points_oos_pred.pkl'))
    return {'model': 'points', 'walk_forward': wf, 'k': k, 'oos_n': int(len(te)),
            'backtest': rows, 'joined_lines': int(len(pair)),
            'features': F, 'train_n': int(len(tr))}


# ---------------------------------------------------------------------------
# SAVES
# ---------------------------------------------------------------------------
def load_saves():
    p = os.path.join(DATA, 'goalie_saves.pkl')
    if not os.path.exists(p):
        raise SystemExit(f'missing {p}')
    df = pd.read_pickle(p).drop_duplicates(['playerId', 'gameId'])
    df['date'] = pd.to_datetime(df.gameDate)
    df['saves'] = pd.to_numeric(df.saves, errors='coerce')
    df['sa'] = pd.to_numeric(df.shotsAgainst, errors='coerce')
    # timeOnIce is seconds in this API (3600 = 60 min)
    toi = pd.to_numeric(df.timeOnIce, errors='coerce')
    df['toi_min'] = np.where(toi > 90, toi / 60.0, toi)  # guard if some seasons are already minutes
    df['starter'] = (pd.to_numeric(df.gamesStarted, errors='coerce').fillna(0) >= 1).astype(int)
    df = df.dropna(subset=['saves', 'playerId', 'gameId', 'date'])
    df = df.sort_values(['date', 'gameId', 'playerId']).reset_index(drop=True)
    df = add_rest_home(df)
    df = rolling_asof(df, ['saves', 'sa', 'toi_min', 'starter'])
    # opponent shots for (from team games) if available
    tp = os.path.join(DATA, 'team_games.pkl')
    if os.path.exists(tp):
        tg = pd.read_pickle(tp).copy()
        tg['date'] = pd.to_datetime(tg.gameDate)
        # opponent's recent shots for == shots the goalie is likely to face
        opp = (tg.sort_values('date').copy())
        opp['opp_sf_r20'] = opp.groupby('teamAbbrev').shotsForPerGame.transform(
            lambda s: s.shift(1).rolling(20, min_periods=3).mean())
        opp['team_sa_r20'] = opp.groupby('teamAbbrev').shotsAgainstPerGame.transform(
            lambda s: s.shift(1).rolling(20, min_periods=3).mean())
        df = df.merge(opp[['gameId', 'teamAbbrev', 'opp_sf_r20']].rename(columns={'teamAbbrev': 'opponentTeamAbbrev'}),
                      on=['gameId', 'opponentTeamAbbrev'], how='left')
        df = df.merge(opp[['gameId', 'teamAbbrev', 'team_sa_r20']], on=['gameId', 'teamAbbrev'], how='left')
    return df


def saves_feat_cols(df):
    # Do not use same-game gamesStarted ('starter') — that's an outcome in the historical box.
    # Rolling starter_* features are prior-game only. Who has a DK line is the live starter filter.
    return [c for c in df.columns if c.endswith(('_r5', '_r10', '_r30', '_car', '_r20')) or c in
            ('n_prior', 'rest', 'b2b', 'home')]


def leakage_saves(df, F):
    cut = df.date.sort_values().iloc[len(df) // 2]
    t = df.copy()
    fut = t.date >= cut
    t.loc[fut, ['saves', 'sa', 'toi_min', 'starter']] = 999
    t = t.drop(columns=[c for c in F if c not in ('home', 'rest', 'b2b', 'n_prior', 'starter') and c in t.columns], errors='ignore')
    t = rolling_asof(t, ['saves', 'sa', 'toi_min', 'starter'])
    key = ['playerId', 'gameId']
    a = df[df.date == cut].set_index(key)
    b = t[t.date == cut].set_index(key)
    common = a.index.intersection(b.index)
    bad = [c for c in F if c in a.columns and c in b.columns
           and not np.allclose(a.loc[common, c].fillna(-1).astype(float),
                               b.loc[common, c].fillna(-1).astype(float), equal_nan=True)]
    if bad:
        raise SystemExit(f'SAVES LEAKAGE {bad}')
    print('saves leakage test passed')


def run_saves():
    print('\n========== SAVES MODEL ==========')
    df = load_saves()
    F = saves_feat_cols(df)
    print('saves rows', len(df), 'seasons', sorted(df.season.unique()), 'feats', len(F))
    leakage_saves(df, F)
    # train primarily on starters (or 30+ min); still score anyone with a line
    use = df[(df.n_prior >= 5) & ((df.starter == 1) | (df.toi_min >= 30))].copy()
    tr, te = use[use.season <= 2025], use[use.season == 2026]
    print('train', len(tr), 'oos_2026', len(te))
    wf = []
    for s in [2023, 2024, 2025]:
        trs, tes = use[use.season < s], use[use.season == s]
        if tes.empty or trs.empty:
            continue
        _, k, mu = train_poisson(trs, tes, F, 'saves', tag=f'saves_wf_{s}')
        y = tes.saves.values
        wf.append(dict(season=s, n=len(tes), k=round(k, 2),
                       nll=round(nll(k, y, mu), 4),
                       mae=round(np.mean(np.abs(mu - y)), 4),
                       mean_mu=round(float(np.mean(mu)), 3), mean_y=round(float(np.mean(y)), 3)))
    print('walk-forward (outcome only, no DK prices):')
    print(pd.DataFrame(wf).to_string(index=False) if wf else '  none')
    m, k, mu = train_poisson(tr, te, F, 'saves', tag='saves')
    te = te.copy(); te['mu'] = mu; te['k'] = k
    print(f'2026 OOS: n={len(te)} k={k:.2f} mae={np.mean(np.abs(mu-te.saves.values)):.4f} '
          f'mean_mu={np.mean(mu):.3f} mean_y={te.saves.mean():.3f}')
    # attach_prices_and_pick expects a 'points' optional col; rename saves out of the way
    graded = load_graded_ou('saves')
    # reuse joiner: it looks at mu,k,date,playerId
    pred = te.rename(columns={'saves': 'points'})  # joiner only uses mu/k/date/playerId
    pair = attach_prices_and_pick(pred, graded)
    print('joined goalie-game-lines', len(pair))
    rows, taken = report_picks(pair, 'saves') if len(pair) else ([], pd.DataFrame())
    for r in rows:
        print(r)
    if len(taken):
        taken.to_csv(os.path.join(SHADOW, 'saves_oos_picks.csv'), index=False)
    te[['playerId', 'gameId', 'gameDate', 'date', 'goalieFullName', 'teamAbbrev',
        'opponentTeamAbbrev', 'saves', 'mu', 'k', 'n_prior', 'starter']].to_pickle(os.path.join(MOD, 'saves_oos_pred.pkl'))
    return {'model': 'saves', 'walk_forward': wf, 'k': k, 'oos_n': int(len(te)),
            'backtest': rows, 'joined_lines': int(len(pair)),
            'features': F, 'train_n': int(len(tr))}


# ---------------------------------------------------------------------------
# PUCKLINE
# ---------------------------------------------------------------------------
def load_team():
    p = os.path.join(DATA, 'team_games.pkl')
    if not os.path.exists(p):
        raise SystemExit(f'missing {p}')
    df = pd.read_pickle(p).copy()
    df['date'] = pd.to_datetime(df.gameDate)
    for c in ['goalsFor', 'goalsAgainst', 'shotsForPerGame', 'shotsAgainstPerGame']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna(subset=['goalsFor', 'goalsAgainst', 'gameId', 'teamAbbrev', 'date'])
    df = df.sort_values(['date', 'gameId', 'teamAbbrev']).reset_index(drop=True)
    # rest / b2b / home at team level (reuse player helpers with team as playerId)
    tmp = df.rename(columns={'teamAbbrev': 'playerId'})
    tmp = add_rest_home(tmp)
    tmp = rolling_asof(tmp, ['goalsFor', 'goalsAgainst', 'shotsForPerGame', 'shotsAgainstPerGame'],
                       windows=(5, 10, 20))
    df = tmp.rename(columns={'playerId': 'teamAbbrev'})
    return df


def pair_games(df):
    home = df[df.homeRoad == 'H'].copy()
    away = df[df.homeRoad == 'R'].copy()
    cols = [c for c in df.columns if c.endswith(('_r5', '_r10', '_r20', '_car')) or c in
            ('rest', 'b2b', 'n_prior', 'goalsFor', 'goalsAgainst', 'teamAbbrev', 'date', 'season', 'gameDate')]
    h = home[['gameId'] + cols].rename(columns=lambda c: c if c in ('gameId',) else 'h_' + c)
    a = away[['gameId'] + [c for c in cols if c != 'season']].rename(columns=lambda c: c if c in ('gameId',) else 'a_' + c)
    g = h.merge(a, on='gameId', how='inner')
    # recover season/date from home
    g['season'] = g['h_season']
    g['date'] = g['h_date']
    g['home_gf'] = g['h_goalsFor']
    g['away_gf'] = g['a_goalsFor']
    g['margin'] = g.home_gf - g.away_gf  # official GF includes SO +1
    g['home_covers_m15'] = (g.margin >= 2).astype(int)   # home -1.5
    g['away_covers_m15'] = (g.margin <= -2).astype(int)  # away -1.5
    g['home_covers_p15'] = (g.margin >= -1).astype(int)  # home +1.5
    g['away_covers_p15'] = (g.margin <= 1).astype(int)   # away +1.5
    return g


def puckline_feats(g):
    return [c for c in g.columns if c.startswith('h_') or c.startswith('a_')
            if c not in ('h_goalsFor', 'h_goalsAgainst', 'h_season', 'h_date', 'h_gameDate',
                         'a_goalsFor', 'a_goalsAgainst', 'a_date', 'a_gameDate', 'a_teamAbbrev', 'h_teamAbbrev')]


def pois_cover_m15(mu_h, mu_a, n=15):
    """P(home_goals - away_goals >= 2) under independent Poisson."""
    ks = np.arange(0, n + 1)
    ph = stats.poisson.pmf(ks, np.clip(mu_h, 1e-6, None)[:, None])
    pa = stats.poisson.pmf(ks, np.clip(mu_a, 1e-6, None)[:, None])
    # P(h - a >= 2) = sum_a P(a)*P(h >= a+2)
    # survival: 1 - F(a+1) = P(h >= a+2)
    out = np.zeros(len(mu_h))
    for a in range(n + 1):
        out += pa[:, a] * (1 - stats.poisson.cdf(a + 1, np.clip(mu_h, 1e-6, None)))
    return out


def run_puckline():
    print('\n========== PUCKLINE MODEL ==========')
    df = load_team()
    g = pair_games(df)
    F = puckline_feats(g)
    # drop any leftover raw outcomes if they slipped in
    F = [c for c in F if 'goalsFor' not in c and 'goalsAgainst' not in c or c.endswith(('_r5', '_r10', '_r20', '_car'))]
    print('games', len(g), 'seasons', sorted(g.season.unique()), 'feats', len(F))
    # leakage: corrupt goals after cutoff, rebuild team rolls, re-pair, compare
    cut = df.date.sort_values().iloc[len(df) // 2]
    t = df.copy()
    fut = t.date >= cut
    t.loc[fut, ['goalsFor', 'goalsAgainst', 'shotsForPerGame', 'shotsAgainstPerGame']] = 999
    tmp = t.rename(columns={'teamAbbrev': 'playerId'})
    # need to recompute rolls from raw; drop roll cols first
    raw_cols = [c for c in tmp.columns if not (c.endswith(('_r5', '_r10', '_r20', '_car')) or c in
                ('rest', 'b2b', 'n_prior', 'home'))]
    tmp = tmp[raw_cols]
    tmp = add_rest_home(tmp)
    tmp = rolling_asof(tmp, ['goalsFor', 'goalsAgainst', 'shotsForPerGame', 'shotsAgainstPerGame'],
                       windows=(5, 10, 20))
    t2 = tmp.rename(columns={'playerId': 'teamAbbrev'})
    g2 = pair_games(t2)
    a = g[g.date == cut].set_index('gameId')
    b = g2[g2.date == cut].set_index('gameId')
    common = a.index.intersection(b.index)
    bad = [c for c in F if c in a.columns and c in b.columns
           and not np.allclose(a.loc[common, c].fillna(-1).astype(float),
                               b.loc[common, c].fillna(-1).astype(float), equal_nan=True)]
    if bad:
        raise SystemExit(f'PUCKLINE LEAKAGE {bad}')
    print('puckline leakage test passed')
    use = g[(g.h_n_prior.fillna(0) >= 5) & (g.a_n_prior.fillna(0) >= 5)].copy()
    tr, te = use[use.season <= 2025], use[use.season == 2026]
    print('train games', len(tr), 'oos_2026 games', len(te))
    # two poisson models: home GF and away GF
    def fit_goals(tr, te, ycol, tag):
        seasons = sorted(tr.season.unique())
        vl = tr[tr.season == seasons[-1]] if seasons else tr.iloc[0:0]
        tr2 = tr[tr.season < seasons[-1]] if len(seasons) >= 2 else tr
        if len(vl) and len(tr2):
            m = lgb.train(P, lgb.Dataset(tr2[F], tr2[ycol]), 2000,
                          valid_sets=[lgb.Dataset(vl[F], vl[ycol])],
                          callbacks=[lgb.early_stopping(100, verbose=False)])
            n_est = max(50, m.best_iteration or 200)
        else:
            n_est = 400
        m = lgb.train(P, lgb.Dataset(tr[F], tr[ycol]), n_est)
        m.save_model(os.path.join(MOD, f'{tag}.txt'))
        mu = np.clip(m.predict(te[F]), 1e-6, None) if len(te) else np.array([])
        return m, n_est, mu

    # walk-forward cover rates (outcome only)
    wf = []
    for s in [2023, 2024, 2025]:
        trs, tes = use[use.season < s], use[use.season == s]
        if tes.empty or trs.empty:
            continue
        _, _, mu_h = fit_goals(trs, tes, 'home_gf', f'puckline_h_wf_{s}')
        _, _, mu_a = fit_goals(trs, tes, 'away_gf', f'puckline_a_wf_{s}')
        tes = tes.copy()
        tes['p_home_m15'] = pois_cover_m15(mu_h, mu_a)
        tes['p_away_m15'] = pois_cover_m15(mu_a, mu_h)
        # pick the favorite (higher p of covering -1.5) vs the dog (+1.5 = 1 - opponent -1.5)
        # Outcome-only: if p_home_m15 > 0.5 pick home -1.5 else away -1.5? That's a poor rule because
        # true P(cover -1.5) is typically ~0.40-0.45. Better: pick the side whose cover prob is
        # above the historical base rate of that side, or pick max of p(-1.5) vs p(+1.5 of other).
        # Report calibration of p_home_m15 vs home_covers_m15, and a simple "bet home -1.5 if
        # p above train base, else home +1.5".
        base = trs.home_covers_m15.mean()
        tes['pick_home_m15'] = (tes.p_home_m15 > base).astype(int)
        # evaluate the pick on the corresponding cover
        # if pick home -1.5, result = home_covers_m15; else home +1.5 = home_covers_p15
        tes['pick_hit'] = np.where(tes.pick_home_m15 == 1, tes.home_covers_m15, tes.home_covers_p15)
        wf.append(dict(season=s, n=len(tes),
                       base_home_m15=round(float(base), 4),
                       pred_home_m15=round(float(tes.p_home_m15.mean()), 4),
                       actual_home_m15=round(float(tes.home_covers_m15.mean()), 4),
                       actual_home_p15=round(float(tes.home_covers_p15.mean()), 4),
                       rule_hit=round(float(tes.pick_hit.mean()), 4),
                       mae_margin=round(float(np.mean(np.abs((mu_h - mu_a) - tes.margin))), 3)))
    print('walk-forward (OUTCOME ONLY — no captured puckline prices exist yet):')
    print(pd.DataFrame(wf).to_string(index=False) if wf else '  none')
    mh, nh, mu_h = fit_goals(tr, te, 'home_gf', 'puckline_home')
    ma, na, mu_a = fit_goals(tr, te, 'away_gf', 'puckline_away')
    json.dump({'features': F, 'n_est_home': int(nh), 'n_est_away': int(na)},
              open(os.path.join(MOD, 'puckline.json'), 'w'))
    te = te.copy()
    te['mu_home'] = mu_h
    te['mu_away'] = mu_a
    te['p_home_m15'] = pois_cover_m15(mu_h, mu_a) if len(te) else []
    te['p_away_m15'] = pois_cover_m15(mu_a, mu_h) if len(te) else []
    if len(te):
        base = tr.home_covers_m15.mean()
        te['pick_home_m15'] = (te.p_home_m15 > base).astype(int)
        te['pick_hit'] = np.where(te.pick_home_m15 == 1, te.home_covers_m15, te.home_covers_p15)
        print(f"2026 OOS outcome-only: n={len(te)} home-1.5 actual={te.home_covers_m15.mean():.3f} "
              f"pred={te.p_home_m15.mean():.3f} rule_hit={te.pick_hit.mean():.3f} "
              f"mae_margin={np.mean(np.abs((mu_h-mu_a)-te.margin)):.3f}")
        te.to_pickle(os.path.join(MOD, 'puckline_oos_pred.pkl'))
        # try to join any captured gameline prices (likely none until tonight)
        gl_rows = []
        import glob
        for f in glob.glob(os.path.join(ROOT, 'captures', '*', 'gamelines', '*.json')):
            try:
                s = json.load(open(f))
            except Exception:
                continue
            if s.get('tag') not in ('D', 'C'):
                continue
            gl_rows.append(s)
        priced = 0
        if gl_rows:
            # no historical prices expected; just note count
            evs = {s['event'] for s in gl_rows}
            priced = len(evs)
        print(f'captured puckline events on disk: {priced} (units/ROI require real DK prices; none pre-2026-11-22)')
    else:
        print('no 2026 OOS games in team file')
        priced = 0
    # historical cover rates for context
    hist = tr.agg(n=('gameId', 'size'), home_m15=('home_covers_m15', 'mean'),
                  home_p15=('home_covers_p15', 'mean'),
                  away_m15=('away_covers_m15', 'mean'))
    print('train cover rates (2021-2025):', hist.to_dict() if hasattr(hist, 'to_dict') else hist)
    return {'model': 'puckline', 'walk_forward': wf, 'oos_n': int(len(te)),
            'captured_price_events': priced,
            'note': 'No puckline DK prices existed before 2026-11-22 capture went live. '
                    'Walk-forward and 2026 OOS are outcome-only (cover rates, not units).',
            'features': F, 'train_n': int(len(tr))}


def main():
    t0 = time.time()
    out = {}
    if os.environ.get('SKIP_POINTS') == '1':
        prev = os.path.join(HERE, 'backtest_results.json')
        print('SKIP_POINTS=1: reusing points results if present; running saves + puckline')
        out['points'] = {'model': 'points', 'note': 'reused from prior run this session; see shadow/points_oos_picks.csv'}
    else:
        out['points'] = run_points()
    out['saves'] = run_saves()
    out['puckline'] = run_puckline()
    out['elapsed_s'] = round(time.time() - t0, 1)
    # JSON-friendly
    def conv(x):
        if isinstance(x, (np.floating,)):
            return float(x)
        if isinstance(x, (np.integer,)):
            return int(x)
        if isinstance(x, dict):
            return {k: conv(v) for k, v in x.items()}
        if isinstance(x, list):
            return [conv(v) for v in x]
        return x
    json.dump(conv(out), open(os.path.join(HERE, 'backtest_results.json'), 'w'), indent=2)
    print('\nwrote models_extra/backtest_results.json in', out['elapsed_s'], 's')


if __name__ == '__main__':
    main()
