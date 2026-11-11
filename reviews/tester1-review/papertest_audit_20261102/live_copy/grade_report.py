"""Grading report with CLV as the PRIMARY score (approved 2026-10-16). Reads graded/<date>.csv (from grade.py).
Primary : mean z-CLV of the frozen model's lean side (p_model_over vs D no-vig), status OK rows with a close.
          z-CLV = side-signed logit(no-vig at C, re-expressed at the D line) - logit(no-vig at D).
          95% CI = game-clustered bootstrap (2000 draws, seed 0). Also by lean size (>= 5 pts).
Secondary: hit rate vs market-implied rate of the same sides (hit minus implied, binomial SE), and
          picks/units if the D file carried picks. Small samples are labeled: CI crossing 0 = 'no evidence'.
Model-only paper track (added 2026-10-17, room request): for the champion (p_model_over) and the challenger
          (p_chal_over from <chal dir>/<date>_D*_<hash>.csv, when present): bet the side the RAW model prefers when its
          edge vs D no-vig is >= 1 pt (95/5 blend ignored), flat 1 unit at the captured DK D price. Reports bets, W-L,
          units, ROI with a game-clustered 95% CI, the same sides' z-CLV and hit vs implied. Fliff: graded only where a
          Fliff price was captured (columns fliff_over/fliff_under); the NHL capture has none yet, so it shows 'not captured'.
Fliff list (as posted) paper track (added 2026-10-17, approved): the posted 'Fliff check' sides graded flat 1 u at the
          REAL Fliff price captured by fliff_prices.py (fliff_prices/<date>_*.csv; latest capture per side where Fliff offered
          the posted line), dates >= 20261017 only. Sides Fliff did not offer, or offered at a different line, are counted, not graded.
Pre-noon exclusion (draft prereg): games with puck drop before 12:00 PM America/Los_Angeles are marked
          excluded_pre_noon and dropped from every scored slice (CLV, model-only, Fliff) for dates >= 20261017;
          earlier dates get an info-only counterfactual in the report, logged CSVs unchanged.
Your own betting results: props-finder/user_bets/bets.csv (real bets logged by yinzerduck) summarized by book and sport.
          Labeled as the user's own results, NOT a model test (selected bets; some placed at DraftKings instead).
Usage: python3 grade_report.py [YYYYMMDD ...] [--graded DIR] [--chal DIR] [--out FILE] [--title TEXT]
       defaults: graded/, challenger/shadow/, graded/REPORT.md  (rebuilt Oct 12-16: --graded rebuilt/graded --chal rebuilt/challenger)"""
import sys, glob, os, math
import numpy as np, pandas as pd
os.chdir(os.path.dirname(os.path.abspath(__file__)))
A = sys.argv[1:]; opt = {}
for k in ('--graded', '--chal', '--out', '--title', '--fliff'):
    if k in A: i = A.index(k); opt[k] = A[i + 1]; del A[i:i + 2]
