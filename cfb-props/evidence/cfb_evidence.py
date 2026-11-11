"""CFB game-line EVIDENCE block (spreads and totals). Shadow/context only. UNTESTED: no historical CFB lines exist on
this box (ESPN drops odds once a game is final), so none of these signals has been checked against a market price.
0 Odds API credits: ESPN scoreboard scores (free) + this repo's own DK snapshots (lines/snapshots.csv).

Ratings (refit on every run, from final scores only, games before the target date):
  margin model   home_margin = HFA*(not neutral) + r_home - r_away       (weighted ridge least squares)
  points model   pts_team    = mu + HFA_pts/2*(home) + off_team + def_opp  (same weights; gives a total)
  weights        current-season games 1.0; prior-season games 0.15 (transfer portal: prior season shrunk hard);
                 ridge pulls every rating to 0 with the weight of ~2 games. FCS opponents are rated like anyone else
                 except that FCS teams (seen only in 1-2 games vs FBS) are pooled into one 'FCS' team.
Spread signals (oriented for the HOME side; flipped for the away side), agrees N of 4:
  power   predicted home margin minus market home margin (-spread_home_line)      band +/-1.5 pts
  form    last-3-games residual margin (actual minus rating prediction), home minus away   band +/-3 pts
  home    team-specific home edge: home team's mean home residual this season, shrunk n/(n+4)   band +/-1.5 pts
          (0 at neutral sites)
  move    DK spread now vs DK open: + home if the line moved >= 1 pt toward the home team
Total signals (oriented for the OVER), agrees N of 3:
  power_total   predicted total minus market total   band +/-2 pts
  form_total    last-3-games total residual, mean of the two teams   band +/-3 pts
  move_total    DK total now vs open, band +/-1 pt
Tempo (plays per game) is NOT derivable from ESPN scores alone, so it is not a signal; the points model is the
"total environment". Bands fixed before use; nothing is fitted to outcomes beyond the ratings themselves."""
import argparse, datetime as dt, glob, json, os, sys, time
import numpy as np, pandas as pd, requests
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE); CACHE = os.path.join(HERE, 'cache')
SB = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard'
PRIOR_W, RIDGE = 0.15, 2.0

def fetch_scores(season, weeks, max_age_h):
    p = os.path.join(CACHE, f'scores_{season}.csv')
    if os.path.exists(p) and (time.time() - os.path.getmtime(p)) / 3600 < max_age_h: return pd.read_csv(p, dtype={'event_id': str})
    rows = []
    for st, wk in [(2, w) for w in weeks] + ([(3, 1)] if season < dt.date.today().year else []):
        try:
            d = requests.get(SB, params=dict(dates=season, seasontype=st, week=wk, groups=80, limit=500), timeout=30).json()
        except Exception as e:
            print('[cfb-evidence] fetch failed', season, wk, e); continue
        for e in d.get('events', []):
            c = e['competitions'][0]
            if c['status']['type']['state'] != 'post': continue
            t = {x['homeAway']: x for x in c['competitors']}
            rows.append(dict(event_id=e['id'], season=season, week=wk, seasontype=st, date=e['date'], neutral=bool(c.get('neutralSite')),
                             home=t['home']['team']['abbreviation'], away=t['away']['team']['abbreviation'],
                             home_pts=float(t['home']['score']), away_pts=float(t['away']['score'])))
    df = pd.DataFrame(rows).drop_duplicates('event_id')
    if len(df): os.makedirs(CACHE, exist_ok=True); df.to_csv(p, index=False)
    elif os.path.exists(p): return pd.read_csv(p, dtype={'event_id': str})
    return df

def load(season=2026, max_age_h=3.0):
    """FCS teams appear here only in their 1-2 games vs FBS each season; they are pooled into one 'FCS' team so that
    FBS-hosts-FCS blowouts do not inflate home field (a team is FBS if it has >= 4 games in either season)."""
    cur = fetch_scores(season, range(1, 17), max_age_h)
    prev = fetch_scores(season - 1, range(1, 17), 1e9)
    G = pd.concat([prev, cur], ignore_index=True)
    n = pd.concat([G[['season', 'home']].rename(columns={'home': 't'}), G[['season', 'away']].rename(columns={'away': 't'})]).value_counts()
    fbs = {t for (ss, t), k in n.items() if k >= 4}
    for c in ('home', 'away'): G[c] = G[c].where(G[c].isin(fbs), 'FCS')
    return G

