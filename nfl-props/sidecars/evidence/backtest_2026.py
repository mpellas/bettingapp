"""Evidence block on the graded 2026 paper-track lines (DraftKings via ESPN, D snapshot >= 3 h pre-kick; NO prices:
-110/-110 assumed, so no-vig = 50% and break-even = 52.4%). Weeks with settled in-scope lines: 4 (pre-track) and 5.
Candidate = champion side with |P_model - 0.5| >= 1 pt (all in-scope lines qualify in practice). All 7 signals;
champ is + by construction; move = D line vs DK open. Ex-ante gate K = 4 of 7; others = sensitivity.
Reports hit vs 50%, line-based z-CLV (track.py definition, z_main), game-clustered 95% CIs. VERY small sample."""
import os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE); import nfl_evidence as E
boot = E.boot
D = E.load(max_age_h=1e9); G = D['games'].set_index('game_id'); rows = []
for W in (4, 5, 6):
    t = pd.read_parquet(os.path.join(ROOT, 'data', 'track', f'2026_wk{W:02d}.parquet'))
    t = t[(t.status == 'settled') & t.in_scope & t.p_over_model.notna() & t.actual.notna()]
    for r in t.itertuples():
        g = G.loc[r.game_id]; hist = D['by_player'].get(r.player_id)
        if hist is None: continue
        h = hist[hist.k < 2026 * 100 + W]
        if not len(h): continue
        team = h.team.iloc[-1]; pos = h.position.iloc[-1]
        if team not in (g.home_team, g.away_team): continue
        oppt = g.away_team if team == g.home_team else g.home_team
        ov = r.p_over_model >= 0.5; pside = r.p_over_model if ov else 1 - r.p_over_model
        if pside - 0.5 < 0.01 or r.actual == r.line_D: continue
        sig = E.over_signals(D, r.player_id, r.market, pos, team, oppt, 2026, W, g.home_team, g.away_team, g.spread_line,
                             g.total_line, g.roof, g.temp, g.wind, line_now=r.line_D, line_open=r.line_open)
        sig['champ'] = (1, f'champion {(pside-0.5)*100:+.1f} pts vs 50%')
        c = E.combine(r.player_name, 'over' if ov else 'under', r.line_D, r.market, sig)   # champ is side-specific (+)
        rows.append(dict(week=W, game_id=r.game_id, player=r.player_name, market=r.market, side='over' if ov else 'under',
                         line=r.line_D, p_side=pside, hit=int((r.actual > r.line_D) == ov), z=r.z_main, **c))
X = pd.DataFrame(rows); X.to_csv(os.path.join(HERE, 'backtest_2026_rows.csv'), index=False)
f = lambda t: f'{t[0]*100:+.1f} [{t[1]*100:+.1f}, {t[2]*100:+.1f}]'; fz = lambda t: f'{t[0]:+.3f} [{t[1]:+.3f}, {t[2]:+.3f}]'
print(f'2026 graded in-scope candidate sides: {len(X)} ({X.week.value_counts().sort_index().to_dict()} by week), {X.game_id.nunique()} games; overs {(X.side=="over").mean():.0%}')
print('agrees_n distribution:', X.agrees_n.value_counts().sort_index().to_dict())
print('| rule | sides | games | hit | hit - 50% (pts) | z-CLV (line-based) |'); print('|---|---|---|---|---|---|')
for K in (None, 2, 3, 4, 5):
    s = X if K is None else X[X.agrees_n >= K]; lab = 'all candidates' if K is None else f'agrees >= {K}' + (' (ex-ante K)' if K == 4 else '')
    if len(s) < 5: print(f'| {lab} | {len(s)} | | too few | | |'); continue
    zz = s[s.z.notna()]
    print(f'| {lab} | {len(s)} | {s.game_id.nunique()} | {s.hit.mean():.3f} | {f(boot((s.hit - 0.5).values, s.game_id.values))} | {fz(boot(zz.z.values, zz.game_id.values)) if len(zz) > 4 else "n/a"} |')
s = X[X.agrees_n < 4]; zz = s[s.z.notna()]
print(f'| agrees < 4 | {len(s)} | {s.game_id.nunique()} | {s.hit.mean():.3f} | {f(boot((s.hit - 0.5).values, s.game_id.values))} | {fz(boot(zz.z.values, zz.game_id.values))} |')
print('signal + counts:', {k: int((X[f"sig_{k}"] == "+").sum()) for k in E.SIGS}, ' - counts:', {k: int((X[f"sig_{k}"] == "-").sum()) for k in E.SIGS})
