"""Independent rebuild of NHL books (no-vig Fliff vs DK) + leak guard + rest presence + n/a note + majority 4-of-7."""
import os, sys, json, glob, re, unicodedata
import numpy as np, pandas as pd
from openpyxl import load_workbook
OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NHL = os.path.join(OUT, 'data', 'nhl')
CAP = os.path.join(NHL, 'captures')

def am2p(a):
    a = float(a); return -a/(-a+100) if a < 0 else 100/(a+100)

def norm(x):
    return re.sub(r'[^a-z]', '', unicodedata.normalize('NFKD', str(x)).encode('ascii','ignore').decode().lower())

def load_fliff(date, asof_hhmm):
    """Independent: same interface as Yinzer's _fliff."""
    fs = sorted(glob.glob(os.path.join(CAP, f'fliff_{date}_*.json')))
    fs = [f for f in fs if os.path.basename(f).split('_')[2] <= asof_hhmm]
    out = {}
    for f in fs:
        try: d = json.load(open(f))
        except Exception: continue
        for bk in d.get('bookmakers', []):
            if bk.get('key') != 'fliff': continue
            for m in bk.get('markets', []):
                if m.get('key') != 'player_shots_on_goal': continue
                tmp = {}
                for o in m.get('outcomes', []):
                    tmp.setdefault((norm(o.get('description')), float(o['point'])), {})[o['name'].lower()] = o['price']
                for (p, pt), v in tmp.items():
                    if 'over' in v and 'under' in v:
                        out.setdefault(p, {})[pt] = (v['over'], v['under'])
    return out, [os.path.basename(f) for f in fs]

def books_mine(r, side, fliff):
    lines = fliff.get(norm(r['player']))
    if not lines: return 0, 'n/a no fliff', None
    ln = float(r['line']); o = side == 'over'
    if ln in lines:
        fo, fu = lines[ln]
        po, pu = am2p(fo), am2p(fu)
        nvf = po/(po+pu); nvf = nvf if o else 1-nvf
        nvd = r['nv_over'] if o else 1-r['nv_over']; d = nvf - nvd
        return (1 if d > 0.02 else (-1 if d < -0.02 else 0)), f'same-line nvf={nvf:.3f} nvd={nvd:.3f} d={d*100:+.1f}', ('same', ln, fo, fu, nvf, nvd, d)
    fl = min(lines, key=lambda x: abs(x-ln))
    lean = (fl > ln) if o else (fl < ln)
    return (1 if lean else -1), f'line-lean fl={fl} dk={ln}', ('lean', fl, ln, lean)

# --- 1) Nov 4: with asof including 1532 (historic check Yinzer claims 6/6) and with leak-guard asof ---
rows = []
for picks_file, pass_hhmm in [('20261104_D_1305.csv','1305'), ('20261104_D_1531.csv','1531')]:
    P = pd.read_csv(os.path.join(NHL, picks_file))
    # asof from captured_utc (live leak guard)
    t = pd.to_datetime(P.get('captured_utc'), utc=True, errors='coerce').max()
    asof_live = t.tz_convert('America/Los_Angeles').strftime('%H%M') if pd.notna(t) else pass_hhmm
    for asof_label, asof in [('live_asof', asof_live), ('pass_hhmm', pass_hhmm), ('incl_1532', '1532'), ('eod', '2359')]:
        fliff, used = load_fliff('20261104', asof)
        for _, r in P.iterrows():
            for side in ('over','under'):
                s, why, meta = books_mine(r, side, fliff)
                rows.append(dict(file=picks_file, asof_label=asof_label, asof=asof, n_fliff_files=len(used),
                                 player=r.player, nhl_id=r.nhl_id, line=r.line, side=side,
                                 nv_over=r.nv_over, dk_over=r.over, dk_under=r.under,
                                 sign=s, why=why, meta=str(meta)))
O = pd.DataFrame(rows)
O.to_csv(os.path.join(OUT, 'nhl_books_nov4.csv'), index=False)

