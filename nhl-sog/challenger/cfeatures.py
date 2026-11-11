"""Challenger features (strictly as-of: every rolling stat is shifted so a game's own outcome never enters its features).
Built on top of the champion's features.feats(). Groups (names used by select.py):
  shrink  : gamma-Poisson shrunk shot / attempt rates (prior = career rate, strength M_GAMES games of TOI) + projected mu
  toi     : TOI trend (r5 - r30), EWM TOI, PP share of team PP time, team PP time r20, opponent PK time allowed r20
  slot    : drill-down opponent test: opponent shots allowed to the player's slot (D / F top6 / F 3rd / F 4th, by TOI
            rank) r20 vs league, plus opponent shots allowed to D and to F separately
  sched   : opponent rest / back-to-back (own home/rest/b2b are already champion features)
  strength: team and opponent goal differential r20, opponent shots-for r20, team shots-against r20 (score-effects proxy)
"""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
M_GAMES = 15
GROUPS = {
    'shrink': ['shr_sog60', 'shr_att60', 'shr_mu'],
    'toi': ['toi_trend', 'toi_ewm3', 'pp_share_r10', 'team_pp_r20', 'opp_pk_r20'],
    'slot': ['opp_slot_ratio_r20', 'opp_D_sa_r20', 'opp_F_sa_r20'],
    'sched': ['opp_rest', 'opp_b2b'],
    'strength': ['team_gd_r20', 'opp_gd_r20', 'opp_sf_r20', 'team_sa_r20'],
}
def _roll(g, col, w, fn='mean', mp=1):
    return g[col].transform(lambda s: getattr(s.shift(1).rolling(w, min_periods=mp), fn)())
