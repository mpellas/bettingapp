"""Directional role-change check (shop lists only; never touches the model, picks/*_D.csv or grading).
predict.py sets `slot` from recent ice-time history (F_top6 / F_3rd / F_4th / D, '+PP1' if on PP1 in >=60% of last 5),
and opp_slot_ratio uses that slot. Today's DailyFaceoff lineup (ev_now/pp_now) can disagree.
Mapping: forwards f1/f2 -> top6, f3 -> 3rd, f4 -> 4th (top6 > 3rd > 4th); PP1 = pp_now=='pp1' vs '+PP1' in slot.
D slots carry no pair, and a forward/defense mismatch has no comparable line, so those compare PP1 only.
Direction: promotion (line up and PP1 not lost, or PP1 gained with line same) -> veto UNDER only;
demotion (line down and PP1 not gained, or PP1 lost with line same) -> veto OVER only;
mixed (line up + lost PP1, or line down + gained PP1) -> veto both sides. Missing lineup (no ev_now) -> no flag."""
import pandas as pd
EV_TIER = {'f1': 1, 'f2': 1, 'f3': 2, 'f4': 3}      # 1 = top6 (best)
SLOT_TIER = {'F_top6': 1, 'F_3rd': 2, 'F_4th': 3}

def _s(v):
    return '' if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()

def role_change(slot, ev_now, pp_now):
    """-> (kind, veto_over, veto_under, reason); kind in ('promotion','demotion','mixed','')."""
    slot, ev, pp = _s(slot), _s(ev_now).lower(), _s(pp_now).lower()
    if not slot or not ev or ev == 'nan': return '', False, False, ''
    base = slot.split('+')[0]
    line = 0                                            # +1 up, -1 down, 0 same / not comparable
    if base in SLOT_TIER and ev in EV_TIER:
        line = (SLOT_TIER[base] > EV_TIER[ev]) - (SLOT_TIER[base] < EV_TIER[ev])
    hist, now = '+PP1' in slot, pp == 'pp1'
    ppd = (now and not hist) - (hist and not now)      # +1 gained PP1, -1 lost
    if line == 0 and ppd == 0: return '', False, False, ''
    if line * ppd < 0: kind = 'mixed'
    elif line > 0 or ppd > 0: kind = 'promotion'
    else: kind = 'demotion'
    vo, vu = kind in ('demotion', 'mixed'), kind in ('promotion', 'mixed')
    return kind, vo, vu, f"role changed ({kind}: history {slot}, today {ev}/{pp or 'no_pp'})"

def role_mismatch(slot, ev_now, pp_now):   # back-compat: reason text or ''
    return role_change(slot, ev_now, pp_now)[3]
