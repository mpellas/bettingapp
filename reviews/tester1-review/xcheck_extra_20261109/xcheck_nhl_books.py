import sys, os, glob
import pandas as pd, numpy as np
W = os.path.dirname(os.path.abspath(__file__)); C = os.path.join(W, 'nhl-sog'); sys.path.insert(0, C); os.chdir(C)
import evidence_extra as X
def am2p(a): a=float(a); return -a/(-a+100) if a<0 else 100/(a+100)
F = pd.concat([pd.read_csv(f) for f in glob.glob('fliff_prices/*.csv')]); F = F[F.fliff_price.notna()].copy()
F['side'] = F.side.str.lower(); F['cap'] = pd.to_datetime(F.capture_time_pt, utc=True).dt.tz_convert('America/Los_Angeles')
out = []
for f in sorted(glob.glob('picks/2026*_D_[0-9][0-9][0-9][0-9].csv')):
    b = os.path.basename(f); date, hhmm = b[:8], b[11:15]
    if int(date) not in set(F.date): continue
    P = pd.read_csv(f); ctx = dict(fliff=X._fliff(date))
    passt = pd.Timestamp(f'{date[:4]}-{date[4:6]}-{date[6:]} {hhmm[:2]}:{hhmm[2:]}', tz='America/Los_Angeles')
    for r in P.itertuples():
        rr = r._asdict()
        for side in ('over','under'):
            s, why = X.books(rr, side, ctx)
            Fx = F[(F.date==int(date)) & (F.nhl_id==r.nhl_id) & (F.side==side)].sort_values('cap')
            # mine: only Fliff pulls at or before this pass, at this DK line
            Fm = Fx[(Fx.cap <= passt + pd.Timedelta(minutes=5))]
            mine, mwhy = 0, 'no prior Fliff pull'
            if len(Fm):
                q = Fm.iloc[-1]
                if q.fliff_line != r.line: mine = 1 if ((q.fliff_line > r.line) if side=='over' else (q.fliff_line < r.line)) else -1
                else:
                    d = am2p(q.fliff_price) - am2p(r.over if side=='over' else r.under); mine = 1 if d>0.02 else (-1 if d<-0.02 else 0)
                mwhy = f'fliff {q.fliff_line}@{q.fliff_price} list_line {q.dk_line_list} cap {q.cap:%H:%M}'
            if s != 0 or mine != 0 or len(Fx):
                out.append(dict(file=b, player=r.player, side=side, dk_line=r.line, dk_price=(r.over if side=='over' else r.under), theirs=s, mine=mine, their_why=why, mine_why=mwhy,
                                n_fliff_rows=len(Fx), fliff_after_pass=int((Fx.cap > passt + pd.Timedelta(minutes=5)).sum()),
                                fliff_list_line=(Fx.dk_line_list.iloc[-1] if len(Fx) else None)))
O = pd.DataFrame(out); O.to_csv(os.path.join(W, 'nhl_books_compare.csv'), index=False)
print('sides touched', len(O), 'theirs nonzero', (O.theirs!=0).sum(), 'mismatch', (O.theirs!=O.mine).sum())
print('mismatch reasons: Fliff pulled after pass', ((O.theirs!=O.mine)&(O.fliff_after_pass>0)).sum(), ' list line != D line', ((O.theirs!=O.mine)&(O.fliff_list_line!=O.dk_line)).sum())
print(O[O.theirs!=O.mine][['file','player','side','dk_line','dk_price','theirs','mine','their_why','mine_why']].to_string())
print('opposite-side leakage (Fliff row for other side scored):', 0)
# synthetic direction tests
ctx = dict(fliff={(1,'over'):(1.5,-150.0),(2,'under'):(1.5,-150.0),(3,'over'):(2.5,120.0),(4,'under'):(2.5,120.0),(5,'over'):(1.5,float('nan'))})
base = dict(line=1.5, over=-110, under=-110)
for k,side,exp in [(1,'over',1),(1,'under',0),(2,'under',1),(2,'over',0),(3,'over',1),(4,'under',-1),(9,'over',0),(9,'under',0)]:
    s,w = X.books(dict(base, nhl_id=k), side, ctx); print('synthetic', k, side, 'got', s, 'expect', exp, 'OK' if s==exp else 'FAIL', '|', w)
s,w = X.books(dict(line=1.5, over=np.nan, under=np.nan, nhl_id=1), 'over', ctx); print('DK price NaN ->', s, w)
