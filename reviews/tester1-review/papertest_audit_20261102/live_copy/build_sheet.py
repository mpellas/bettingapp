"""Build the daily D-snapshot picks spreadsheet.

Usage: python3 build_sheet.py <picks.csv> <gate.csv> <out.xlsx> [--puck-drop "6:00 PM PT"]

picks.csv : picks/YYYYMMDD_D.csv (model output; used for the frozen model columns)
gate.csv  : shop_gate output (shop_ok/shop_veto); recent-form columns are (re)computed
            with recent_form.annotate so the filter is always p_recent > no-vig.

status per side row (one row per player per side):
  'DK bet'      blended EV > 0 at the DraftKings price
  'Fliff check' model P > no-vig P, shop_ok, |model-no-vig| <= 0.12, no slot veto on side,
                side_method == milestone, lineup gate passed, recent-form pass;
                ranked by model minus no-vig, top 5
  'Skipped'     with the first failing reason
Thin edge (approved 2026-10-16): any side (DK bet or Fliff check) whose model minus no-vig OR p_recent minus
no-vig is under 1 point is 'Skipped' with reason 'thin edge (...)'.
Edge floor (2026-10-20): any side (DK bet or Fliff check) with model minus no-vig under 5.0 pts is Skipped with
reason 'edge below 5-pt floor' (thin-edge sides keep the thin-edge reason).
Shadow columns (not used for status): fresh_recent_mu, shrunk_mu, p_shrunk (gamma-Poisson, shrink.py).
Evidence columns (display only, added 2026-10-17; NOT used for status): sig_champ ... sig_move (+/-/0), agrees_n,
disagrees_n, evidence_summary (evidence.py). --post writes one plain-text line per non-Skipped side.
"""
import math, sys, argparse
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.formatting.rule import FormulaRule
from openpyxl.utils import get_column_letter
import recent_form
import lineup_age   # 2026-11-03 12h stale-lineup skip
try:
    import shrink
except Exception:
    shrink = None
try:
    import evidence
except Exception:
    evidence = None
import os, re

sys.path.insert(0, '/workspace/props-finder')
try:
    from pickem import TYPES, breakeven
except Exception:  # fallback: no PrizePicks column
    TYPES, breakeven = {}, None

WITHIN = 0.12
TOP_N = 5
NEAR_TIE = 0.01
EDGE_FLOOR = 0.05   # testers' rule (Oct 12-16 data): model minus no-vig under 5.0 pts -> Skipped, DK and Fliff lists

def am_to_dec(a):
    a = float(a); return 1 + a / 100 if a > 0 else 1 + 100 / -a

def shop_at(p):
    """Worst American price still EV>=0 at probability p."""
    d = 1 / p
    if d >= 2: return int(math.ceil(100 * (d - 1) - 1e-9))
    return -int(math.floor(100 / (d - 1) + 1e-9))

def yn(b): return 'yes' if b else 'no'

def truthy(v):
    return str(v).strip().lower() in ('true', '1', 'yes')

