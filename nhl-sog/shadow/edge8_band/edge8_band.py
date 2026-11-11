"""Edge-8 price-band shadow (paper only, forward from 2026-10-31; user asked Oct 31 to keep watching it).
Rule (same as weekly review 2026-10-31 sec. 5 item 1): Fliff-check candidate side (status_reason 'model +...') on a window
pass, model minus no-vig >= 8.0 pts (sheet p_model - p_novig), captured DK price between -150 and +110 inclusive -> 1u at DK.
Latest in-window pass (captured >= 150 min before NHL.com start) per player-game. Also logs a wider 'board' variant (any side,
any status, same edge/price test) as a secondary column; the deciding tally is the candidate rule.
Reads /workspace/nhl-sog/sheets and picks (read-only). Never places bets, never changes live rules, no Odds API.
Usage: python3 edge8_band.py YYYYMMDD [YYYYMMDD ...]"""
import sys, os, glob, re
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nhlbox as nb
NHL = '/workspace/nhl-sog'; HERE = os.path.dirname(os.path.abspath(__file__))
def rows(date):
    out = []
    for f in sorted(glob.glob(f'{NHL}/sheets/{date}_D_*_picks.xlsx')):
        p = re.search(r'_D_(\d{4})_picks', f)[1]
        s = pd.read_excel(f, sheet_name='Picks')
        pk = pd.read_csv(f'{NHL}/picks/{date}_D_{p}.csv')[['player', 'line', 'nhl_id', 'gameId', 'captured_utc']].drop_duplicates(['player', 'line'])
        s = s.merge(pk, on=['player', 'line'], how='left'); s['pass'] = f'{date}_{p}'; out.append(s)
    if not out: return pd.DataFrame()
    a = pd.concat(out, ignore_index=True); a = a[a.nhl_id.notna()]
    a['cap'] = pd.to_datetime(a.captured_utc, utc=True, format='mixed')
    st = {g: nb.start_utc(g) for g in a.gameId.unique()}
    a['mins_before'] = [(st[g] - c).total_seconds()/60 for g, c in zip(a.gameId, a.cap)]
    a = a[a.mins_before >= 150]
    a = a[a.cap == a.groupby(['nhl_id', 'gameId']).cap.transform('max')]
    a['edge_pts'] = ((a.p_model - a.p_novig)*100).round(2)
    a['in_band'] = (a.dk_price >= -150) & (a.dk_price <= 110)
    a['candidate'] = a.status_reason.astype(str).str.startswith('model +')
    a['rule_edge8_band'] = a.candidate & (a.edge_pts >= 8) & a.in_band
    a['board_edge8_band'] = (a.edge_pts >= 8) & a.in_band
    a = a[a.board_edge8_band].copy(); a['date'] = date
    return a[['date', 'pass', 'game', 'player', 'nhl_id', 'gameId', 'side', 'line', 'dk_price', 'fliff_shop_at', 'edge_pts',
              'status', 'status_reason', 'mins_before', 'candidate', 'rule_edge8_band', 'board_edge8_band']]
if __name__ == '__main__':
    new = pd.concat([rows(d) for d in sys.argv[1:]], ignore_index=True)
    tally = os.path.join(HERE, 'tally.csv')
    if len(new): nb.append_tally(tally, nb.grade(new), ['date', 'nhl_id', 'gameId', 'side', 'line'])
    T = pd.read_csv(tally) if os.path.exists(tally) else pd.DataFrame()
    if len(T):  # regrade anything pending
        pend = T.result.isin(['PENDING'])
        if pend.any(): T = pd.concat([T[~pend], nb.grade(T[pend].drop(columns=['actual', 'result', 'u_dk_price']))], ignore_index=True); T.to_csv(tally, index=False)
        s = pd.DataFrame([dict(tracker='edge8_band (candidates, deciding)', **nb.summary(T, T.rule_edge8_band.astype(bool), 'u_dk_price')),
                          dict(tracker='edge8_band (any board side, secondary)', **nb.summary(T, T.board_edge8_band.astype(bool), 'u_dk_price'))])
    else:
        s = pd.DataFrame([dict(tracker='edge8_band (candidates, deciding)', sides=0, graded=0, W=0, L=0, units=0.0, roi_pct=0.0, pending=0)])
    s.to_csv(os.path.join(HERE, 'summary.csv'), index=False)
    print(new.drop(columns=['status_reason']).to_string(index=False) if len(new) else 'no edge8 band sides'); print(s.to_string(index=False))
