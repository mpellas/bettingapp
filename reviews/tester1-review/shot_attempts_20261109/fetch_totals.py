"""Cache DK open/close game totals from ESPN's public odds feed into cache/espn_totals.csv. Polite: 0.5 s between calls.
python3 fetch_totals.py live   -> events in nhl-sog graded/*.csv + the Nov 5 GATE
python3 fetch_totals.py s2025  -> all 2025-26 regular-season games (scoreboard by date, then odds per event)"""
import sys, os, time, json, glob, urllib.request
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); C = os.path.join(HERE, 'cache', 'espn_totals.csv')
def get(u):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(2 + 3 * i)
    return None
def tot(x):
    try: return float((x or {}).get('total', {}).get('american'))
    except Exception: return None
def odds(ev):
    d = get(f'https://sports.core.api.espn.com/v2/sports/hockey/leagues/nhl/events/{ev}/competitions/{ev}/odds'); time.sleep(0.5)
    items = {str(it.get('provider', {}).get('id')): it for it in (d or {}).get('items', [])}
    for pid, name in (('100', 'DraftKings'), ('58', 'ESPN BET')):   # DK first; ESPN BET fallback (2025-26 proxy only)
        it = items.get(pid)
        if it:
            return dict(open_total=tot(it.get('open')), close_total=tot(it.get('close')), ou=it.get('overUnder'), provider=name)
    return dict(open_total=None, close_total=None, ou=None, provider=None)
def main(mode):
    have = pd.read_csv(C, dtype={'event': str}) if os.path.exists(C) else pd.DataFrame(columns=['event'])
    done = set(have.event.astype(str)); rows = []
    if mode == 'live':
        evs = {}
        for f in glob.glob('/workspace/nhl-sog/graded/2026*.csv') + ['/workspace/nhl-sog/picks/20261105_D_1239_GATE.csv']:
            d = pd.read_csv(f, usecols=['event', 'game'])
            evs.update({str(e): g for e, g in zip(d.event, d.game)})
        todo = [(e, g, None) for e, g in evs.items() if e not in done]
    else:
        todo = []
        for day in pd.date_range('2025-10-07', '2026-04-17'):
            sb = get(f'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={day:%Y%m%d}'); time.sleep(0.5)
            for e in (sb or {}).get('events', []):
                if str(e['id']) in done: continue
                if (e.get('season') or {}).get('type') not in (2, None): continue
                todo.append((str(e['id']), e['name'], e['date']))
        print('events to fetch', len(todo), flush=True)
    for i, (e, g, dt) in enumerate(todo):
        rows.append(dict(event=e, game=g, start_utc=dt, mode=mode, **odds(e)))
        if i % 50 == 0:
            print(i, e, g, rows[-1], flush=True)
            pd.concat([have, pd.DataFrame(rows)]).to_csv(C, index=False)
    pd.concat([have, pd.DataFrame(rows)]).to_csv(C, index=False); print('done', len(rows))
if __name__ == '__main__': main(sys.argv[1])