HFA_W = 200.0
def fit(G, season, before, hfa_prior=None):
    """weighted ridge fits on final games before `before` (UTC ISO). Returns dict of ratings. Home field is pulled
    toward the PRIOR season's full-season estimate with the weight of 200 games: early-season non-conference home
    games (P4 hosting G5/FCS) otherwise inflate it (2026 to Oct 17: 5.0 pts unpulled vs 3.9 for all of 2025)."""
    if hfa_prior is None and (G.season == season - 1).any():
        hfa_prior = fit(G[G.season == season - 1], season - 1, '9999', hfa_prior=0.0)['hfa'] if season > G.season.min() else 0.0
    hw = HFA_W if hfa_prior else 1e-6; hfa_prior = hfa_prior or 0.0
    g = G[G.date < before].copy(); g['w'] = np.where(g.season == season, 1.0, PRIOR_W)
    teams = sorted(set(g.home) | set(g.away)); ix = {t: i for i, t in enumerate(teams)}; n, m = len(teams), len(g)
    h = np.array([ix[t] for t in g.home]); a = np.array([ix[t] for t in g.away]); hf = (~g.neutral.astype(bool)).astype(float).values
    w = g.w.values; sw = np.sqrt(w)
    # margin: [HFA, r_1..r_n]
    X = np.zeros((m, n + 1)); X[:, 0] = hf; X[np.arange(m), 1 + h] = 1; X[np.arange(m), 1 + a] = -1
    y = (g.home_pts - g.away_pts).values
    R = np.eye(n + 1) * RIDGE; R[0, 0] = hw; rhs = (X * w[:, None]).T @ y; rhs[0] += hw * hfa_prior
    beta = np.linalg.solve((X * w[:, None]).T @ X + R, rhs)
    # points: rows per team-game: [mu, home_half, off_1..n, def_1..n]
    P = np.zeros((2 * m, 2 + 2 * n)); P[:, 0] = 1
    P[:m, 1] = hf / 2; P[m:, 1] = -hf / 2
    P[np.arange(m), 2 + h] = 1; P[np.arange(m), 2 + n + a] = 1
    P[m + np.arange(m), 2 + a] = 1; P[m + np.arange(m), 2 + n + h] = 1
    yp = np.r_[g.home_pts.values, g.away_pts.values]; wp = np.r_[w, w]
    Rp = np.eye(2 + 2 * n) * RIDGE; Rp[0, 0] = Rp[1, 1] = 1e-6
    bp = np.linalg.solve((P * wp[:, None]).T @ P + Rp, (P * wp[:, None]).T @ yp)
    r = dict(zip(teams, beta[1:])); off = dict(zip(teams, bp[2:2 + n])); de = dict(zip(teams, bp[2 + n:]))
    out = dict(hfa=beta[0], hfa_prior=hfa_prior, r=r, mu=bp[0], hfa_pts=bp[1], off=off, de=de, n_games=m, season=season)
    # residuals for form / home edge (current season only)
    c = g[g.season == season].copy()
    c['pred_m'] = [pred_margin(out, x.home, x.away, x.neutral) for x in c.itertuples()]
    c['pred_t'] = [pred_total(out, x.home, x.away) for x in c.itertuples()]
    c['res_m'] = c.home_pts - c.away_pts - c.pred_m; c['res_t'] = c.home_pts + c.away_pts - c.pred_t
    out['cur'] = c.sort_values('date'); return out

def pred_margin(F, home, away, neutral):
    return (0 if neutral else F['hfa']) + F['r'].get(home, 0) - F['r'].get(away, 0)
def pred_total(F, home, away):
    return 2 * F['mu'] + F['off'].get(home, 0) + F['de'].get(away, 0) + F['off'].get(away, 0) + F['de'].get(home, 0)

def team_form(F, team, k=3):
    c = F['cur']; x = c[(c.home == team) | (c.away == team)].tail(k)
    if len(x) < 2: return np.nan, np.nan, len(x)
    rm = np.where(x.home == team, x.res_m, -x.res_m)
    return float(rm.mean()), float(x.res_t.mean()), len(x)

def home_edge(F, team):
    c = F['cur']; x = c[(c.home == team) & (~c.neutral.astype(bool))]
    n = len(x); return (float(x.res_m.mean()) * n / (n + 4) if n else 0.0), n

def band(v, b):
    if v is None or (isinstance(v, float) and np.isnan(v)): return 0
    return 1 if v > b else (-1 if v < -b else 0)
SYM = {1: '+', -1: '-', 0: '0'}