GD = opt.get('--graded', 'graded'); CD = opt.get('--chal', 'challenger/shadow'); OUT = opt.get('--out', f'{GD}/REPORT.md')
TITLE = opt.get('--title', 'NHL SOG grading report (primary score: z-CLV vs close)')
CH = open('challenger/CHALLENGER').read().strip()
dates = A or sorted(os.path.basename(f)[:8] for f in glob.glob(f'{GD}/2*.csv'))
G = pd.concat([pd.read_csv(f'{GD}/{d}.csv').assign(date=d) for d in dates], ignore_index=True)
CHAL = [pd.read_csv(f)[['nhl_id', 'gameId', 'line', 'p_chal_over']].assign(date=d) for d in dates for f in sorted(glob.glob(f'{CD}/{d}_D*_{CH}.csv'))[:1]]
if CHAL: G = G.merge(pd.concat(CHAL).drop_duplicates(['date', 'nhl_id', 'gameId', 'line']), on=['date', 'nhl_id', 'gameId', 'line'], how='left')
else: G['p_chal_over'] = np.nan
import game_starts as GS
G, _noon_summary = GS.mark_pre_noon(G)
lg = lambda p: np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
# ---- Early close (added 2026-10-17): games whose book pulled the board > 5 min before puck drop (close_timing.py, read-only
# over captures). Their nv_over_C is moved to nv_over_C_early, so EVERY z-CLV / closing-line number below excludes them;
# hit/units still count. They are reported on their own in '## Early closes'. capture_gap games stay in the primary numbers; a second CLV table excludes them (2026-10-19, post-hoc).
import close_timing as CT
_T = CT.all_games()
G['close_timing'] = G.event.astype(str).map(lambda e: (_T.get(e) or {}).get('close_timing', 'no_capture'))
G['close_last_lines_min'] = G.event.astype(str).map(lambda e: (_T.get(e) or {}).get('last_lines_min'))
G['early_close'] = G.close_timing.eq('early_close')
G['nv_over_C_early'] = np.where(G.early_close, G.nv_over_C, np.nan); G.loc[G.early_close, 'nv_over_C'] = np.nan
G['lean'] = np.where(G.p_model_over > G.nv_over, 'over', 'under'); G['lean_pts'] = (G.p_model_over - G.nv_over).abs() * 100
s = np.where(G.lean == 'over', 1, -1)
G['zclv_lean'] = s * (lg(G.nv_over_C) - lg(G.nv_over))
G['hit_lean'] = np.where(G.actual.isna(), np.nan, np.where(G.lean == 'over', G.actual > G.line, G.actual < G.line).astype(float))
G['imp_lean'] = np.where(G.lean == 'over', G.nv_over, 1 - G.nv_over)
def boot(df, col, B=2000):
    df = df[df[col].notna()]
    if len(df) == 0: return (np.nan, np.nan, np.nan, 0, 0)
    games = df.gameId.unique(); grp = {g: df.loc[df.gameId == g, col].values for g in games}
    rng = np.random.default_rng(0); ms = []
    for _ in range(B):
        pick = rng.choice(games, len(games)); v = np.concatenate([grp[g] for g in pick]); ms.append(v.mean())
    return (df[col].mean(), *np.percentile(ms, [2.5, 97.5]), len(df), len(games))
def block(df, label):
    ok = df[df.status == 'OK']
    m, lo, hi, n, ng = boot(ok, 'zclv_lean')
    h = ok[ok.hit_lean.notna()]
    hit, imp = h.hit_lean.mean(), h.imp_lean.mean(); se = math.sqrt(imp * (1 - imp) / len(h)) if len(h) else np.nan
    verdict = ('too few games for a verdict (<5)' if ng < 5 else None) or ('no evidence of edge (CI includes 0)' if lo <= 0 <= hi else ('positive CLV' if lo > 0 else 'negative CLV'))
    zc = ok.zclv_lean.dropna()
    return (f'| {label} | {n} | {ng} | {m:+.4f} | [{lo:+.4f}, {hi:+.4f}] | {(zc > 0).mean():.1%} / {(zc < 0).mean():.1%} '
            f'| {hit:.1%} vs {imp:.1%} ({(hit-imp)*100:+.1f} ± {se*100:.1f}) | {verdict} |')
L = [f'# {TITLE}', '',
     f'Dates: {", ".join(dates)}. Lines {len(G)}; status {G.status.value_counts().to_dict()}.', '',
     '| slice | n lines (OK, with C) | games | mean z-CLV | 95% CI (game-clustered) | share moved for / against | lean hit vs no-vig fair (pts ± 1 SE; not break-even) | verdict |',
     '|---|---|---|---|---|---|---|---|']
for d in dates: L.append(block(G[G.date == d], d))
L.append(block(G, '**all**')); L.append(block(G[G.lean_pts >= 5], 'all, lean >= 5 pts')); L.append(block(G[G.lean_pts < 5], 'all, lean < 5 pts'))
# ---- capture_gap excluded (added 2026-10-19, user-approved POST-HOC reporting choice, not prereg) ----
_GX = G.copy(); _GX.loc[_GX.close_timing.eq('capture_gap'), 'zclv_lean'] = np.nan
_gl = sorted({f"{r.game} ({r.date})" for r in G[G.close_timing.eq('capture_gap')].drop_duplicates(['date', 'event']).itertuples()})
L += ['', '### Same CLV table with capture_gap games excluded (post-hoc reporting choice, not prereg)', '',
      'capture_gap = our capture stopped > 5 min before puck drop, so the close is just the last price we saw. The table above (all games) stays the primary number. '
      'Excluded here: ' + ('; '.join(_gl) if _gl else 'none on these dates') + '. Hit rates are unchanged; only z-CLV rows drop.', '',
      '| slice | n lines (OK, with C) | games | mean z-CLV | 95% CI (game-clustered) | share moved for / against | lean hit vs no-vig fair (pts ± 1 SE; not break-even) | verdict |',
      '|---|---|---|---|---|---|---|---|']