def build_rows(picks, gate, puck, date=None):
    g = recent_form.annotate(gate)
    key = ['espn_id', 'line']
    g = g.set_index(key)
    if shrink is not None:
        try: picks = shrink.annotate(picks)
        except Exception as e: print('shrink columns skipped:', e)
    rows = []
    for _, r in picks.iterrows():
        gr = g.loc[(r.espn_id, r.line)]
        shop_ok = truthy(gr.shop_ok)
        lineup = shop_ok and (pd.isna(gr.shop_veto) or str(gr.shop_veto).strip() == '')
        rmu = gr.recent_mu
        for side in ('over', 'under'):
            pm = r.p_model_over if side == 'over' else 1 - r.p_model_over
            pb = r.p_blend_over if side == 'over' else 1 - r.p_blend_over
            nv = r.nv_over if side == 'over' else 1 - r.nv_over
            pr = gr[f'p_recent_{side}']
            dk = r[side]
            ev = r[f'ev_{side}']
            sv = str(r.slot_veto).strip().lower()
            veto = not pd.isna(r.slot_veto) and sv not in ('', 'nan', 'false') and (sv in ('true', 'both') or sv == side)
            types = ','.join(t for t in TYPES if breakeven and pb >= breakeven(t)) or None
            rows.append(dict(
                _nhl_id=r.nhl_id, _line=r.line, _side=side,
                game=r.game, puck_drop_pt=puck, player=r.player, side=side.upper(), line=r.line,
                dk_price=int(float(dk)), fliff_shop_at=shop_at(pb), prizepicks_types=types,
                model_mu=round(r.mu, 2), recent_mu=round(rmu, 2),
                gap_model_minus_recent=round(r.mu - rmu, 2), gap_model_to_line=round(r.mu - r.line, 2),
                gap_recent_to_line=round(rmu - r.line, 2), p_model=round(pm, 3), p_recent=round(pr, 3),
                p_novig=round(nv, 3), p_blend=round(pb, 3),
                flag_shop_ok=yn(shop_ok), flag_within_12_novig=yn(abs(pm - nv) <= WITHIN),
                flag_slot_veto=yn(veto), flag_milestone=yn(r.side_method == 'milestone'),
                flag_recent_pass=yn(pr > nv), flag_lineup_gate=yn(lineup),
                shrunk_mu=round(r.shrunk_mu, 2) if 'shrunk_mu' in r and pd.notna(r.shrunk_mu) else None,
                p_shrunk=round(r[f'p_shrunk_{side}'], 3) if f'p_shrunk_{side}' in r and pd.notna(r[f'p_shrunk_{side}']) else None,
                flag_thin_edge=yn(recent_form.thin_edge(pm - nv, pr - nv)),
                last5_shots=gr.get('last5_shots', ''), recent_windows=gr.get('recent_windows', ''),
                _veto=('' if pd.isna(gr.shop_veto) else str(gr.shop_veto).strip()),
                _stale=lineup_stale_of(gr),
                _role=(str(gr.role_reason) if truthy(gr.get(f'role_veto_{side}', False)) and pd.notna(gr.get('role_reason')) else ''),
                _ev=ev, _edge=pm - nv, _rmargin=pr - nv,
                _rmargin_fresh=(r[f'p_fresh_{side}'] - nv) if f'p_fresh_{side}' in r and pd.notna(r[f'p_fresh_{side}']) else None,
                _drift=input_drift(r),
            ))
    df = pd.DataFrame(rows)
    df = assign_status(df, '_rmargin')
    # Fresh-data check (added 2026-10-17 after the fetch.py staleness fix): recompute the recent-form gate and
    # thin-edge rule from fresh game logs; show any side whose status would change. Model probabilities are not
    # recomputed here (re-run predict.py after fetch.py for that).
    if df._rmargin_fresh.notna().any():
        alt = assign_status(df.assign(_rmargin=df._rmargin_fresh.fillna(df._rmargin)), '_rmargin')
        df['status_if_fresh_inputs'] = alt.status
    else:
        df['status_if_fresh_inputs'] = None
    def chk(x):
        msg = x._drift or 'inputs match fresh game logs'
        if x.status_if_fresh_inputs and x.status_if_fresh_inputs != x.status:
            msg += f'; STATUS CHANGES with fresh inputs: {x.status} -> {x.status_if_fresh_inputs}'
        return msg
    df['fresh_data_check'] = df.apply(chk, axis=1)
    # Evidence block: display only. Status above is computed before this and is not touched.
    ecols = [f'sig_{k}' for k in (evidence.SIGS if evidence else [])] + ['agrees_n', 'disagrees_n', 'evidence_summary']
    try:
        if evidence is None or not date: raise RuntimeError('no date / evidence module')
        A = evidence.annotate(picks, date, gate=gate).rename(columns={'nhl_id': '_nhl_id', 'line': '_line', 'side': '_side'})
        df = df.merge(A[['_nhl_id', '_line', '_side'] + ecols], on=['_nhl_id', '_line', '_side'], how='left')
        df['agrees_n'] = df.agrees_n.astype('Int64'); df['disagrees_n'] = df.disagrees_n.astype('Int64')
    except Exception as e:
        print('evidence columns skipped:', e)
        for c in ecols: df[c] = None
    df['offered_fliff'] = df['offered_dk'] = df['offered_prizepicks'] = None
    return df.drop(columns=[c for c in df if c.startswith('_')])