def game_evidence(F, r):
    """r: one snapshots.csv row (latest pre capture). Returns rows for home/away spread sides and over/under."""
    home, away, neu = r.home, r.away, False
    neu = bool(r.get('neutral', False)) if 'neutral' in r else False
    pm = pred_margin(F, home, away, neu); pt = pred_total(F, home, away)
    mkt_m = -float(r.spread_home_line) if pd.notna(r.spread_home_line) else np.nan
    fh, fth, nh = team_form(F, home); fa, fta, na = team_form(F, away); he, nhg = home_edge(F, home)
    S = {'power': (band(pm - mkt_m, 1.5), f'rating home margin {pm:+.1f} vs market {mkt_m:+.1f}'),
         'form': (band((fh - fa) if pd.notna(fh) and pd.notna(fa) else np.nan, 3),
                  f'last-3 residual {home} {fh:+.1f} vs {away} {fa:+.1f}' if pd.notna(fh) and pd.notna(fa) else 'form n/a (<2 games)'),
         'home': ((0, 'neutral site') if neu else (band(he, 1.5), f'{home} home edge {he:+.1f} ({nhg} home games, shrunk)')),
         'move': (band(-(float(r.spread_home_line) - float(r.open_spread_home_line)) if pd.notna(r.open_spread_home_line) else np.nan, 0.99),
                  f'DK spread {home} {r.open_spread_home_line:+g} -> {r.spread_home_line:+g}' if pd.notna(r.open_spread_home_line) else 'move n/a')}
    T = {'power_total': (band(pt - float(r.total), 2) if pd.notna(r.total) else 0, f'rating total {pt:.1f} vs market {r.total:g}'),
         'form_total': (band(np.nanmean([fth, fta]) if pd.notna(fth) or pd.notna(fta) else np.nan, 3),
                        f'last-3 total residual {home} {fth:+.1f}, {away} {fta:+.1f}' if pd.notna(fth) and pd.notna(fta) else 'form n/a'),
         'move_total': (band(float(r.total) - float(r.open_total), 0.99) if pd.notna(r.open_total) and pd.notna(r.total) else 0,
                        f'DK total {r.open_total:g} -> {r.total:g}' if pd.notna(r.open_total) else 'move n/a')}
    out = []
    for side, s, line, price in ((home, 1, r.spread_home_line, r.spread_home_price), (away, -1, r.spread_away_line, r.spread_away_price)):
        out.append(_row(r, 'spread', f'{side} {line:+g}', price, S, s, 4, pm, mkt_m))
    for side, s, price in (('Over', 1, r.over_price), ('Under', -1, r.under_price)):
        out.append(_row(r, 'total', f'{side} {r.total:g}', price, T, s, 3, pt, r.total))
    return out

def _row(r, mkt, label, price, sig, s, K, model, market):
    d = dict(event_id=r.event_id, game=f'{r.away} @ {r.home}', kickoff_utc=r.kickoff_utc, market=mkt, side=label, dk_price=price,
             rating_value=round(model, 1), market_value=market, captured_utc=r.captured_utc); ag, ga = [], []
    for k, (v, t) in sig.items():
        v *= s; d[f'sig_{k}'] = SYM[v]; d[f'why_{k}'] = t; (ag if v > 0 else ga if v < 0 else []).append(t)
    d['agrees_n'] = len(ag); d['of_k'] = K; d['disagrees_n'] = len(ga)
    d['evidence_summary'] = f"{r.away}@{r.home} {label}: agrees {len(ag)} of {K} (" + ('; '.join(ag) or 'none') + ')' + \
                            ('; against: ' + '; '.join(ga) if ga else '; nothing against') + ' [UNTESTED]'
    return d

def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--date', default=dt.date.today().strftime('%Y%m%d'), help='PT date YYYYMMDD of the games')
    ap.add_argument('--season', type=int, default=2026); ap.add_argument('--asof', default=None, help='UTC ISO; default now')
    a = ap.parse_args(); asof = a.asof or dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    snap = pd.read_csv(os.path.join(ROOT, 'lines', 'snapshots.csv'), dtype={'event_id': str, 'date_pt': str})
    snap = snap[(snap.date_pt == a.date) & (snap.state == 'pre') & (snap.captured_utc <= asof)]
    if snap.empty: sys.exit(f'no pre-game DK snapshots for {a.date} at or before {asof}')
    last = snap.sort_values('captured_utc').groupby('event_id').tail(1)
    G = load(a.season); F = fit(G, a.season, min(last.kickoff_utc.min().replace('Z', ''), asof[:19]))
    # neutral flag for the target games from the latest raw scoreboard
    neu = {}
    for f in sorted(glob.glob(os.path.join(ROOT, 'lines', 'raw', a.date, 'scoreboard_*.json')))[-1:]:
        for e in json.load(open(f)).get('events', []): neu[e['id']] = bool(e['competitions'][0].get('neutralSite'))
    last = last.assign(neutral=last.event_id.map(neu).fillna(False))
    rows = [x for _, r in last.iterrows() for x in game_evidence(F, r)]
    X = pd.DataFrame(rows); os.makedirs(os.path.join(HERE, 'out'), exist_ok=True)
    base = os.path.join(HERE, 'out', f'cfb_evidence_{a.date}_{dt.datetime.now():%H%M}')
    X.to_csv(base + '.csv', index=False)
    hdr = (f'CFB game-line evidence (shadow/context only, UNTESTED vs any market) - {len(last)} games, ratings from '
           f'{F["n_games"]} final games (2026 weight 1.0, 2025 weight {PRIOR_W}); HFA {F["hfa"]:.1f} pts (prior {F["hfa_prior"]:.1f}); asof {asof}')
    open(base + '.txt', 'w').write(hdr + '\n' + '\n'.join(X.sort_values(['agrees_n'], ascending=False).evidence_summary) + '\n')
    print(hdr); print(X.groupby('market').agrees_n.value_counts().sort_index().to_string()); print('->', base + '.csv / .txt')

if __name__ == '__main__': main()