print('=== NHL books Nov 4 ===')
for lab in O.asof_label.unique():
    sub = O[O.asof_label==lab]
    nz = sub[sub.sign!=0]
    print(f'{lab} asof={sub['asof'].iloc[0]} fliff_files={sub['n_fliff_files'].iloc[0]} nonzero={len(nz)} +={(nz.sign==1).sum()} -={(nz.sign==-1).sum()}')
    if len(nz):
        print(nz[['file','player','side','line','sign','why']].to_string(index=False))

# Same-line symmetry check on incl_1532
sub = O[O.asof_label=='incl_1532']
# pair over/under
pairs = []
for (f,p,ln), g in sub.groupby(['file','player','line']):
    ov = g[g.side=='over'].sign.iloc[0]; un = g[g.side=='under'].sign.iloc[0]
    pairs.append((f,p,ln,ov,un, ov==-un if (ov!=0 or un!=0) else True))
print('pair opposite-sign (or both 0) fails:', sum(1 for x in pairs if not x[5]), 'of', len(pairs))
print('nonzero pairs:', [(p,ln,ov,un) for f,p,ln,ov,un,ok in pairs if ov or un])

# Vig-bias check: compare old vig method vs new no-vig on same data
print('\n=== vig bias check (old method would juice-compare) ===')
fliff, _ = load_fliff('20261104', '2359')
# Also load DK two-sided from the JSON for comparison? We have nv_over in picks.
# Old buggy: compare am2p(fliff_side_price) to am2p(dk_side_price) without de-vig
old_plus = old_minus = new_plus = new_minus = 0
P = pd.read_csv(os.path.join(NHL, '20261104_D_1531.csv'))
for _, r in P.iterrows():
    lines = fliff.get(norm(r.player))
    if not lines or float(r.line) not in lines: continue
    fo, fu = lines[float(r.line)]
    for side in ('over','under'):
        o = side=='over'
        # old
        fp = fo if o else fu; dk = r.over if o else r.under
        d_old = am2p(fp) - am2p(dk)
        s_old = 1 if d_old>0.02 else (-1 if d_old<-0.02 else 0)
        # new
        po, pu = am2p(fo), am2p(fu); nvf = po/(po+pu); nvf = nvf if o else 1-nvf
        nvd = r.nv_over if o else 1-r.nv_over; d = nvf-nvd
        s_new = 1 if d>0.02 else (-1 if d<-0.02 else 0)
        if s_old>0: old_plus+=1
        if s_old<0: old_minus+=1
        if s_new>0: new_plus+=1
        if s_new<0: new_minus+=1
print(f'Nov4 D_1531 same-line: OLD vig +{old_plus}/-{old_minus}; NEW novig +{new_plus}/-{new_minus}')

# --- 2) Broader historic: all D files we copied, asof=eod (to match 'had fliff') AND asof=pass (leak) ---
hist = []
for f in sorted(glob.glob(os.path.join(NHL, '2026*_D_[0-9][0-9][0-9][0-9].csv'))):
    b = os.path.basename(f); date, hhmm = b[:8], b[11:15]
    P = pd.read_csv(f)
    t = pd.to_datetime(P.get('captured_utc'), utc=True, errors='coerce').max()
    asof_live = t.tz_convert('America/Los_Angeles').strftime('%H%M') if pd.notna(t) else hhmm
    for lab, asof in [('live', asof_live), ('eod', '2359')]:
        fliff, used = load_fliff(date, asof)
        if not fliff and lab=='eod': continue
        for _, r in P.iterrows():
            for side in ('over','under'):
                s, why, meta = books_mine(r, side, fliff)
                if s != 0 or (lab=='eod' and fliff.get(norm(r.player))):
                    hist.append(dict(file=b, lab=lab, asof=asof, player=r.player, side=side, line=r.line, sign=s, why=why))
H = pd.DataFrame(hist)
H.to_csv(os.path.join(OUT, 'nhl_books_historic.csv'), index=False)
for lab in ('live','eod'):
    sub = H[H.lab==lab]; nz=sub[sub.sign!=0]
    print(f'\nhistoric {lab}: rows_logged={len(sub)} nonzero={len(nz)} +={(nz.sign==1).sum()} -={(nz.sign==-1).sum()}')
