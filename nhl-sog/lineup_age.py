"""12-hour stale-lineup skip (added 2026-11-03, testers' approved rule; Tester2).
A side is skipped when the DailyFaceoff lineup used for the gate/role checks (DFO 'updatedAt', stored as dfo_updated
in the GATE csv) is more than 12 hours older than the list build time. Missing/unparseable timestamp -> SKIP
(we cannot prove the lineup is fresh). Exactly 12h is still fresh. Never touches the model, features or --rescore."""
from datetime import datetime, timezone
import pandas as pd
STALE_H = 12.0
REASON_STALE = 'lineup stale >12h'
REASON_MISSING = 'lineup timestamp missing'

def age_hours(updated, now=None):
    """Hours between DFO updatedAt and now (UTC). None if missing/unparseable."""
    if updated is None or (isinstance(updated, float) and pd.isna(updated)) or str(updated).strip() in ('', 'nan', 'None'):
        return None
    try:
        t = pd.Timestamp(str(updated))
        t = t.tz_localize('UTC') if t.tzinfo is None else t.tz_convert('UTC')
    except Exception:
        return None
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    now = now.tz_localize('UTC') if now.tzinfo is None else now.tz_convert('UTC')
    return (now - t).total_seconds() / 3600.0

def stale_reason(updated, now=None):
    """'' if fresh, else the skip reason text."""
    a = age_hours(updated, now)
    if a is None: return REASON_MISSING
    if a > STALE_H: return f'{REASON_STALE} ({a:.1f}h old)'
    return ''

# ---- 2026-11-03 last-game fallback (user-approved; Tester2) ----
# When DFO is >12h old (or missing), instead of skipping: fetch the team's most recent completed NHL.com game boxscore.
# Boxscores list who dressed (not lines), so a side passes if the player dressed last game AND DFO lists him in a slot.
# NHL.com fetch failure -> keep the old skip. lineup_source: dfo_fresh / last_game_fallback / stale_skip.
import requests
NHL = 'https://api-web.nhle.com/v1'
REASON_NOT_DRESSED = 'lineup stale >12h, disagrees with last game (not dressed)'
REASON_NOT_IN_DFO = 'lineup stale >12h, not in DFO lineup'
REASON_NO_FALLBACK = 'lineup stale >12h, fallback unavailable'
_CACHE = {}   # (team, today_game_id) -> set of dressed playerIds, or None on failure (per run)

def _get(url):
    return requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=(10, 20)).json()

def _team_abbrev(team, today_game_id, get):
    d = get(f'{NHL}/gamecenter/{int(today_game_id)}/boxscore')
    for side in ('awayTeam', 'homeTeam'):
        t = d[side]; names = {str((t.get(k) or {}).get('default', '')).lower() for k in ('commonName', 'placeName', 'name')}
        full = f"{(t.get('placeName') or {}).get('default','')} {(t.get('commonName') or {}).get('default','')}".lower()
        if str(team).lower() == full or any(n and n in str(team).lower() for n in names if n): return t['abbrev']
    raise ValueError(f'team {team} not in game {today_game_id}')

def last_game_dressed(team, today_game_id, get=None):
    """Set of NHL playerIds who dressed in the team's most recent completed game; None if unavailable. Cached."""
    key = (team, str(today_game_id))
    if key in _CACHE: return _CACHE[key]
    get = get or _get
    try:
        ab = _team_abbrev(team, today_game_id, get)
        g = [x for x in get(f'{NHL}/club-schedule-season/{ab}/now')['games'] if x.get('gameState') in ('OFF', 'FINAL')]
        last = max(g, key=lambda x: x['startTimeUTC'])
        box = get(f"{NHL}/gamecenter/{last['id']}/boxscore"); bs = box['playerByGameStats']
        side = 'awayTeam' if str(box['awayTeam']['abbrev']) == ab else 'homeTeam'
        ids = {int(p['playerId']) for grp in ('forwards', 'defense', 'goalies') for p in bs[side].get(grp, [])}
        _CACHE[key] = ids or None
    except Exception:
        _CACHE[key] = None
    return _CACHE[key]

def stale_check(updated, team, today_game_id, nhl_id, in_dfo, now=None, get=None):
    """(reason, lineup_source). reason '' = passes the stale check."""
    if not stale_reason(updated, now): return '', 'dfo_fresh'
    ids = last_game_dressed(team, today_game_id, get)
    if ids is None: return REASON_NO_FALLBACK, 'stale_skip'
    if not in_dfo: return REASON_NOT_IN_DFO, 'last_game_fallback'
    try: dressed = int(float(nhl_id)) in ids
    except Exception: dressed = False
    return ('' if dressed else REASON_NOT_DRESSED), 'last_game_fallback'
