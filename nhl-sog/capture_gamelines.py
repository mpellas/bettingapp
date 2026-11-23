"""DraftKings NHL game-line capture (puckline, total, moneyline). Data-only, paper.

Parses provider 100 (DraftKings) odds off the SAME free ESPN scoreboard event
already fetched by capture.py. No extra HTTP calls. Writes only to
captures/<date>/gamelines/<eid>_<tag>_HHMMSS.json; never read by SOG code,
close.py, or close_watch.
"""
import json, os


def _am(x):
    if x is None or x == '':
        return None
    s = str(x).strip().replace('\u2212', '-').replace('+', '')
    try:
        return int(float(s))
    except Exception:
        return None


def _ln(x):
    if x is None or x == '':
        return None
    s = str(x).strip().replace('\u2212', '-').lower()
    for ch in ('o', 'u', '+'):
        s = s.replace(ch, '')
    try:
        return float(s)
    except Exception:
        return None


def _side(block, key):
    b = (block or {}).get(key) or {}
    c = b.get('close') or {}
    o = b.get('open') or {}
    return {
        'line': _ln(c.get('line') if c.get('line') is not None else o.get('line')),
        'american': _am(c.get('odds')),
        'american_open': _am(o.get('odds')),
        'open_line': _ln(o.get('line')),
    }


def dk_odds(event):
    """Return the DraftKings (provider 100) odds object from a scoreboard event, or None."""
    comp = (event.get('competitions') or [{}])[0]
    for o in (comp.get('odds') or []):
        if str((o.get('provider') or {}).get('id')) == '100':
            return o
    return None


def from_event(event, tag, minutes_to_start, captured_dt):
    """Build the gamelines snapshot dict, or None if DK lines are absent."""
    odds = dk_odds(event)
    if not odds:
        return None
    comp = event['competitions'][0]
    teams = {c['homeAway']: c['team'] for c in comp['competitors']}
    home, away = teams['home'], teams['away']
    ps = odds.get('pointSpread') or {}
    tot = odds.get('total') or {}
    ml = odds.get('moneyline') or {}
    home_pl, away_pl = _side(ps, 'home'), _side(ps, 'away')
    over, under = _side(tot, 'over'), _side(tot, 'under')
    home_ml, away_ml = _side(ml, 'home'), _side(ml, 'away')
    # total line may live on the side or on odds.overUnder
    tot_line = over.get('line') or under.get('line') or odds.get('overUnder')
    if tot_line is not None:
        tot_line = float(tot_line)
        over['line'] = over.get('line') if over.get('line') is not None else tot_line
        under['line'] = under.get('line') if under.get('line') is not None else tot_line
    out = {
        'event': event.get('id'),
        'name': event.get('name'),
        'home': home.get('displayName'),
        'away': away.get('displayName'),
        'home_abbr': home.get('abbreviation'),
        'away_abbr': away.get('abbreviation'),
        'start_utc': event.get('date'),
        'captured_utc': captured_dt.isoformat(),
        'tag': tag,
        'minutes_to_start': round(minutes_to_start, 1),
        'book': 'DraftKings (ESPN provider 100)',
        'puckline': {'home': home_pl, 'away': away_pl} if (home_pl.get('american') is not None or away_pl.get('american') is not None) else None,
        'total': {'line': tot_line, 'over': over, 'under': under} if (over.get('american') is not None or under.get('american') is not None or tot_line is not None) else None,
        'moneyline': {'home': home_ml, 'away': away_ml} if (home_ml.get('american') is not None or away_ml.get('american') is not None) else None,
    }
    if not any(out[k] for k in ('puckline', 'total', 'moneyline')):
        return None
    return out


def counts(snap):
    n_pl = n_tot = n_ml = 0
    if snap.get('puckline'):
        n_pl = sum(1 for s in snap['puckline'].values() if s.get('american') is not None)
    if snap.get('total'):
        n_tot = sum(1 for k in ('over', 'under') if (snap['total'].get(k) or {}).get('american') is not None)
    if snap.get('moneyline'):
        n_ml = sum(1 for s in snap['moneyline'].values() if s.get('american') is not None)
    return {'puckline_sides': n_pl, 'total_sides': n_tot, 'moneyline_sides': n_ml}


def dump_atomic(obj, path):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(obj, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