# Check any live nonzero that used fliff AFTER pass
# For each live nonzero, check if fliff HHMM > asof
print('live nonzero detail (should be rare / only if fliff pulled before sheet):')
print(H[(H.lab=='live')&(H.sign!=0)][['file','asof','player','side','line','sign','why']].head(40).to_string(index=False) if len(H[(H.lab=='live')&(H.sign!=0)]) else '  (none)')

# --- 3) Confirm EXTRA has rest; simulate n/a note ---
sys.path.insert(0, OUT)
# Load evidence_extra from our copy but point HERE to data/nhl so captures resolve
import importlib.util
spec = importlib.util.spec_from_file_location('ee', os.path.join(OUT, 'nhl_evidence_extra.py'))
ee = importlib.util.module_from_spec(spec)
# Patch HERE before exec? The module sets HERE at import from __file__ dir = OUT
# But captures are in data/nhl/captures. So monkeypatch after load.
spec.loader.exec_module(ee)
print('\nEXTRA keys:', list(ee.EXTRA.keys()), 'tests_all would be', 7+len(ee.EXTRA))
assert 'rest' in ee.EXTRA and 'books' in ee.EXTRA and 'hit' in ee.EXTRA

# Point _fliff / schedule at our data copy
ee.HERE = NHL  # so captures/ under data/nhl works

# Simulate schedule failure -> n/a note
P = pd.read_csv(os.path.join(NHL, '20261104_D_1531.csv')).head(2)
# Fake base agrees_n
base = pd.DataFrame([dict(nhl_id=r.nhl_id, line=r.line, side=s, agrees_n=3)
                     for _, r in P.iterrows() for s in ('over','under')])
# Break schedule
_real = ee._schedule
def _boom(iso):
    raise TimeoutError('simulated timeout')
ee._schedule = _boom
# Minimal logs for hit/rest
logs = pd.DataFrame(columns=['playerId','gameDate','shots','gameId'])
# Need nhl_id match empty -> rest n/a no prior; hit n/a
out = ee.annotate(P, '20261104', base=base, logs=logs, asof_hhmm='1300')  # before 1532 -> books n/a
print('\n=== n/a simulation (schedule timeout + asof before fliff) ===')
for _, r in out.iterrows():
    print(r.player if 'player' in r else r.nhl_id, r.side, 'sig_x_rest', r.sig_x_rest, 'sig_x_books', r.sig_x_books,
          '|', r.evidence_all_summary)
    assert 'n/a:' in r.evidence_all_summary, 'n/a note missing!'
    assert 'rest n/a' in r.evidence_all_summary or 'schedule' in r.evidence_all_summary
print('n/a note PASS')
ee._schedule = _real

# --- 4) Majority 4-of-7 unchanged on Nov 5 sheet ---
wb = load_workbook(os.path.join(NHL, '20261105_D_1239_picks.xlsx'), read_only=True, data_only=True)
ws = wb['Picks']; rows = list(ws.iter_rows(values_only=True)); hdr = list(rows[0])
ai = hdr.index('agrees_n'); si = hdr.index('side') if 'side' in hdr else None
# count sides with agrees_n >= 4; sheet has one row per side already?
df = pd.DataFrame(rows[1:], columns=hdr)
# filter to real pick rows
df = df[df['agrees_n'].notna()]
maj = df[pd.to_numeric(df['agrees_n'], errors='coerce') >= 4]
print(f'\nNov5 1239 sheet: rows={len(df)} majority 4+ of 7 = {len(maj)} (expected 67)')
# statuses
if 'status' in df:
    print('status counts:', df.status.value_counts().to_dict())
# ensure no agrees_all / tests_all columns that would have changed the card
extra_cols = [c for c in hdr if c and ('all' in str(c).lower() or str(c).startswith('sig_x_'))]
print('extra/new cols on sheet:', extra_cols)
# Card: Fliff check / DK bet counts
print('done nhl script')
