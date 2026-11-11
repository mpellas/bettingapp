"""Backtests (paper). Part 1: live DK lines Oct 11 - Nov 5 2026 at D price. Part 2: 2025-26 proxy (no prices).
Writes out/backtest_live_sides.csv, out/backtest_live_summary.csv, out/backtest_proxy_summary.csv; prints tables."""
import os, sys, glob, re
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, 'vendor'))
NHL = '/workspace/nhl-sog'
import evidence_extra as EE, tester1_extra as T1
from att_signal import _norm
from sample_nov5_logs import yinzer_logs
EE.HERE = NHL
rng = np.random.default_rng(20261109)

def wilson(k, n, z=1.96):
    if n == 0: return (np.nan, np.nan)
    p = k / n; d = 1 + z*z/n; c = (p + z*z/(2*n)) / d; h = z*np.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return c - h, c + h
def profit(price, win):
    price = float(price); return (100/abs(price) if price < 0 else price/100) if win else -1.0
def boot_roi(df, B=2000):
    if len(df) == 0: return (np.nan, np.nan)
    g = df.groupby('gameId').agg(u=('units', 'sum'), n=('units', 'size')); u, n = g.u.values, g.n.values; m = len(g)
    idx = rng.integers(0, m, (B, m)); r = u[idx].sum(1) / n[idx].sum(1)
    return np.percentile(r, 2.5), np.percentile(r, 97.5)
def summ(df, label):
    n = len(df); k = int(df.win.sum()); lo, hi = wilson(k, n); rl, rh = boot_roi(df)
    return dict(group=label, sides=n, games=df.gameId.nunique() if n else 0, wins=k, hit=k/n if n else np.nan, hit_lo=lo, hit_hi=hi,
                units=df.units.sum(), roi=df.units.sum()/n if n else np.nan, roi_lo=rl, roi_hi=rh)

def agrees_map():
    m = {}
    for f in sorted(glob.glob(f'{NHL}/sheets/2026*_picks.xlsx')):
        d = re.match(r'(\d{8})', os.path.basename(f)).group(1)
        try: S = pd.read_excel(f, sheet_name='Picks')
        except Exception: continue
        if 'agrees_n' not in S: continue
        for p, s, l, a in zip(S.player, S.side.astype(str).str.lower(), S.line, S.agrees_n):
            if pd.notna(a): m[(d, _norm(p), float(l), s)] = int(a)   # later sheets same day overwrite (same game rows are byte-identical)
    E = pd.read_csv(f'{NHL}/shadow/backtest_evidence_rows.csv')
    for d, p, l, s, a in zip(E.date.astype(str), E.player, E.line, E.side, E.agrees_n):
        m.setdefault((d, _norm(p), float(l), s), int(a))
    return m

