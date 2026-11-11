"""Per-side evidence block (added 2026-10-17; display only, NOT a gate). For each side of a D line, seven signals are
scored + (agrees with the side), - (disagrees) or 0 (neutral / unavailable):
  1 champ    frozen champion P(side) vs DK no-vig P(side)                     neutral band +-0.5 pt
  2 chal     frozen challenger 3386583f18 P(side) vs no-vig (shadow file)     neutral band +-0.5 pt; 0 if not run
  3 shrunk   gamma-Poisson shrunk recent form P(side) vs no-vig (shrink.py)   neutral band +-0.5 pt
  4 toi      fresh toi_r5 vs this season's TOI/game to date ONLY (2026-10-20): vote only if |diff| >= 1.0 min
             (under + / over - when last 5 is >= 1.0 below season); < 5 games this season -> 0. toi_r30 is display only.
  5 opp      opponent shots allowed to the player's slot (predict.py opp_slot_ratio): over + if > 1.03, - if < 0.97
  6 lineup   DailyFaceoff at D: injury / game-time decision -> over -, under 0; on PP1 -> over +, under -;
             forward on lines 3-4 with no PP unit -> over -, under +; otherwise 0. A shop-gate veto (if given) -> over -.
  7 move     DK no-vig at D vs ESPN open price at the same line: moved toward the side by > 0.5 pt -> +, away -> -
agrees_n = number of + (of 7); disagrees_n = number of -. evidence_summary = one plain line."""
import os, json, math, glob
import numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__))
SIGS = ['champ', 'chal', 'shrunk', 'toi', 'opp', 'lineup', 'move']
CHAL = '3386583f18'
MIN_SEASON_G, TOI_BAND = 5, 1.0
def am2p(a): a = float(a); return -a / (-a + 100) if a < 0 else 100 / (a + 100)
def nv_pair(o, u):
    try: po, pu = am2p(o), am2p(u); return po / (po + pu)
    except Exception: return np.nan
def _sgn(x, band):
    if x is None or (isinstance(x, float) and math.isnan(x)): return 0
    return 1 if x > band else (-1 if x < -band else 0)
def _norm(s):
    import unicodedata, re
    return re.sub(r'[^a-z]', '', unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower())
def lineup_info(cap_dir, event, player):
    fs = sorted(glob.glob(os.path.join(os.path.dirname(cap_dir), '*', f'{event}_D.json')))  # dir = UTC start date, may be next day
    if not fs: return None
    f = fs[-1]
    d = json.load(open(f)); me = _norm(player); info = dict(found=False, inj=False, pp=None, ev=None)
    for lu in d.get('lineups', {}).values():
        for p in lu.get('players', []) or []:
            if _norm(p.get('name')) != me: continue
            info['found'] = True
            if p.get('injuryStatus') or p.get('gameTimeDecision') or p.get('categoryIdentifier') == 'oi': info['inj'] = True
            cat, grp = (p.get('categoryIdentifier') or ''), (p.get('groupIdentifier') or '')
            if cat == 'pp': info['pp'] = grp
            elif cat == 'ev': info['ev'] = grp; info['in_lineup'] = True
    return info
def season_toi(nhl_id, date_iso, logs):
    g = logs[(logs.playerId == nhl_id) & (logs.gameDate < date_iso)]
    cur = g[g.gameDate >= f'{date_iso[:4]}-09-01' if int(date_iso[5:7]) >= 9 else f'{int(date_iso[:4])-1}-09-01']
    if len(cur) >= MIN_SEASON_G: return cur.timeOnIcePerGame.mean() / 60
    return np.nan  # 2026-10-20: no last-30 fallback (it is mostly last season early on) -> no vote