def lineup_stale_of(gr):
    """2026-11-03: skip reason if the gate's DFO lineup is >12h old or has no timestamp, else ''.
    Uses the gate's lineup_stale column (computed at gate time = list build time) when present; older GATE files
    without it fall back to dfo_updated vs now."""
    if 'lineup_stale' in gr.index:
        v = gr.get('lineup_stale')
        return '' if pd.isna(v) else str(v).strip()
    return lineup_age.stale_reason(gr.get('dfo_updated'))

def input_drift(r):
    """Compare the D file's recent-form inputs with fresh game logs (shrink.py). None if they agree."""
    if 'fresh_sog60_r10' not in r or pd.isna(r.get('fresh_sog60_r10')): return 'fresh game logs unavailable'
    d1, d2 = r.fresh_sog60_r10 - r.sog60_r10, r.fresh_toi_r5 - r.toi_r5
    if abs(d1) < 0.05 and abs(d2) < 0.1: return None
    return f'STALE INPUTS: sog60_r10 {r.sog60_r10:.2f}->{r.fresh_sog60_r10:.2f}, toi_r5 {r.toi_r5:.1f}->{r.fresh_toi_r5:.1f}'

def assign_status(df, rcol):
    df = df.copy()
    df['flag_recent_pass'] = [yn(v > 0) for v in df[rcol]]
    df['flag_thin_edge'] = [yn(recent_form.thin_edge(e, m)) for e, m in zip(df._edge, df[rcol])]

    def fail(x):
        if x.get('_stale'): return x._stale   # 2026-11-03 12h stale-lineup skip (first reason, both lists)
        if x.get('_role'): return f"{x._role}, {'under' if x.get('_side')=='under' else 'over'} skipped"
        if x._edge <= 0: return 'model not above no-vig'
        if x.flag_shop_ok != 'yes': return f'shop gate failed ({x._veto})' if x.get('_veto') else 'shop gate failed'
        if x.flag_within_12_novig != 'yes': return 'model more than 12 points from no-vig'
        if x.flag_slot_veto == 'yes': return 'slot veto'
        if x.flag_milestone != 'yes': return 'side not from milestone prices'
        if x.flag_lineup_gate != 'yes': return 'lineup/injury gate failed'
        if x.flag_recent_pass != 'yes': return 'recent form does not beat no-vig'
        return None
    df['_fail'] = df.apply(fail, axis=1)
    df['status'], df['status_reason'], df['note'] = 'Skipped', '', ''
    thin = df.flag_thin_edge.eq('yes')
    role = df['_role'].fillna('').ne('') if '_role' in df else False   # side-specific role veto (mixed sets it on both)
    stale = df['_stale'].fillna('').ne('') if '_stale' in df else pd.Series(False, index=df.index)
    role = role | stale   # stale lineup: Skipped on DK and Fliff lists, like a role veto
    floor = (df._edge < EDGE_FLOOR - 1e-12) & ~thin   # 5-pt model-edge floor (thin edge keeps its own reason)
    dk = (df._ev > 0) & ~thin & ~floor & ~role   # role-changed sides are Skipped on the DraftKings list too
    df.loc[dk, 'status'] = 'DK bet'; df.loc[dk, 'status_reason'] = 'positive blended EV at DraftKings'
    elig = df[~dk & ~thin & ~floor & df._fail.isna()].sort_values('_edge', ascending=False)
    top, rest = elig.index[:TOP_N], elig.index[TOP_N:]
    df.loc[top, 'status'] = 'Fliff check'
    df.loc[top, 'status_reason'] = df.loc[top].apply(
        lambda x: f'model {x._edge*100:+.1f} pts vs no-vig; recent {x._rmargin*100:+.1f} pts', axis=1)
    df.loc[[i for i in top if df.at[i, '_rmargin'] < NEAR_TIE], 'note'] = 'near-tie, testers advise skip'
    df.loc[rest, 'status_reason'] = f'passes all checks but outside top {TOP_N} by edge'
    sk = df.status.eq('Skipped') & df._fail.notna()
    df.loc[sk, 'status_reason'] = df.loc[sk, '_fail'] + '; no positive blended EV at DraftKings'
    rk = sk & role & ~stale & (df._ev > 0)
    df.loc[rk, 'status_reason'] = df.loc[rk, '_fail'] + '; positive blended EV at DraftKings but role changed, not listed'
    sl = sk & stale & (df._ev > 0)
    df.loc[sl, 'status_reason'] = df.loc[sl, '_fail'] + '; positive blended EV at DraftKings but lineup stale, not listed'
    th = df.status.eq('Skipped') & thin & (df._fail.isna() | (df._ev > 0)) & ~role
    df.loc[th, 'status_reason'] = df.loc[th].apply(
        lambda x: f'thin edge (model {x._edge*100:+.1f} pts, recent {x._rmargin*100:+.1f} pts vs no-vig; under 1 point)', axis=1)
    fl = df.status.eq('Skipped') & floor & (df._fail.isna() | (df._ev > 0)) & ~role
    df.loc[fl, 'status_reason'] = df.loc[fl].apply(
        lambda x: f'edge below 5-pt floor (model {x._edge*100:+.1f} pts vs no-vig)', axis=1)
    return df

