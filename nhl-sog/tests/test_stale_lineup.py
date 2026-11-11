"""12h stale-lineup skip (2026-11-03): fresh passes, 13h-old skipped, missing timestamp skipped."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd, build_sheet as B, lineup_age as L
NOW = '2026-11-03T20:00:00Z'   # 12:00 PM PT build time
assert L.stale_reason('2026-11-03T17:00:00.000Z', NOW) == ''                      # 3h old -> fresh
assert L.stale_reason('2026-11-03T08:00:00Z', NOW) == ''                          # exactly 12h -> fresh
assert L.stale_reason('2026-11-03T07:00:00Z', NOW) == 'lineup stale >12h (13.0h old)'
assert L.stale_reason(None, NOW) == L.stale_reason(float('nan'), NOW) == L.stale_reason('', NOW) == 'lineup timestamp missing'
assert L.stale_reason('garbage', NOW) == 'lineup timestamp missing'
print('13h:', L.stale_reason('2026-11-03T07:00:00Z', NOW))
def row(p, stale, ev=-0.01):
    return dict(player=p, _side='under', _edge=.08, _rmargin=.05, _ev=ev, _role='', _veto='', _stale=stale,
                flag_shop_ok='yes', flag_within_12_novig='yes', flag_slot_veto='no', flag_milestone='yes', flag_lineup_gate='yes')
df = pd.DataFrame([row('Fresh', L.stale_reason('2026-11-03T17:00:00Z', NOW)),
                   row('Old13h', L.stale_reason('2026-11-03T07:00:00Z', NOW)),
                   row('NoTS', L.stale_reason(None, NOW)),
                   row('Old13hDK', L.stale_reason('2026-11-03T07:00:00Z', NOW), ev=0.03),
                   row('FreshDK', '', ev=0.03)])
S = B.assign_status(df, '_rmargin').set_index('player')
print(S[['status', 'status_reason']].to_string())
assert S.at['Fresh', 'status'] == 'Fliff check'
assert S.at['FreshDK', 'status'] == 'DK bet'
for p in ('Old13h', 'NoTS', 'Old13hDK'): assert S.at[p, 'status'] == 'Skipped', p
assert S.at['Old13h', 'status_reason'].startswith('lineup stale >12h')
assert S.at['NoTS', 'status_reason'].startswith('lineup timestamp missing')
assert 'lineup stale, not listed' in S.at['Old13hDK', 'status_reason']
print('ok')
# ---- 2026-11-03 last-game fallback (mock NHL.com) ----
def mock(url):
    if url.endswith('/gamecenter/2026020236/boxscore'):
        return {'awayTeam': {'abbrev': 'UTA', 'placeName': {'default': 'Utah'}, 'commonName': {'default': 'Mammoth'}},
                'homeTeam': {'abbrev': 'TOR', 'placeName': {'default': 'Toronto'}, 'commonName': {'default': 'Maple Leafs'}}}
    if url.endswith('/club-schedule-season/UTA/now'):
        return {'games': [{'id': 2026020200, 'gameState': 'OFF', 'startTimeUTC': '2026-10-30T00:00:00Z'},
                          {'id': 2026020220, 'gameState': 'OFF', 'startTimeUTC': '2026-11-01T00:00:00Z'},
                          {'id': 2026020236, 'gameState': 'FUT', 'startTimeUTC': '2026-11-04T00:00:00Z'}]}
    if url.endswith('/gamecenter/2026020220/boxscore'):
        return {'awayTeam': {'abbrev': 'COL'}, 'homeTeam': {'abbrev': 'UTA'},
                'playerByGameStats': {'awayTeam': {'forwards': [{'playerId': 9}]},
                                      'homeTeam': {'forwards': [{'playerId': 8475314}], 'defense': [{'playerId': 2}], 'goalies': []}}}
    raise RuntimeError(url)
OLD = '2026-11-01T20:40:08Z'
L._CACHE.clear()
assert L.stale_check('2026-11-03T17:00:00Z', 'Utah Mammoth', 2026020236, 1, True, NOW, mock) == ('', 'dfo_fresh')
assert L.stale_check(OLD, 'Utah Mammoth', 2026020236, 8475314, True, NOW, mock) == ('', 'last_game_fallback')
assert L.stale_check(OLD, 'Utah Mammoth', 2026020236, 9, True, NOW, mock) == (L.REASON_NOT_DRESSED, 'last_game_fallback')
assert L.stale_check(None, 'Utah Mammoth', 2026020236, 8475314, False, NOW, mock) == (L.REASON_NOT_IN_DFO, 'last_game_fallback')
def boom(url): raise RuntimeError('down')
L._CACHE.clear()
assert L.stale_check(OLD, 'Utah Mammoth', 2026020236, 8475314, True, NOW, boom) == (L.REASON_NO_FALLBACK, 'stale_skip')
print('fallback ok')
