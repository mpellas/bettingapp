"""FREE inactives snapshot, label "I" (shadow; approved 2026-10-16). Not part of the pinned prereg code:
it lives outside src/nflprops, writes outside data/snapshots, and only IMPORTS snapshot helpers read-only.

For every NFL game kicking off in [--min, --max] minutes (default 60-90; NFL inactives post ~90 min before kick),
captures once per game (idempotent):
  * DraftKings prop targets via ESPN core propBets (same parser as nflprops.snapshot; no prices exist there)
  * game odds list (spread / total / moneyline, with prices)
  * ESPN game summary 'injuries' block (status per player: Out / Doubtful / Questionable / Inactive ...)
and writes data/snapshots_inactives/<PT date>/<event>_I_<UTC>.json (raw) + <event>_I_<UTC>_lines.csv where every
prop line carries the player's injury status, the status of teammates at the same position marked Out/Inactive
("usage_shift" candidates), and the line delta vs the latest earlier loop capture (data/lines not needed).
Usage: .venv/bin/python sidecars/inactives/inactives_snapshot.py [--min 60 --max 90] [--force]"""
import argparse, csv, datetime as dt, glob, json, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'src'))
from nflprops.snapshot import _get, parse_items, SITE, CORE, PT, SNAP  # read-only reuse
OUT = os.path.join(ROOT, 'data', 'snapshots_inactives')
SUM = 'https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary'
ROSTER_POS = 'https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{id}'
OUTSTAT = {'out', 'inactive', 'injured reserve', 'doubtful', 'suspension'}

def done(day, ev):
    return bool(glob.glob(os.path.join(OUT, day, f'{ev}_I_*.json')))

def prev_lines(ev):
    """Latest loop capture's DK targets for this event: {(espn_id, market): line}."""
    fs = sorted(glob.glob(str(SNAP / '*' / f'{ev}_100_*_p*.json')))
    if not fs: return {}
    ts = fs[-1].split('_')[-2]; items = []
    for f in fs:
        if f.split('_')[-2] == ts: items += json.load(open(f)).get('items', [])
    return {(r['espn_id'], r['market']): r['line'] for r in parse_items(items)}, ts

def capture_event(e, now, day):
    ev = e['id']; ts = now.strftime('%Y%m%dT%H%M%SZ')
    rec = {'label': 'I', 'event_id': ev, 'name': e.get('shortName'), 'kickoff_utc': e['date'],
           'captured_at_utc': now.isoformat(timespec='seconds'),
           'minutes_to_kickoff': round((dt.datetime.fromisoformat(e['date'].replace('Z', '+00:00')) - now).total_seconds() / 60, 1)}
    ro = _get(CORE.format(ev=ev), {'limit': 100}); rec['odds'] = ro.json() if ro.status_code == 200 else None
    items, page = [], 1
    while True:
        rp = _get(CORE.format(ev=ev) + '/100/propBets', {'lang': 'en', 'region': 'us', 'limit': 1000, 'page': page})
        if rp.status_code != 200: break
        d = rp.json(); items += d.get('items', [])
        if page >= int(d.get('pageCount') or 1) or page >= 10: break
        page += 1
    rec['prop_items'] = items
    sm = _get(SUM, {'event': ev}); s = sm.json() if sm.status_code == 200 else {}
    inj = {}
    for t in s.get('injuries', []):
        for i in t.get('injuries', []):
            a = i.get('athlete', {})
            inj[str(a.get('id'))] = dict(team=t['team']['abbreviation'], name=a.get('displayName'), status=i.get('status'),
                                         pos=(a.get('position') or {}).get('abbreviation'), date=i.get('date'))
    rec['injuries'] = inj
    os.makedirs(os.path.join(OUT, day), exist_ok=True)
    base = os.path.join(OUT, day, f'{ev}_I_{ts}')
    json.dump(rec, open(base + '.json', 'w'))
    rows = parse_items(items)
    pl = prev_lines(ev); prev, pts = (pl if pl else ({}, None))
    outs = [v for v in inj.values() if (v['status'] or '').lower() in OUTSTAT]
    with open(base + '_lines.csv', 'w', newline='') as f:
        w = csv.writer(f); w.writerow(['event_id', 'game', 'kickoff_utc', 'minutes_to_kickoff', 'espn_id', 'market', 'line_I',
                                       'line_prev_capture', 'prev_capture_utc', 'line_delta', 'player_injury_status', 'team_out_list'])
        for r in rows:
            lp = prev.get((r['espn_id'], r['market'])); st = inj.get(r['espn_id'], {}).get('status', '')
            w.writerow([ev, e.get('shortName'), e['date'], rec['minutes_to_kickoff'], r['espn_id'], r['market'], r['line'],
                        lp, pts, (r['line'] - lp) if lp is not None else '', st,
                        '; '.join(f"{o['team']} {o['pos']} {o['name']} ({o['status']})" for o in outs)])
    return dict(event=ev, game=e.get('shortName'), lines=len(rows), injuries=len(inj), out=len(outs), file=base + '_lines.csv')

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--min', type=float, default=60); ap.add_argument('--max', type=float, default=90)
    ap.add_argument('--force', action='store_true'); a = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc); day = now.astimezone(PT).strftime('%Y-%m-%d')
    sb = _get(SITE, {'limit': 400}).json(); res = []
    for e in sb.get('events', []):
        mins = (dt.datetime.fromisoformat(e['date'].replace('Z', '+00:00')) - now).total_seconds() / 60
        if not (a.min <= mins <= a.max) and not a.force: continue
        if done(day, e['id']) and not a.force: res.append(dict(event=e['id'], skipped='already captured')); continue
        res.append(capture_event(e, now, day))
    print(json.dumps({'captured_at_pt': now.astimezone(PT).isoformat(timespec='seconds'), 'window_min': [a.min, a.max], 'results': res}, indent=1))

if __name__ == '__main__': main()
