"""Paper-only challenger: NHL SOG model shrunk 50% toward DK no-vig in logit space.

  p_ch_over = sigmoid(0.5*logit(p_model_over) + 0.5*logit(nv_over))
  p_blend_ch = 0.95*nv_over + 0.05*p_ch_over ;  ev_ch = p_blend_ch*dec(DK price) - 1
Everything else (gates, thin edge, 5-pt floor, 12-pt band, top-5 cap, shop_at) is the unchanged
build_sheet.build_rows/assign_status from a COPY of nhl-sog (src/). Only p_model_over/p_blend_over/ev_* are swapped.

Usage:
  python3 shadow_shrink50.py slate <picks.csv> <gate.csv> [--out sides.csv]
  python3 shadow_shrink50.py --backtest [--through 20261030]
"""
import os, sys, glob, json, re, argparse, math
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); SRC = os.path.join(HERE, 'src')
assert '/workspace/nhl-sog' not in os.path.realpath(SRC)
sys.path.insert(0, SRC)
import build_sheet as bs
bs.shrink = None; bs.evidence = None   # display-only modules; not used for status
W_SHRINK, W_BOOK = 0.5, 0.95
lg = lambda p: np.log(np.clip(p, 1e-6, 1-1e-6) / (1 - np.clip(p, 1e-6, 1-1e-6)))
sg = lambda z: 1 / (1 + np.exp(-z))
def dec(a): a = float(a); return 1 + a/100 if a > 0 else 1 + 100/-a

def challenger(picks):
    p = picks.copy()
    p['p_model_over'] = sg((1-W_SHRINK)*lg(p.p_model_over) + W_SHRINK*lg(p.nv_over))
    p['p_blend_over'] = W_BOOK*p.nv_over + (1-W_BOOK)*p.p_model_over
    p['ev_over'] = [pb*dec(o)-1 for pb, o in zip(p.p_blend_over, p.over)]
    p['ev_under'] = [(1-pb)*dec(u)-1 for pb, u in zip(p.p_blend_over, p.under)]
    return p

def run(picks, gate):
    picks = picks[picks.p_model_over.notna() & picks.nv_over.notna()].reset_index(drop=True)
    out = {}
    for tag, pk in (('live', picks), ('ch', challenger(picks))):
        d = bs.build_rows(pk, gate, '', None)
        d['side'] = d.side.str.lower()
        d['edge_pts'] = (d.p_model - d.p_novig) * 100   # display edge (rounded probs)
        out[tag] = d
    L, Ch = out['live'], out['ch']
    pm = picks.set_index(['player', 'line'])
    ch_over = sg(0.5*lg(picks.p_model_over) + 0.5*lg(picks.nv_over)).values
    chm = dict(zip(zip(picks.player, picks.line), ch_over))
    r = L[['game', 'player', 'side', 'line', 'dk_price']].copy()
    def e(row, pover):
        nv = pm.loc[(row.player, row.line)].nv_over; nv = nv.iloc[0] if hasattr(nv, 'iloc') else nv
        return 100*((pover - nv) if row.side == 'over' else (nv - pover))
    r['live_edge_pts'] = [e(x, (lambda v: v.iloc[0] if hasattr(v, 'iloc') else v)(pm.loc[(x.player, x.line)].p_model_over)) for x in L.itertuples()]
    r['ch_edge_pts'] = [e(x, chm[(x.player, x.line)]) for x in L.itertuples()]
    r['live_status'], r['live_reason'], r['live_shop_at'] = L.status, L.status_reason, L.fliff_shop_at
    r['ch_status'], r['ch_reason'], r['ch_shop_at'] = Ch.status.values, Ch.status_reason.values, Ch.fliff_shop_at.values
    r['live_list'] = r.live_status.ne('Skipped'); r['ch_list'] = r.ch_status.ne('Skipped')
    for c in ('live_edge_pts', 'ch_edge_pts'): r[c] = r[c].round(2)
    return r, picks

def pair(gatef):
    pf = gatef.replace('_GATE.csv', '.csv')
    return pf if os.path.exists(pf) else None

def starts():
    st = {}
    for f in glob.glob(SRC + '/captures/*/*.json'):
        try: d = json.load(open(f)); st[str(d['event'])] = pd.Timestamp(d['start_utc'].replace('Z', '+00:00'))
        except Exception: pass
    return st

def results():
    act = {}
    for f in glob.glob(SRC + '/graded/*.csv'):
        d = pd.read_csv(f)
        if not {'actual', 'nhl_id', 'gameId'} <= set(d.columns): continue
        for x in d.itertuples():
            if pd.notna(x.actual): act[(int(x.nhl_id), int(x.gameId))] = float(x.actual)
    for f in glob.glob(SRC + '/data/catchup_box/*.json'):
        d = json.load(open(f)); gid = int(os.path.basename(f).split('.')[0]) if os.path.basename(f).split('.')[0].isdigit() else None
        if gid is None or d.get('gameState') not in ('OFF', 'FINAL'): continue
        def walk(o):
            if isinstance(o, dict):
                if 'playerId' in o and 'sog' in o: act.setdefault((int(o['playerId']), gid), float(o['sog']))
                for v in o.values(): walk(v)
            elif isinstance(o, list):
                for v in o: walk(v)
        walk(d.get('playerByGameStats', d))
    return act

