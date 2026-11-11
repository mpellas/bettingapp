"""Posted-list paper track by list (added 2026-10-21, room request). Reads picks/<date>_<HHMM>_post.txt ('Fliff check' lines),
outcomes from graded/<date>.csv (actual shots from grade.py's NHL API pull), Fliff price from fliff_prices/<date>_*.csv
(capture whose list_file matches this list; never a DK price). Flat 1 u per posted side, as posted (before tester skips).
Lists from 20261020_1513 on carry the 5-pt edge floor (commit 3f24324); earlier lists are pre-floor.
Usage: python3 list_track.py [YYYYMMDD ...]  -> prints markdown"""
import re, glob, os, sys
import numpy as np, pandas as pd
os.chdir(os.path.dirname(os.path.abspath(__file__)))
FLOOR_FROM = '20261020_1513'
PAT = re.compile(r'^Fliff check: (.+?) (OVER|UNDER) ([\d.]+) \(DK ([+-]?\d+), Fliff at ([+-]?\d+) or better\)')
dec = lambda a: 1 + (a / 100 if a > 0 else 100 / -a)
def rows(dates):
    R = []
    for d in dates:
        gp = f'graded/{d}.csv'
        if not os.path.exists(gp): continue
        G = pd.read_csv(gp)
        F = pd.concat([pd.read_csv(f) for f in glob.glob(f'fliff_prices/{d}_*.csv')] or [pd.DataFrame()], ignore_index=True)
        for pf in sorted(glob.glob(f'picks/{d}_*_post.txt')):
            stamp = os.path.basename(pf)[:13]
            for ln in open(pf):
                m = PAT.match(ln)
                if not m: continue
                pl, side, line, dk, shop = m.group(1), m.group(2), float(m.group(3)), int(m.group(4)), int(m.group(5))
                g = G[(G.player == pl) & (G.line == line)]
                act = g.actual.dropna().iloc[0] if len(g.actual.dropna()) else np.nan
                fp = np.nan
                if len(F):
                    f = F[(F.player == pl) & (F.side == side) & (F.list_file.astype(str).str.replace('_D_', '_', regex=False).str.startswith(stamp)) & (F.fliff_status == 'offered') & (F.fliff_line == line)]
                    if len(f): fp = float(f.fliff_price.iloc[-1])
                hit = np.nan if np.isnan(act) else int(act > line if side == 'OVER' else act < line)
                R.append(dict(list=stamp, era='post-floor' if stamp >= FLOOR_FROM else 'pre-floor', player=pl, side=side, line=line,
                              dk=dk, shop_at=shop, fliff=fp, actual=act, hit=hit,
                              u_dk=np.nan if np.isnan(hit) else (dec(dk) - 1 if hit else -1.0),
                              u_fliff=np.nan if np.isnan(hit) or np.isnan(fp) else (dec(fp) - 1 if hit else -1.0)))
    return pd.DataFrame(R)
def md(dates):
    R = rows(dates); L = ['## Posted lists by list (as posted, before tester skips): pre-floor vs post-floor', '']
    if R.empty: return L + ['No posted lists.']
    L += ['| slice | sides | graded | W-L | units @ DK list price | Fliff offered & graded | W-L @ Fliff | units @ captured Fliff |', '|---|---|---|---|---|---|---|---|']
    def line(lbl, r):
        g = r.dropna(subset=['hit']); f = g.dropna(subset=['u_fliff'])
        return (f'| {lbl} | {len(r)} | {len(g)} | {int(g.hit.sum())}-{int(len(g) - g.hit.sum())} | {g.u_dk.sum():+.2f} u | {len(f)} | '
                f'{int(f.hit.sum())}-{int(len(f) - f.hit.sum())} | {f.u_fliff.sum():+.2f} u |')
    for s, r in R.groupby('list'): L.append(line(f'{s} ({r.era.iloc[0]})', r))
    for e in ('pre-floor', 'post-floor'): L.append(line(f'**all {e}**', R[R.era == e]))
    L += ['', '| list | side | DK | shop-at | captured Fliff | shots | result |', '|---|---|---|---|---|---|---|']
    for _, x in R.iterrows():
        L.append(f'| {x.list} | {x.player} {x.side} {x.line} | {x.dk:+d} | {x.shop_at:+d} | {"" if np.isnan(x.fliff) else f"{int(x.fliff):+d}"} | '
                 f'{"" if np.isnan(x.actual) else int(x.actual)} | {"pending/void" if np.isnan(x.hit) else ("W" if x.hit else "L")} |')
    L += ['', f'Pre-floor = lists before {FLOOR_FROM} (5-pt edge floor, commit 3f24324). Fliff units use only prices fliff_prices.py captured for that list; '
          'sides with no captured Fliff offer are not graded at Fliff (no DK substitution). Paper only.']
    return L
if __name__ == '__main__': print('\n'.join(md(sys.argv[1:] or ['20261018', '20261019', '20261020'])))