for d in dates: L.append(block(_GX[_GX.date == d], d))
L.append(block(_GX, '**all, capture_gap excluded**')); L.append(block(_GX[_GX.lean_pts >= 5], 'all, lean >= 5 pts, capture_gap excluded')); L.append(block(_GX[_GX.lean_pts < 5], 'all, lean < 5 pts, capture_gap excluded'))
pk = G[G.get('pick', pd.Series(index=G.index, dtype=object)).isin(['OVER', 'UNDER']) & (G.status == 'OK')] if 'pick' in G else G.iloc[:0]
L += ['', f'Picks carried in D files: {len(pk)} graded' + (f'; hits {int(pk.hit.sum())}/{len(pk)}; units {pk.units.sum():+.2f}; mean z-CLV {pk.zclv.mean():+.4f}' if len(pk) else ' (lists were built from the sheet, not the D file; real bets live in props-finder/user_bets, kept separate).'),
      '', 'Slices with < 5 games get no verdict: a game-clustered CI needs more clusters. Read the pooled rows. PENDING_no_box = box score not posted yet (re-run grade.py).', '', 'z-CLV is in logit units: +0.04 is about +1 point of probability near 50%. A sample this size cannot separate a 1-2 point edge from zero.']
dec = lambda a: np.where(a < 0, 1 + 100 / np.abs(a), 1 + a / 100)
# ---- Early closes (lines pulled > 5 min before puck drop): out of CLV above, reported here ----
L += ['', '## Early closes (book pulled lines early): kept out of every CLV number', '',
      f'A game is an early close when the last close-window snapshot with lines was more than {CT.EARLY_MIN} min before puck drop and '
      'later snapshots came back empty (the book pulled the board). Its close is really an early price, so those rows are excluded '
      'from every z-CLV / closing-line figure in this report (CLV table, model-only, Fliff list). Win/loss and units still count. '
      'z-CLV against that early price is shown here for the record only.', '']
_E = G[G.early_close]
if _E.empty: L.append('No early closes on these dates.')
else:
    L += ['| date | game | event | last lines (min before puck drop) | rows (OK) | lean z-CLV vs early price (record only) | lean hit vs no-vig fair |', '|---|---|---|---|---|---|---|']
    for (d_, ev), e_ in _E.groupby(['date', 'event']):
        ok_ = e_[e_.status == 'OK']; z_ = (np.where(ok_.lean == 'over', 1, -1) * (lg(ok_.nv_over_C_early) - lg(ok_.nv_over))) if len(ok_) else np.array([])
        h_ = ok_[ok_.hit_lean.notna()]
        L.append(f"| {d_} | {e_.game.iloc[0]} | {ev} | {e_.close_last_lines_min.iloc[0]} | {len(e_)} ({len(ok_)}) | "
                 f"{(np.nanmean(z_) if len(z_) else float('nan')):+.4f} | " + (f'{h_.hit_lean.mean():.1%} vs {h_.imp_lean.mean():.1%} ({len(h_)})' if len(h_) else 'pending') + ' |')
_gap = G[G.close_timing == 'capture_gap'].groupby(['date', 'event']).agg(game=('game', 'first'), m=('close_last_lines_min', 'first'), n=('status', 'size'))
if len(_gap):
    L += ['', 'Info (IN the primary CLV numbers; excluded from the second CLV table): games where OUR capture stopped before puck drop (no later snapshot), so the close is the last price we saw: '
          + '; '.join(f"{r.game} ({d_}, last lines {r.m} min out, {r.n} rows)" for (d_, ev), r in _gap.iterrows()) + '.']