def add(df, team_games=None):
    df = df.sort_values(['date', 'gameId']).reset_index(drop=True)
    g = df.groupby('playerId', sort=False)
    # ---- shrink
    df['hrs'] = df.toi / 60
    S10, T10 = _roll(g, 'shots', 10, 'sum'), _roll(g, 'hrs', 10, 'sum')
    A10 = _roll(g, 'att', 10, 'sum')
    Sc = g.shots.transform(lambda s: s.shift(1).expanding().sum()); Tc = g.hrs.transform(lambda s: s.shift(1).expanding().sum())
    Ac = g.att.transform(lambda s: s.shift(1).expanding().sum())
    lg_s = 6.0  # fixed fallback (shots/60) for a player with no history; such rows are dropped (n_prior>=5)
    rate0 = (Sc / Tc).where(Tc > 0, lg_s); arate0 = (Ac / Tc).where(Tc > 0, lg_s * 1.8)
    m = M_GAMES * df.toi_r30.fillna(15.0) / 60
    df['shr_sog60'] = (S10.fillna(0) + rate0 * m) / (T10.fillna(0) + m)
    df['shr_att60'] = (A10.fillna(0) + arate0 * m) / (T10.fillna(0) + m)
    df['shr_mu'] = df.shr_sog60 * df.toi_r5 / 60
    # ---- toi
    df['toi_trend'] = df.toi_r5 - df.toi_r30
    df['toi_ewm3'] = g.toi.transform(lambda s: s.shift(1).ewm(halflife=3, min_periods=1).mean())
    tp = df.groupby(['gameId', 'teamAbbrev', 'opponentTeamAbbrev', 'date'], as_index=False).pptoi.max().sort_values(['date', 'gameId'])
    tp.loc[~tp.gameId.isin(df.loc[df.shots.notna(), 'gameId']), 'pptoi'] = np.nan
    tp['team_pp_r20'] = tp.groupby('teamAbbrev').pptoi.transform(lambda s: s.shift(1).rolling(20, min_periods=3).mean())
    tp['team_pp_r10'] = tp.groupby('teamAbbrev').pptoi.transform(lambda s: s.shift(1).rolling(10, min_periods=3).mean())
    # PP time conceded by a team = PP time of the teams that faced it; keyed by (game, that team as opponent)
    tp['opp_pk_r20'] = tp.groupby('opponentTeamAbbrev').pptoi.transform(lambda s: s.shift(1).rolling(20, min_periods=3).mean())
    df = df.merge(tp[['gameId', 'teamAbbrev', 'team_pp_r20', 'team_pp_r10', 'opp_pk_r20']], on=['gameId', 'teamAbbrev'], how='left')
    df['pp_share_r10'] = (df.pptoi_r10 / df.team_pp_r10).clip(0, 1.5)
    # ---- slot (drill-down opponent test)
    df['frk'] = df[df.D == 0].groupby(['gameId', 'teamAbbrev']).toi.rank(ascending=False, method='first')
    df['slot_g'] = np.where(df.D == 1, 'D', np.where(df.frk <= 6, 'F_top6', np.where(df.frk <= 9, 'F_3rd', 'F_4th')))
    df.loc[df.toi.isna(), 'slot_g'] = None
    g = df.groupby('playerId', sort=False)
    frk_asof = g.frk.transform(lambda s: s.shift(1).rolling(10, min_periods=1).mean())
    df['slot_asof'] = np.where(df.D == 1, 'D', np.where(frk_asof <= 6.5, 'F_top6', np.where(frk_asof <= 9.5, 'F_3rd', 'F_4th')))
    sg = df[df.slot_g.notna()].groupby(['gameId', 'opponentTeamAbbrev', 'date', 'slot_g'], as_index=False).shots.sum()
    games = df[['gameId', 'opponentTeamAbbrev', 'date']].drop_duplicates()
    full = games.assign(k=1).merge(pd.DataFrame({'slot_g': ['D', 'F_top6', 'F_3rd', 'F_4th'], 'k': 1}), on='k').drop(columns='k')
    sg = full.merge(sg, on=['gameId', 'opponentTeamAbbrev', 'date', 'slot_g'], how='left').sort_values(['date', 'gameId'])
    played = sg.gameId.isin(df.loc[df.shots.notna(), 'gameId'])
    sg.loc[played, 'shots'] = sg.loc[played, 'shots'].fillna(0)
    sg['opp_slot_sa_r20'] = sg.groupby(['opponentTeamAbbrev', 'slot_g']).shots.transform(lambda s: s.shift(1).rolling(20, min_periods=3).mean())
    # league slot mean from strictly earlier DATES (a row shift would leak same-day games)
    dl = sg[sg.shots.notna()].groupby(['slot_g', 'date']).shots.agg(['sum', 'count']).reset_index().sort_values('date')
    for c in ('sum', 'count'): dl[c + '_p'] = dl.groupby('slot_g')[c].transform(lambda s: s.shift(1).rolling(90, min_periods=10).sum())
    dl['lg_slot'] = dl.sum_p / dl.count_p
    alld = sg[['slot_g', 'date']].drop_duplicates().merge(dl[['slot_g', 'date', 'lg_slot']], on=['slot_g', 'date'], how='left').sort_values('date')
    # future dates (no games played yet) take the latest known value
    alld['lg_slot'] = alld.groupby('slot_g').lg_slot.ffill()
    sg = sg.merge(alld, on=['slot_g', 'date'], how='left')
    sg['opp_slot_ratio_r20'] = sg.opp_slot_sa_r20 / sg.lg_slot
    df = df.merge(sg[['gameId', 'opponentTeamAbbrev', 'slot_g', 'opp_slot_ratio_r20']].rename(columns={'slot_g': 'slot_asof'}),
                  on=['gameId', 'opponentTeamAbbrev', 'slot_asof'], how='left')
    dD = sg.pivot_table(index=['gameId', 'opponentTeamAbbrev'], columns='slot_g', values='opp_slot_sa_r20').reset_index()
    dD['opp_D_sa_r20'] = dD['D']; dD['opp_F_sa_r20'] = dD[['F_top6', 'F_3rd', 'F_4th']].sum(axis=1, min_count=3)
    df = df.merge(dD[['gameId', 'opponentTeamAbbrev', 'opp_D_sa_r20', 'opp_F_sa_r20']], on=['gameId', 'opponentTeamAbbrev'], how='left')
    # ---- sched (opponent)
    td = df[['gameId', 'teamAbbrev', 'date']].drop_duplicates().sort_values('date')
    td['t_rest'] = td.groupby('teamAbbrev').date.diff().dt.days.clip(upper=10)
    df = df.merge(td[['gameId', 'teamAbbrev', 't_rest']].rename(columns={'teamAbbrev': 'opponentTeamAbbrev', 't_rest': 'opp_rest'}),
                  on=['gameId', 'opponentTeamAbbrev'], how='left')
    df['opp_b2b'] = (df.opp_rest == 1).astype(int)
    # ---- strength (team game logs)
    if team_games is None: team_games = pd.read_pickle(os.path.join(HERE, 'team_games.pkl'))
    t = team_games.copy(); t['date'] = pd.to_datetime(t.gameDate)
    syn = df[['gameId', 'teamAbbrev', 'opponentTeamAbbrev', 'date']].drop_duplicates(['gameId', 'teamAbbrev'])
    syn = syn[~syn.set_index(['gameId', 'teamAbbrev']).index.isin(t.set_index(['gameId', 'teamAbbrev']).index)]
    t = pd.concat([t, syn], ignore_index=True).sort_values(['date', 'gameId'])  # future games: NaN outcomes, shifted out
    t['gd'] = t.goalsFor - t.goalsAgainst
    gt = t.groupby('teamAbbrev')
    t['team_gd_r20'] = gt.gd.transform(lambda s: s.shift(1).rolling(20, min_periods=3).mean())
    t['team_sf_g_r20'] = gt.shotsForPerGame.transform(lambda s: s.shift(1).rolling(20, min_periods=3).mean())
    t['team_sa_r20'] = gt.shotsAgainstPerGame.transform(lambda s: s.shift(1).rolling(20, min_periods=3).mean())
    df = df.merge(t[['gameId', 'teamAbbrev', 'team_gd_r20', 'team_sa_r20']], on=['gameId', 'teamAbbrev'], how='left')
    o = t[['gameId', 'teamAbbrev', 'team_gd_r20', 'team_sf_g_r20']].rename(columns={'teamAbbrev': 'opponentTeamAbbrev', 'team_gd_r20': 'opp_gd_r20', 'team_sf_g_r20': 'opp_sf_r20'})
    df = df.merge(o, on=['gameId', 'opponentTeamAbbrev'], how='left')
    return df