def live():
    L = yinzer_logs(); AM = agrees_map(); rows = []
    for f in sorted(glob.glob(f'{NHL}/graded/2026*.csv')):
        date = os.path.basename(f)[:8]
        G = pd.read_csv(f)
        G = G[G.actual.notna() & ~G.status.isin(['VOID_dnp', 'VOID_pulled_before_close'])].copy()
        if not len(G): continue
        EE.EXTRA.update(T1.EXTRA_T1)
        A = EE.annotate(G, date, base=None, logs=L)
        for k in ['att', 'total']: EE.EXTRA.pop(k)
        G2 = pd.concat([G.assign(side='over'), G.assign(side='under')])
        M = G2.merge(A, on=['nhl_id', 'line', 'side'], how='left')
        M['date'] = date
        rows.append(M)
    D = pd.concat(rows, ignore_index=True)
    ctxs = {}
    def na(fn, r):
        c = ctxs.setdefault(r.date, dict(logs=L, iso=f'{r.date[:4]}-{r.date[4:6]}-{r.date[6:]}', t1=ctxs.get('_t1')))
        if c.get('t1') is None: c.pop('t1')
        out = fn(r, 'over', c)[1].startswith('n/a'); ctxs['_t1'] = c.get('t1'); return out
    U = D.drop_duplicates(['date', 'nhl_id', 'line']).copy()
    U['att_na'] = [na(T1.att, r) for _, r in U.iterrows()]; U['total_na'] = [na(T1.total, r) for _, r in U.iterrows()]
    D = D.merge(U[['date', 'nhl_id', 'line', 'att_na', 'total_na']], on=['date', 'nhl_id', 'line'], how='left')
    print('n/a share: att', round(U.att_na.mean(), 3), 'total', round(U.total_na.mean(), 3))
    D['price'] = np.where(D.side == 'over', D.over, D.under).astype(float)
    D['win'] = np.where(D.side == 'over', D.actual > D.line, D.actual < D.line)
    D['units'] = [profit(p, w) for p, w in zip(D.price, D.win)]
    D['of_7'] = [AM.get((d, _norm(p), float(l), s)) for d, p, l, s in zip(D.date, D.player, D.line, D.side)]
    for c in ['hit', 'books', 'rest', 'att', 'total']: D[f'p_{c}'] = (D[f'sig_x_{c}'] == '+').astype(int)
    D['of_8_att'] = D.of_7 + D.p_att; D['of_8_total'] = D.of_7 + D.p_total
    D['of_10'] = D.of_7 + D.p_hit + D.p_books + D.p_rest; D['of_9_t1'] = D.of_7 + D.p_att + D.p_total
    D['of_12'] = D.of_10 + D.p_att + D.p_total
    keep = ['date', 'gameId', 'game', 'player', 'nhl_id', 'line', 'side', 'price', 'actual', 'win', 'units', 'status', 'of_7',
            'sig_x_hit', 'sig_x_books', 'sig_x_rest', 'sig_x_att', 'sig_x_total', 'of_10', 'of_12', 'att_na', 'total_na']
    D[keep].to_csv(os.path.join(HERE, 'out', 'backtest_live_sides.csv'), index=False)
    out = [summ(D, 'ALL sides')]
    for sig in ['att', 'total', 'hit']:
        for v in '+-0':
            out.append(summ(D[D[f'sig_x_{sig}'] == v], f'{sig} {v}'))
        for sd in ['over', 'under']:
            for v in '+-0':
                x = D[(D[f'sig_x_{sig}'] == v) & (D.side == sd)]
                if len(x): out.append(summ(x, f'{sig} {v} ({sd} sides)'))
    E = D[D.of_7.notna()]
    out.append(summ(E, 'sides with known of_7'))
    out.append(summ(E[E.of_7 >= 4], 'majority 4+ of 7'))
    for sig in ['att', 'total']:
        for v in '+-0': out.append(summ(E[(E.of_7 >= 4) & (E[f'sig_x_{sig}'] == v)], f'4+ of 7 & {sig} {v}'))
        out.append(summ(E[E[f'of_8_{sig}'] >= 5], f'majority 5+ of 8 (7 + {sig})'))
    out.append(summ(E[E.of_10 >= 6], 'majority 6+ of 10 (current EXTRA: hit, books, rest)'))
    out.append(summ(E[E.of_9_t1 >= 5], 'majority 5+ of 9 (7 + att,total)'))
    out.append(summ(E[E.of_12 >= 7], 'majority 7+ of 12 (10 + att, total)'))
    # paired contrast within side: '+' minus '-' (hit pts and ROI), game-clustered bootstrap
    con = []
    for sig in ['att', 'total', 'hit']:
        for sd in ['over', 'under']:
            x = D[(D.side == sd) & D[f'sig_x_{sig}'].isin(['+', '-'])]
            gid = x.gameId.unique(); grp = {g: d for g, d in x.groupby('gameId')}
            def stat(d):
                p, m = d[d[f'sig_x_{sig}'] == '+'], d[d[f'sig_x_{sig}'] == '-']
                return p.win.mean() - m.win.mean(), p.units.mean() - m.units.mean()
            est = stat(x); bs = []
            for _ in range(1000):
                d = pd.concat([grp[g] for g in rng.choice(gid, len(gid))]); bs.append(stat(d))
            bs = np.array(bs)
            con.append(dict(signal=sig, side=sd, n_plus=int((x[f'sig_x_{sig}'] == '+').sum()), n_minus=int((x[f'sig_x_{sig}'] == '-').sum()),
                            hit_diff=est[0], hit_diff_lo=np.nanpercentile(bs[:, 0], 2.5), hit_diff_hi=np.nanpercentile(bs[:, 0], 97.5),
                            roi_diff=est[1], roi_diff_lo=np.nanpercentile(bs[:, 1], 2.5), roi_diff_hi=np.nanpercentile(bs[:, 1], 97.5)))
    C = pd.DataFrame(con); C.to_csv(os.path.join(HERE, 'out', 'backtest_live_contrasts.csv'), index=False)
    print(C.round(3).to_string(index=False))
    S = pd.DataFrame(out); S.to_csv(os.path.join(HERE, 'out', 'backtest_live_summary.csv'), index=False)
    pd.set_option('display.width', 250)
    print(S.round(3).to_string(index=False))
    print('dates', D.date.min(), D.date.max(), 'lines', len(D)//2, 'of_7 known sides', len(E), 'dates with of_7', sorted(E.date.unique()))
    return D

if __name__ == '__main__': live()