KEY = [
 ('game', 'Both teams in the matchup, away at home.'),
 ('puck_drop_pt', 'Scheduled puck drop in Pacific Time (America/Los_Angeles).'),
 ('player', 'Player name for the shots-on-goal prop.'),
 ('side', 'OVER or UNDER on the line.'),
 ('line', 'DraftKings shots-on-goal line for that player.'),
 ('dk_price', 'DraftKings American odds for this side.'),
 ('fliff_shop_at', 'Worst Fliff American price still EV≥0 at the blended probability for this side. Skip if the offered Fliff price is worse than this.'),
 ('prizepicks_types', "PrizePicks entry types (power2/3, flex3–6) where blended side probability clears that type's no-push breakeven. Empty if none."),
 ('model_mu', 'Model expected shots for the player.'),
 ('recent_mu', 'Recent-form expected shots (shot-rate based).'),
 ('gap_model_minus_recent', 'model_mu minus recent_mu. Positive means the model is higher than recent form.'),
 ('gap_model_to_line', 'model_mu minus the line.'),
 ('gap_recent_to_line', 'recent_mu minus the line.'),
 ('p_model', 'Frozen model probability of this side.'),
 ('p_recent', 'Recent-form (Poisson) probability of this side clearing the line.'),
 ('p_novig', 'No-vig market probability for this side from DraftKings.'),
 ('p_blend', 'Blended model/market probability for this side.'),
 ('flag_shop_ok', 'Yes if the lineup/injury shop gate passed for this player.'),
 ('flag_within_12_novig', 'Yes if |p_model − p_novig| ≤ 0.12 (model within 12 points of no-vig).'),
 ('flag_slot_veto', 'Yes if the slot veto applies to this side.'),
 ('flag_milestone', 'Yes if the side was chosen via the milestone method.'),
 ('flag_recent_pass', 'Yes if p_recent beats p_novig for this side.'),
 ('flag_thin_edge', 'Yes if model minus no-vig OR p_recent minus no-vig is under 1 point. Such sides are Skipped (thin edge), even with positive DraftKings EV.'),
 ('shrunk_mu', 'SHADOW (not used for status): recent shots shrunk toward the player\'s longer-run rate (gamma-Poisson, 15-game prior), fresh game logs.'),
 ('p_shrunk', 'SHADOW: probability of this side from the shrunk estimate (negative binomial).'),
 ('status_if_fresh_inputs', 'Status recomputed with recent form from fresh game logs (model probabilities unchanged). Differs from status only if the D file used stale inputs.'),
 ('fresh_data_check', "'inputs match fresh game logs', or STALE INPUTS with old->fresh 10-game shot rate and 5-game TOI, plus STATUS CHANGES when the side's status would differ."),
 ('flag_lineup_gate', 'Yes if the lineup/injury gate passed (shop_ok and no shop_veto).'),
 ('sig_champ', "EVIDENCE (display only, not used for status). Frozen champion c3ab760178 probability minus no-vig for this side: + above +0.5 pt, - below -0.5 pt, 0 in between."),
 ('sig_chal', 'Shadow challenger 3386583f18 probability minus no-vig (same ±0.5 pt band). 0 with "challenger not run" if challenger/shadow/<date>_D_3386583f18.csv is missing.'),
 ('sig_shrunk', 'Shrunk recent form (p_shrunk) minus no-vig (±0.5 pt band).'),
 ('sig_toi', 'Ice-time trend: last-5-game TOI minus this-season mean only (vote needs ≥1.0 min gap and ≥5 season games; last-30 shown for reference only); + for an over when TOI is rising, + for an under when falling.'),
 ('sig_opp', "Opponent shots allowed to the player's slot (D / F lines / PP1) vs league, last 20 games (±3% band); + for an over when the opponent allows more."),
 ('sig_lineup', 'From the DailyFaceoff lineup in the D capture: injured/out/GTD or shop veto = - for over; on PP1 = + over / - under; 3rd-4th line or 3rd pair with no PP = - over / + under.'),
 ('sig_move', 'DK no-vig move from the open to the D snapshot (±0.5 pt band); + when the market moved toward this side.'),
 ('agrees_n', "Number of the 7 signals that are + for this side ('agrees N of 7')."),
 ('disagrees_n', 'Number of the 7 signals that are - for this side.'),
 ('evidence_summary', "One plain line: 'agrees N of 7 (...); against: ...'. Backtest so far does NOT show that a high count improves results; treat as context, not a filter."),
 ('status', "'DK bet' = positive blended EV at the DraftKings price. 'Fliff check' = model > no-vig, shop_ok, within 12 points, no slot veto, milestone side, lineup gate, recent-form pass; top 5 by model minus no-vig. Any side with a thin edge (under 1 point on model or recent) is 'Skipped'. Otherwise 'Skipped'."),
 ('status_reason', 'Edge summary for bets/checks, or the first failing check when Skipped.'),
 ('note', "Extra caution, e.g. 'near-tie, testers advise skip' when recent form beats no-vig by under 1 point."),
 ('offered_fliff', 'Blank input cell — type the Fliff price you were offered. Turns green if better/equal vs fliff_shop_at (by decimal odds), red if worse.'),
 ('offered_dk', 'Blank input cell — type the DraftKings price you were offered. Same green/red vs fliff_shop_at.'),
 ('offered_prizepicks', 'Blank input cell — type a PrizePicks-comparable American price if you map one. Same green/red vs fliff_shop_at.'),
 ('(formatting note)', 'Green/red conditional formatting on offered_* columns only evaluates in Excel or Google Sheets, not in every spreadsheet viewer.'),
]