# ---- Pre-noon PT exclusion (draft prereg line 21) ----
L += ['', '## Pre-noon PT exclusion (draft prereg)', '',
      'Eligible graded-track games have puck drop at or after 12:00 PM America/Los_Angeles. '
      f'From {GS.EXCLUDE_FROM} through {GS.EXCLUDE_UNTIL}, earlier games are marked `excluded_pre_noon` and left out of every scored slice '
      '(CLV table, model-only paper track, Fliff list). Start times come from saved captures, else api-web.nhle.com.', '']
_excl = [s for s in _noon_summary if s['enforced'] and s['pre_noon_rows']]
if _excl:
    for s in _excl:
        games = ', '.join(f"{g['name'] or g['gameId']} ({g['start_pt']}, {g['rows']} rows)" for g in s['games']) or '—'
        L.append(f"- **{s['date']}**: {s['pre_noon_rows']} rows excluded ({s['pre_noon_ok']} were OK before exclusion). Games: {games}.")
else:
    enforced_dates = [s['date'] for s in _noon_summary if s['enforced']]
    L.append('No pre-noon games in the enforced window' + (f" ({', '.join(enforced_dates)})." if enforced_dates else f' (no dates >= {GS.EXCLUDE_FROM} in this report).'))
_hist = [s for s in _noon_summary if not s['enforced']]
if _hist:
    L += ['', '### Earlier days (before enforcement) — info only, logged files unchanged', '']
    total_ok_pre = sum(s['pre_noon_ok'] for s in _hist)
    for s in _hist:
        if s['pre_noon_ok'] or s['pre_noon_rows']:
            games = ', '.join(f"{g['name'] or g['gameId']} ({g['start_pt']}, {g['ok']} OK)" for g in s['games']) or '—'
            L.append(f"- **{s['date']}**: {s['pre_noon_ok']} OK rows / {s['pre_noon_rows']} total rows were pre-noon. Games: {games}.")
        else:
            L.append(f"- **{s['date']}**: 0 pre-noon graded rows.")
    L.append('')
    if total_ok_pre == 0:
        L.append('Headline champion numbers with pre-noon OK rows excluded: **unchanged** (no pre-noon OK rows in these dates).')
    else:
        _Gh = G[G.date.astype(str) < GS.EXCLUDE_FROM]
        # status not rewritten for historical; drop pre-noon via mask
        _ok_h = _Gh[_Gh.status == 'OK']
        _ok_ex = _ok_h[GS.counterfactual_ok_mask(_ok_h)]
        L.append(f'Pre-noon OK rows on earlier days: {total_ok_pre}. Counterfactual scored OK lines: {len(_ok_ex)} (was {len(_ok_h)}).')
        if len(_ok_ex):
            m, lo, hi, n, ng = boot(_ok_ex, 'zclv_lean')
            L.append(f'- CLV **all** with pre-noon excluded: n={n}, games={ng}, mean z-CLV {m:+.4f} [{lo:+.4f}, {hi:+.4f}].')
            _mo = _ok_ex[_ok_ex.p_model_over.notna() & _ok_ex.actual.notna()].copy()
            e = _mo.p_model_over - _mo.nv_over
            _mo['side'] = np.where(e >= 0.01, 'over', np.where(-e >= 0.01, 'under', ''))
            _mo = _mo[_mo.side != '']
            if len(_mo):
                win = np.where(_mo.side == 'over', _mo.actual > _mo.line, _mo.actual < _mo.line)
                price = np.where(_mo.side == 'over', _mo.over, _mo.under).astype(float)
                u = np.where(win, dec(price) - 1, -1.0)
                L.append(f'- Model-only champion with pre-noon excluded: {int(win.sum())}-{len(_mo)-int(win.sum())}, {u.sum():+.2f} u on {len(_mo)} bets.')