def score_side(r, side, chal_p=None, lineup=None, veto=None, s_toi=None):
    """r: one D row with nv_over, p_model_over, p_shrunk_over/under, fresh_toi_r5, opp_slot_ratio, over_open/under_open."""
    o = side == 'over'
    nv = r['nv_over'] if o else 1 - r['nv_over']
    pm = r['p_model_over'] if o else 1 - r['p_model_over']
    s, why = {}, {}
    s['champ'] = _sgn(pm - nv, 0.005); why['champ'] = f'champion {(pm-nv)*100:+.1f} pts'
    if chal_p is not None and not pd.isna(chal_p):
        pc = chal_p if o else 1 - chal_p; s['chal'] = _sgn(pc - nv, 0.005); why['chal'] = f'challenger {(pc-nv)*100:+.1f} pts'
    else: s['chal'] = 0; why['chal'] = 'challenger not run'
    ps = r.get(f'p_shrunk_{side}')
    if ps is not None and not pd.isna(ps): s['shrunk'] = _sgn(ps - nv, 0.005); why['shrunk'] = f'shrunk form {(ps-nv)*100:+.1f} pts'
    else: s['shrunk'] = 0; why['shrunk'] = 'shrunk form n/a'
    t5 = r.get('fresh_toi_r5', r.get('toi_r5'))
    if s_toi is not None and not pd.isna(s_toi) and t5 is not None and not pd.isna(t5):
        d = t5 - s_toi; x = d if o else -d; s['toi'] = 1 if x >= TOI_BAND else (-1 if x <= -TOI_BAND else 0)
        why['toi'] = f'TOI last 5 {t5:.1f} vs this season {s_toi:.1f} ({d:+.1f} min)'
        t30 = r.get('toi_r30')  # display only (2026-10-19): r30 spans last season, so it can disagree with the signal
        if t30 is not None and not pd.isna(t30): why['toi'] += f'; last 30 incl. last season {t30:.1f} (reference only)'
    else: s['toi'] = 0; why['toi'] = f'TOI n/a (< {MIN_SEASON_G} games this season)'
    sr = r.get('opp_slot_ratio')
    if sr is not None and not pd.isna(sr):
        s['opp'] = _sgn((sr - 1) if o else (1 - sr), 0.03); why['opp'] = f'opponent allows {(sr-1)*100:+.0f}% to {r.get("slot", "slot")}'
    else: s['opp'] = 0; why['opp'] = 'opponent slot n/a'
    lv = 0; lw = 'lineup n/a'
    if lineup and lineup.get('found'):
        if lineup['inj'] and not lineup.get('in_lineup'): lv, lw = (-1 if o else 0), 'injured / out per DFO'
        elif lineup['inj']: lv, lw = (-1 if o else 0), 'injury/GTD flag'
        elif lineup['pp'] == 'pp1': lv, lw = (1 if o else -1), 'on PP1'
        elif lineup['pp'] is None and (lineup['ev'] or '') in ('f3', 'f4'): lv, lw = (-1 if o else 1), f'{lineup["ev"]} line, no PP'
        else: lv, lw = 0, f'{lineup["ev"] or "?"} {lineup["pp"] or "no PP"}'
    elif lineup is not None: lw = 'not in DFO lineup'
    if veto: lv, lw = (-1 if o else lv), f'shop veto: {veto}'
    s['lineup'], why['lineup'] = lv, lw
    nvo = nv_pair(r.get('over_open'), r.get('under_open'))
    if not pd.isna(nvo):
        mv = r['nv_over'] - nvo; s['move'] = _sgn(mv if o else -mv, 0.005); _v = (mv if o else -mv); why['move'] = f'no-vig moved {abs(_v)*100:.1f} pts ' + ('toward' if _v >= 0 else 'away from') + ' side since open'
    else: s['move'] = 0; why['move'] = 'open n/a'
    return s, why
def summary(player, side, line, s, why):
    pro = [why[k] for k in SIGS if s[k] > 0]; con = [why[k] for k in SIGS if s[k] < 0]
    return (f'{player} {side[0].upper()}{line}: agrees {len(pro)} of 7'
            + (f' ({"; ".join(pro)})' if pro else '') + (f'; against: {"; ".join(con)}' if con else '; nothing against'))
def chal_probs(date):
    f = os.path.join(HERE, 'challenger', 'shadow', f'{date}_D_{CHAL}.csv')
    if not os.path.exists(f): return {}
    c = pd.read_csv(f); return {(int(a), float(b)): p for a, b, p in zip(c.nhl_id, c.line, c.p_chal_over)}
def annotate(picks, date, gate=None, chal=None, logs=None):
    """Returns one row per (line, side) with sig_* columns, agrees_n, disagrees_n, evidence_summary."""
    import shrink
    P = picks if 'p_shrunk_over' in picks else shrink.annotate(picks)
    chal = chal_probs(date) if chal is None else chal
    logs = shrink.gamelogs() if logs is None else logs
    iso = f'{date[:4]}-{date[4:6]}-{date[6:]}'; cap = os.path.join(HERE, 'captures', date)
    veto = {}
    if gate is not None and 'shop_veto' in gate:
        veto = {(int(a), float(b)): v for a, b, v in zip(gate.nhl_id, gate.line, gate.shop_veto) if isinstance(v, str) and v.strip()}
    out = []
    for _, r in P.iterrows():
        lu = lineup_info(cap, r.event, r.player); st = season_toi(r.nhl_id, iso, logs)
        for side in ('over', 'under'):
            s, why = score_side(r, side, chal.get((int(r.nhl_id), float(r.line))), lu, veto.get((int(r.nhl_id), float(r.line))), st)
            out.append(dict(nhl_id=r.nhl_id, line=r.line, side=side, **{f'sig_{k}': {1: '+', -1: '-', 0: '0'}[v] for k, v in s.items()},
                            agrees_n=sum(v > 0 for v in s.values()), disagrees_n=sum(v < 0 for v in s.values()),
                            evidence_summary=summary(r.player, side, r.line, s, why)))
    return pd.DataFrame(out)