def post_text(df):
    """Pick-post lines for non-Skipped sides, with the evidence line under each (display only)."""
    out = []
    for _, x in df[df.status != 'Skipped'].iterrows():
        out.append(f"{x.status}: {x.player} {x.side} {x.line} (DK {x.dk_price:+d}, Fliff at {x.fliff_shop_at:+d} or better) - {x.status_reason}"
                   + (f" [{x.note}]" if x.note else ''))
        l5 = [int(v) for v in str(x.get('last5_shots') or '').split(',') if v.strip().lstrip('-').isdigit()]
        if l5:
            hit = sum((v > x.line) if x.side == 'OVER' else (v < x.line) for v in l5)
            out.append(f"   last {len(l5)}: {hit} of {len(l5)} {x.side.lower()} {x.line} (shots {','.join(map(str, l5))}); model {x.p_model*100:.1f}%, recent form {x.p_recent*100:.1f}% ({x.get('recent_windows')})")
        if x.get('evidence_summary'): out.append(f"   evidence: {x.evidence_summary}")
    return '\n'.join(out) + '\n'

def write(df, out):
    wb = Workbook(); ws = wb.active; ws.title = 'Picks'
    cols = list(df.columns); ws.append(cols)
    for c in ws[1]: c.font = Font(bold=True)
    for row in df.itertuples(index=False):
        ws.append([None if (isinstance(v, float) and math.isnan(v)) else v for v in row])
    ws.freeze_panes = 'A2'
    n = len(df) + 1
    widths = {'game': 42, 'puck_drop_pt': 12, 'player': 18, 'side': 8, 'line': 7, 'status': 12, 'status_reason': 48, 'note': 28}
    for i, c in enumerate(cols, 1):
        ws.column_dimensions[get_column_letter(i)].width = widths.get(c, 14)
    G = get_column_letter(cols.index('fliff_shop_at') + 1)
    dec = lambda ref: f'IF({ref}>0,1+{ref}/100,1+100/(-{ref}))'
    green = PatternFill(start_color='C6EFCE', end_color='C6EFCE', fill_type='solid')
    red = PatternFill(start_color='FFC7CE', end_color='FFC7CE', fill_type='solid')
    for name in ('offered_fliff', 'offered_dk', 'offered_prizepicks'):
        L = get_column_letter(cols.index(name) + 1); a, gg = f'{L}2', f'${G}2'
        base = f'ISNUMBER({a}),ISNUMBER({gg})'
        ws.conditional_formatting.add(f'{L}2:{L}{n}', FormulaRule(formula=[f'AND({base},{dec(a)}>={dec(gg)})'], fill=green))
        ws.conditional_formatting.add(f'{L}2:{L}{n}', FormulaRule(formula=[f'AND({base},{dec(a)}<{dec(gg)})'], fill=red))
    k = wb.create_sheet('Key'); k.append(['Column', 'Meaning'])
    for c in k[1]: c.font = Font(bold=True)
    for r in KEY: k.append(list(r))
    k.freeze_panes = 'A2'; k.column_dimensions['A'].width = 24; k.column_dimensions['B'].width = 110
    wb.save(out)

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('picks'); ap.add_argument('gate'); ap.add_argument('out')
    ap.add_argument('--puck-drop', default='')
    ap.add_argument('--date', default=None, help='YYYYMMDD; default from the picks file name')
    ap.add_argument('--post', default=None, help='write pick-post text (one line per non-Skipped side) to this file')
    a = ap.parse_args()
    date = a.date or (re.search(r'(20\d{6})', os.path.basename(a.picks)) or [None, None])[1]
    df = build_rows(pd.read_csv(a.picks), pd.read_csv(a.gate), a.puck_drop, date)
    write(df, a.out)
    if a.post:
        open(a.post, 'w').write(post_text(df))
        print('post text ->', a.post)
    print(df[df.status != 'Skipped'][['player', 'side', 'line', 'fliff_shop_at', 'p_model', 'p_novig', 'p_recent', 'status', 'note']].to_string())
    print(df.status.value_counts().to_string())