def model_only(df, pcol, label, book='dk'):
    d = df[(df.status == 'OK') & df.actual.notna() & df[pcol].notna()].copy()
    po, pu = (d.over, d.under) if book == 'dk' else (d.get('fliff_over'), d.get('fliff_under'))
    if po is None: return f'| {label} | Fliff | not captured | | | | | |'
    d['po'], d['pu'] = pd.to_numeric(po, errors='coerce').values, pd.to_numeric(pu, errors='coerce').values
    e = d[pcol] - d.nv_over; d['side'] = np.where(e >= 0.01, 'over', np.where(-e >= 0.01, 'under', ''))
    d = d[(d.side != '') & np.where(d.side == 'over', d.po.notna(), d.pu.notna())]
    if d.empty: return f'| {label} | {book.upper()} | 0 | | | | | |'
    win = np.where(d.side == 'over', d.actual > d.line, d.actual < d.line)
    price = np.where(d.side == 'over', d.po, d.pu).astype(float)
    d['u'] = np.where(win, dec(price) - 1, -1.0); d['w'] = win.astype(float)
    d['z'] = np.where(d.side == 'over', 1, -1) * (lg(d.nv_over_C) - lg(d.nv_over))
    imp = np.where(d.side == 'over', d.nv_over, 1 - d.nv_over).mean()
    m, lo, hi, n, ng = boot(d, 'u'); zm, zlo, zhi, _, _ = boot(d, 'z')
    return (f'| {label} | {book.upper()} | {n} ({ng} g) | {int(d.w.sum())}-{n - int(d.w.sum())} | {d.u.sum():+.2f} u | {m:+.1%} [{lo:+.1%}, {hi:+.1%}] '
            f'| {zm:+.4f} [{zlo:+.4f}, {zhi:+.4f}] | {d.w.mean():.1%} vs {imp:.1%} |')
if GD == 'graded': L += ['', 'Oct 12-16 rows here used STALE inputs (NOTES.md) and are kept as logged. The clean retro-computed record for those days (point-in-time, gap-free data, champion + challenger) is rebuilt/REPORT.md - separate from what was posted or bet that week.']
L += ['', '## Model-only paper track (raw model side, edge vs no-vig >= 1 pt, flat 1 u at the captured price; blend ignored)', '',
      '| track | book | bets (games) | W-L | units | ROI (95% CI, game-clustered) | z-CLV of those sides (95% CI) | hit vs no-vig fair (not break-even) |', '|---|---|---|---|---|---|---|---|']
for pcol, name in (('p_model_over', 'champion c3ab760178'), ('p_chal_over', f'challenger {CH}')):
    if G[pcol].notna().any():
        for d_ in dates: L.append(model_only(G[G.date == d_], pcol, f'{name}, {d_}'))
        L.append(model_only(G, pcol, f'**{name}, all**')); L.append(model_only(G, pcol, f'{name}, all', 'fliff'))
    else: L.append(f'| {name} | DK | no predictions on these dates | | | | | |')
L += ['', 'Paper only: flat 1 unit per side at the DraftKings price captured in the D snapshot. Not bets placed; real bets live in props-finder/user_bets.']

