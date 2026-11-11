"""FREE CFB game-line capture: ESPN scoreboard (FBS, groups=80) DraftKings spread / total / moneyline with prices.
No Odds API credits. Each run saves the raw scoreboard JSON (never overwritten) and appends one row per game to
lines/snapshots.csv. Open/close are derived by grade_lines.py from these capture times (open = first capture,
also ESPN's own 'open' fields; close = last capture 0-30 min before kickoff, same definition as the NHL/NFL tracks).
Usage: python3 capture_lines.py [--dates 20261017,20261018] [--loop]   (--loop: every 30 min; every 4 min when a
kickoff is <= 45 min away; stops when no game today/tomorrow is still pre-game)"""
import argparse, csv, datetime as dt, json, os, time, urllib.request
from zoneinfo import ZoneInfo
HERE = os.path.dirname(os.path.abspath(__file__)); PT = ZoneInfo('America/Los_Angeles')
URL = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?dates={d}&groups=80&limit=300'
COLS = ['captured_utc', 'minutes_to_kickoff', 'event_id', 'date_pt', 'kickoff_utc', 'state', 'away', 'home', 'provider',
        'spread_home_line', 'spread_home_price', 'spread_away_line', 'spread_away_price', 'total', 'over_price', 'under_price',
        'ml_home', 'ml_away', 'open_spread_home_line', 'open_spread_home_price', 'open_spread_away_price', 'open_total',
        'open_over_price', 'open_under_price', 'open_ml_home', 'open_ml_away', 'home_score', 'away_score', 'raw_file']
def num(x):
    if x in (None, '', 'OFF', 'EVEN'): return 100 if x == 'EVEN' else None
    try: return float(str(x).replace('+', '').replace('o', '').replace('u', ''))
    except ValueError: return None
def g(d, *ks):
    for k in ks:
        if not isinstance(d, dict): return None
        d = d.get(k)
    return d
def capture(dates):
    now = dt.datetime.now(dt.timezone.utc); ts = now.strftime('%Y%m%dT%H%M%SZ'); rows, nxt = [], None
    for d in dates:
        raw = urllib.request.urlopen(urllib.request.Request(URL.format(d=d), headers={'User-Agent': 'cfb-lines/0.1 (personal research)'}), timeout=30).read()
        os.makedirs(f'{HERE}/raw/{d}', exist_ok=True); rf = f'raw/{d}/scoreboard_{ts}.json'
        open(f'{HERE}/{rf}', 'wb').write(raw)
        for e in json.loads(raw).get('events', []):
            c = e['competitions'][0]; kick = dt.datetime.fromisoformat(e['date'].replace('Z', '+00:00'))
            mins = round((kick - now).total_seconds() / 60, 1); state = e['status']['type']['state']
            if state == 'pre' and mins > 0: nxt = mins if nxt is None else min(nxt, mins)
            tm = {t['homeAway']: t for t in c['competitors']}
            o = (c.get('odds') or [{}])[0]; ps, tot, ml = o.get('pointSpread') or {}, o.get('total') or {}, o.get('moneyline') or {}
            rows.append(dict(captured_utc=now.isoformat(timespec='seconds'), minutes_to_kickoff=mins, event_id=e['id'], date_pt=d,
                kickoff_utc=e['date'], state=state, away=tm['away']['team']['abbreviation'], home=tm['home']['team']['abbreviation'],
                provider=g(o, 'provider', 'name'),
                spread_home_line=num(g(ps, 'home', 'close', 'line')), spread_home_price=num(g(ps, 'home', 'close', 'odds')),
                spread_away_line=num(g(ps, 'away', 'close', 'line')), spread_away_price=num(g(ps, 'away', 'close', 'odds')),
                total=num(g(tot, 'over', 'close', 'line')) or o.get('overUnder'), over_price=num(g(tot, 'over', 'close', 'odds')),
                under_price=num(g(tot, 'under', 'close', 'odds')), ml_home=num(g(ml, 'home', 'close', 'odds')), ml_away=num(g(ml, 'away', 'close', 'odds')),
                open_spread_home_line=num(g(ps, 'home', 'open', 'line')), open_spread_home_price=num(g(ps, 'home', 'open', 'odds')),
                open_spread_away_price=num(g(ps, 'away', 'open', 'odds')), open_total=num(g(tot, 'over', 'open', 'line')),
                open_over_price=num(g(tot, 'over', 'open', 'odds')), open_under_price=num(g(tot, 'under', 'open', 'odds')),
                open_ml_home=num(g(ml, 'home', 'open', 'odds')), open_ml_away=num(g(ml, 'away', 'open', 'odds')),
                home_score=tm['home'].get('score'), away_score=tm['away'].get('score'), raw_file=rf))
    f = f'{HERE}/snapshots.csv'; new = not os.path.exists(f)
    with open(f, 'a', newline='') as fh:
        w = csv.DictWriter(fh, COLS)
        if new: w.writeheader()
        w.writerows(rows)
    with_odds = sum(r['spread_home_line'] is not None for r in rows)
    print(f'{now.astimezone(PT):%Y-%m-%d %H:%M} PT: {len(rows)} games ({with_odds} with DK spread), next kickoff in {nxt} min')
    return nxt
def today_dates():
    t = dt.datetime.now(PT).date(); return [t.strftime('%Y%m%d'), (t + dt.timedelta(1)).strftime('%Y%m%d')]
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--dates'); ap.add_argument('--loop', action='store_true'); a = ap.parse_args()
    while True:
        try: nxt = capture(a.dates.split(',') if a.dates else today_dates())
        except Exception as e: print('capture failed:', e); nxt = 60
        if not a.loop: break
        if nxt is None: print('no pre-game games left; exiting'); break
        time.sleep(240 if nxt <= 45 else min(1800, max(60, (nxt - 44) * 60)))