def backtest(through):
    st, act = starts(), results()
    rows, skipped = [], []
    for gf in sorted(glob.glob(SRC + '/picks/*_GATE.csv')):
        pf = pair(gf)
        if not pf: skipped.append((os.path.basename(gf), 'no matching picks file')); continue
        try:
            pk = pd.read_csv(pf, dtype={'event': str}); gt = pd.read_csv(gf, dtype={'event': str})
            r, pk2 = run(pk, gt)
        except Exception as ex:
            skipped.append((os.path.basename(gf), f'{type(ex).__name__}: {ex}'[:120])); continue
        meta = pk2[['player', 'line', 'nhl_id', 'gameId', 'event', 'captured_utc']].drop_duplicates(['player', 'line'])
        r = r.merge(meta, on=['player', 'line'], how='left'); r['pass'] = os.path.basename(gf); rows.append(r)
    a = pd.concat(rows, ignore_index=True)
    a['cap'] = pd.to_datetime(a.captured_utc, utc=True, format='mixed'); a['start'] = a.event.map(st)
    a['mins'] = (a.start - a.cap).dt.total_seconds() / 60
    a = a[(a.mins >= 150) | a.mins.isna()]
    a['date'] = a.start.fillna(a.cap).dt.tz_convert('America/Los_Angeles').dt.strftime('%Y%m%d')
    a = a[a.date <= through]
    last = a.groupby(['nhl_id', 'gameId']).cap.transform('max'); a = a[a.cap == last]
    a = a.drop_duplicates(['nhl_id', 'gameId', 'side', 'line'], keep='last')
    a['actual'] = [act.get((int(n), int(g))) for n, g in zip(a.nhl_id, a.gameId)]
    def u(x, price):
        if pd.isna(x.actual): return np.nan
        hit = x.actual > x.line if x.side == 'over' else x.actual < x.line
        return dec(price) - 1 if hit else -1.0
    a['W'] = [np.nan if pd.isna(x.actual) else int((x.actual > x.line) if x.side == 'over' else (x.actual < x.line)) for x in a.itertuples()]
    a['u_dk'] = [u(x, x.dk_price) for x in a.itertuples()]
    a['u_live_shop'] = [u(x, x.live_shop_at) for x in a.itertuples()]
    a['u_ch_shop'] = [u(x, x.ch_shop_at) for x in a.itertuples()]
    a.drop(columns=['cap', 'start']).to_csv(os.path.join(HERE, 'backtest_sides.csv'), index=False)
    out = []
    for nm, m, shop in (('live', a.live_list, 'u_live_shop'), ('challenger', a.ch_list, 'u_ch_shop'),
                        ('both', a.live_list & a.ch_list, 'u_ch_shop'), ('live_only', a.live_list & ~a.ch_list, 'u_live_shop'),
                        ('ch_only', a.ch_list & ~a.live_list, 'u_ch_shop')):
        x = a[m]; g = x[x.W.notna()]
        out.append(dict(list=nm, sides=len(x), ungraded=int(x.W.isna().sum()), W=int(g.W.sum()), L=int((1-g.W).sum()),
                        units_dk=round(g.u_dk.sum(), 2), units_shop_at=round(g[shop].sum(), 2),
                        overs=int((x.side == 'over').sum()), unders=int((x.side == 'under').sum())))
    s = pd.DataFrame(out); s.to_csv(os.path.join(HERE, 'backtest_summary.csv'), index=False)
    print(f'passes used: {len(rows)}; skipped: {len(skipped)}'); [print('  skip', *k) for k in skipped]
    print(f'player-games: {a.groupby(["nhl_id","gameId"]).ngroups}; side rows: {len(a)}')
    print(s.to_string(index=False))

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('mode', nargs='?'); ap.add_argument('picks', nargs='?'); ap.add_argument('gate', nargs='?')
    ap.add_argument('--out'); ap.add_argument('--backtest', action='store_true'); ap.add_argument('--through', default='20261030')
    a = ap.parse_args()
    if a.backtest: backtest(a.through)
    else:
        r, _ = run(pd.read_csv(a.picks, dtype={'event': str}), pd.read_csv(a.gate, dtype={'event': str}))
        if a.out: r.to_csv(a.out, index=False)
        cols = ['player', 'side', 'line', 'dk_price', 'live_edge_pts', 'ch_edge_pts', 'live_status', 'ch_status', 'live_shop_at', 'ch_shop_at']
        print(r[r.live_list | r.ch_list][cols].to_string(index=False) or 'no listed sides')
        print('live listed', int(r.live_list.sum()), '| challenger listed', int(r.ch_list.sum()), '| rows', len(r))