# ---- Fliff list (as posted): posted Fliff-check sides at the captured real Fliff price (from 2026-10-17) ----
FP_DIR = opt.get('--fliff', 'fliff_prices')
fd = [d for d in dates if d >= '20261017']
F = [pd.read_csv(f).assign(_f=os.path.basename(f)) for d in fd for f in sorted(glob.glob(f'{FP_DIR}/{d}_*.csv'))]
L += ['', '## Fliff list (as posted): paper track at the real captured Fliff price (from Oct 17)', '']
if not F: L.append('No Fliff price captures for these dates yet (fliff_prices.py starts Oct 17).')
else:
    F = pd.concat(F, ignore_index=True); F['date'] = F.date.astype(str); F['_off'] = F.fliff_status.eq('offered')
    F = F.sort_values(['_off', '_f']).drop_duplicates(['date', 'player', 'side', 'line'], keep='last')
    cnt = F.fliff_status.value_counts().to_dict()
    F['nhl_id'] = pd.to_numeric(F.nhl_id, errors='coerce'); F['gameId'] = pd.to_numeric(F.gameId, errors='coerce')
    J = F[F._off].merge(G[['date', 'nhl_id', 'gameId', 'line', 'actual', 'status', 'nv_over', 'nv_over_C']], on=['date', 'nhl_id', 'gameId', 'line'], how='left')
    J = J[~J.status.isin(['VOID_dnp', 'PENDING_no_box']) & J.actual.notna()].copy()  # W/L needs a box score, not a close (2026-10-21); z-CLV NaN where no close
    def ftrack(d, label):
        if d.empty: return f'| {label} | 0 | | | | | |'
        win = np.where(d.side == 'OVER', d.actual > d.line, d.actual < d.line)
        d = d.assign(u=np.where(win, dec(d.fliff_price.astype(float)) - 1, -1.0), w=win.astype(float),
                     z=np.where(d.side == 'OVER', 1, -1) * (lg(d.nv_over_C) - lg(d.nv_over)))
        m, lo, hi, n, ng = boot(d, 'u'); zm, zlo, zhi, _, _ = boot(d, 'z')
        ver = 'too few games for a verdict (<5)' if ng < 5 else ('no evidence of profit (CI includes 0)' if lo <= 0 <= hi else ('profitable' if lo > 0 else 'losing'))
        return (f'| {label} | {n} ({ng} g) | {int(d.w.sum())}-{n - int(d.w.sum())} | {d.u.sum():+.2f} u | {m:+.1%} [{lo:+.1%}, {hi:+.1%}] '
                f'| {zm:+.4f} [{zlo:+.4f}, {zhi:+.4f}] | {ver} |')
    L += [f'Posted Fliff-check sides captured: {len(F)}; Fliff status {cnt}. Graded (offered at the posted line, box score in): {len(J)}.', '',
          '| slice | bets (games) | W-L | units | ROI (95% CI, game-clustered) | z-CLV of those sides (95% CI) | verdict |', '|---|---|---|---|---|---|---|']
    for d_ in fd: L.append(ftrack(J[J.date == d_], f'Fliff list (as posted), {d_}'))
    L.append(ftrack(J, '**Fliff list (as posted), all**'))
    L.append(ftrack(J[J.beats_shop_at.astype(str).str.lower() == 'true'], 'all, Fliff price beat shop-at'))
    L += ['', 'Paper only: flat 1 unit on every posted Fliff-check side Fliff offered at the same line, at the captured Fliff price, whether or not it was bet.']

import list_track
L += [''] + list_track.md(dates)

# ---- Your own betting results (real bets you logged; NOT a model test) ----
BF = '/workspace/props-finder/user_bets/bets.csv'
L += ['', '## Your own betting results (real bets you logged; not a model test)', '']
if os.path.exists(BF):
    B = pd.read_csv(BF); B['res'] = B.result.str.lower()
    _d = lambda a: 1 + (a / 100 if a > 0 else 100 / -a)
    _miss = B.payout.isna() & B.res.eq('win')  # payout not visible: use price-implied payout, counted below
    B.loc[_miss, 'payout'] = (B.risk * B.price.astype(float).map(_d)).round(2)
    B['profit'] = np.where(B.res == 'win', B.payout - B.risk, np.where(B.res == 'loss', -B.risk, 0.0))
    B = B[B.res.isin(['win', 'loss', 'push'])]
    L += ['| book / sport | bets | W-L-P | risked | profit | ROI |', '|---|---|---|---|---|---|']
    for keys, b in list(B.groupby(['book', 'sport'])) + [(('**all**', ''), B)]:
        L.append(f'| {" / ".join(k for k in keys if k)} | {len(b)} | {(b.res == "win").sum()}-{(b.res == "loss").sum()}-{(b.res == "push").sum()} '
                 f'| ${b.risk.sum():.2f} | ${b.profit.sum():+.2f} | {b.profit.sum() / b.risk.sum():+.1%} |')
    L += ['', f'These are the bets you chose and placed (some at DraftKings instead of Fliff, some from lists later found flawed, e.g. Oct 13 NHL). Wins with no visible payout use the price-implied payout ({int(_miss.sum())} such bet(s)). They show how your own betting is doing, not whether the model works; the model is judged by the paper tracks above.']
else: L.append('bets.csv not found.')
os.makedirs(os.path.dirname(OUT) or '.', exist_ok=True); open(OUT, 'w').write('\n'.join(L) + '\n'); print('\n'.join(L))
