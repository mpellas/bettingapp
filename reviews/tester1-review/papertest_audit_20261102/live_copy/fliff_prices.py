"""Capture Fliff's real NHL shots-on-goal prices for the day's Fliff-check sides (approved by yinzerduck
2026-10-17 08:27 PT: spend Odds API credits, cap 10 credits per day).

Usage: python3 fliff_prices.py <YYYYMMDD> <list> [--mock DIR] [--cap 10] [--dry-run]
  <list> : the day's sheet (sheets/*.xlsx, 'Picks' tab), a csv with a 'status' column (rows 'Fliff check'),
           or the post text from build_sheet.py --post ("Fliff check: Player SIDE line (DK .., Fliff at .. or better)").
  --mock DIR : read <DIR>/events.json and <DIR>/<odds_event_id>.json instead of calling the API (testing; no credits).
  --dry-run  : resolve sides and events (free /events call) but make no paid call.

Per unique game: ONE call to /v4/sports/icehockey_nhl/events/{id}/odds with markets=player_shots_on_goal,
bookmakers=fliff,draftkings, oddsFormat=american. (Odds API bills per market x region; up to 10 bookmakers count
as one region, so adding draftkings does not change the cost; the cost is read back from x-requests-last and logged.)
Event lookup uses the free /events endpoint (0 credits). Before each paid call the per-day log
fliff_credits_<date>.csv (time_pt, event, cost, x_requests_remaining) is summed; the call is skipped if
spent + expected cost (last observed cost, default 1) would exceed the cap.
Outputs: captures/fliff_<date>_<HHMM>_<event>.json (raw), fliff_prices/<date>_<HHMM>.csv, summary on stdout.
Paper capture only: never places bets. Does not touch models/, challenger/, prereg/."""
import sys, os, re, json, glob, csv, argparse, unicodedata, urllib.request, datetime as dt
from zoneinfo import ZoneInfo
import pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); os.chdir(HERE)
PT = ZoneInfo('America/Los_Angeles'); BASE = 'https://api.the-odds-api.com/v4/sports/icehockey_nhl'

def key():  # same source as props-finder/find.py
    k = os.environ.get('ODDS_API_KEY')
    if not k: k = open('/workspace/nfl-props/data/secrets/odds_api_key').read().strip()
    return k

def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r), {k.lower(): v for k, v in r.headers.items()}

def norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\b(jr|sr|ii|iii)\b', '', s)
    return re.sub(r'[^a-z]', '', s)

def dec(a): a = float(a); return 1 + a / 100 if a > 0 else 1 + 100 / -a

POST_RE = re.compile(r'^Fliff check:\s*(.+?)\s+(OVER|UNDER)\s+([\d.]+)\s+\(DK\s*([+-]?\d+),\s*Fliff at\s*([+-]?\d+)', re.I)

def load_sides(path, date):
    if path.endswith('.xlsx'): df = pd.read_excel(path, sheet_name=0)
    elif path.endswith('.csv'): df = pd.read_csv(path)
    else:
        rows = [m.groups() for m in map(POST_RE.match, open(path).read().splitlines()) if m]
        df = pd.DataFrame(rows, columns=['player', 'side', 'line', 'dk_price', 'fliff_shop_at']).assign(status='Fliff check', game=None)
    if 'status' not in df: sys.exit(f'{path}: no status column. Pass the sheet (.xlsx), its csv, or the post text.')
    df = df[df.status.astype(str).str.strip().str.lower() == 'fliff check'].copy()
    df['side'] = df.side.str.upper(); df['line'] = df.line.astype(float)
    df['dk_price'] = df.dk_price.astype(float).astype(int); df['fliff_shop_at'] = df.fliff_shop_at.astype(float).astype(int)
    # nhl_id / gameId / espn event / game from the day's D files (player + line)
    D = [pd.read_csv(f) for f in sorted(glob.glob(f'picks/{date}_*.csv')) if 'GATE' not in f and 'verify' not in f]
    D = pd.concat(D, ignore_index=True) if D else pd.DataFrame(columns=['player', 'line', 'nhl_id', 'gameId', 'event', 'game'])
    D = D[[c for c in ('player', 'line', 'nhl_id', 'gameId', 'event', 'game') if c in D]].copy()
    D['_k'] = D.player.map(norm) + '|' + D.line.astype(float).astype(str); D = D.drop_duplicates('_k', keep='last')
    df['_k'] = df.player.map(norm) + '|' + df.line.astype(str)
    df = df.merge(D.drop(columns=['player', 'line']).rename(columns={'game': 'game_D', 'event': 'espn_event'}), on='_k', how='left')
    df['game'] = df['game'].where(df['game'].notna() & (df['game'].astype(str) != 'None'), df.get('game_D'))
    return df.drop(columns=['_k', 'game_D'], errors='ignore').reset_index(drop=True)

def match_event(game, events):
    if not isinstance(game, str) or ' at ' not in game: return None
    away, home = (norm(x) for x in game.split(' at ', 1))
    c = [e for e in events if norm(e['home_team']) == home and norm(e['away_team']) == away]
    return sorted(c, key=lambda e: e['commence_time'])[0] if c else None

def spent(log):
    if not os.path.exists(log): return 0, None
    r = list(csv.DictReader(open(log)))
    return sum(int(float(x['cost'] or 0)) for x in r), (int(float(r[-1]['cost'])) if r else None)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('date'); ap.add_argument('list')
    ap.add_argument('--mock'); ap.add_argument('--cap', type=int, default=10); ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--log-dir', default='.', help='where fliff_credits_<date>.csv lives (testing only)')
    ap.add_argument('--out-dir', default='.', help='root for captures/ and fliff_prices/ (testing only)')
    a = ap.parse_args(); date = a.date
    now = dt.datetime.now(PT); hhmm = now.strftime('%H%M')
    log = os.path.join(a.log_dir, f'fliff_credits_{date}.csv')
    sides = load_sides(a.list, date)
    if sides.empty: print(f'Fliff prices {date}: no Fliff-check sides in {a.list}; no credits used.'); return
    if a.mock: events = json.load(open(os.path.join(a.mock, 'events.json')))
    else: events, _ = get(f'{BASE}/events?apiKey={key()}')  # free endpoint (0 credits)
    sides['odds_event'] = [(match_event(g, events) or {}).get('id') for g in sides.game]
    os.makedirs(os.path.join(a.out_dir, 'captures'), exist_ok=True); os.makedirs(os.path.join(a.out_dir, 'fliff_prices'), exist_ok=True)
    books = {}; notes = []
    for ev in [e for e in dict.fromkeys(sides.odds_event) if e]:
        tot, last = spent(log); exp = last or 1
        prev = sorted(glob.glob(os.path.join(a.out_dir, 'captures', f'fliff_{date}_*_{ev}.json')))
        if prev and not a.mock and now.timestamp() - os.path.getmtime(prev[-1]) < 30 * 60:  # reuse a capture < 30 min old: 0 credits
            d = json.load(open(prev[-1])); cap_t = dt.datetime.fromtimestamp(os.path.getmtime(prev[-1]), PT)
            notes.append(f'event {ev}: reused capture {os.path.basename(prev[-1])} (< 30 min old, 0 credits)')
        elif tot + exp > a.cap: notes.append(f'cap reached ({tot}/{a.cap} credits today): skipped event {ev}'); continue
        elif a.dry_run: notes.append(f'dry run: would call event {ev} (~{exp} credit)'); continue
        else: d = cap_t = None
        if d is None:
          if a.mock: d, h = json.load(open(os.path.join(a.mock, f'{ev}.json'))), {'x-requests-last': '1', 'x-requests-remaining': 'mock'}
          else:
            d, h = get(f'{BASE}/events/{ev}/odds?apiKey={key()}&markets=player_shots_on_goal&bookmakers=fliff,draftkings&oddsFormat=american')
          cap_t = dt.datetime.now(PT)
          json.dump(d, open(os.path.join(a.out_dir, 'captures', f'fliff_{date}_{hhmm}_{ev}.json'), 'w'))
          new = not os.path.exists(log)
          with open(log, 'a', newline='') as f:
            w = csv.writer(f)
            if new: w.writerow(['time_pt', 'event', 'cost', 'x_requests_remaining'])
            w.writerow([cap_t.isoformat(timespec='seconds'), ev, h.get('x-requests-last', ''), h.get('x-requests-remaining', '')])
        for bk in d.get('bookmakers', []):
            for m in bk.get('markets', []):
                if m.get('key') != 'player_shots_on_goal': continue
                for o in m.get('outcomes', []):
                    books.setdefault((ev, bk['key']), {}).setdefault(norm(o.get('description', '')), []).append(
                        (o['name'].upper(), float(o['point']), int(o['price'])))
        books[(ev, '_t')] = cap_t.isoformat(timespec='seconds')
    out = []
    for _, s in sides.iterrows():
        ev, p = s.odds_event, norm(s.player)
        def find(bk):
            offers = [x for x in books.get((ev, bk), {}).get(p, []) if x[0] == s.side]
            same = [x for x in offers if x[1] == s.line]
            return (same or offers or [None])[0]
        f, k = find('fliff'), find('draftkings')
        if not ev: status = 'game not found in Odds API events'
        elif (ev, '_t') not in books: status = 'not captured (cap or dry run)'
        elif f is None and not books.get((ev, 'fliff')): status = 'not offered on Fliff (no Fliff shots market posted for this game yet)'
        elif f is None: status = 'not offered on Fliff'
        elif f[1] != s.line: status = 'different line'
        else: status = 'offered'
        fp = f[2] if f else None
        out.append(dict(date=date, player=s.player, game=s.game, side=s.side, line=s.line, nhl_id=s.get('nhl_id'), gameId=s.get('gameId'),
                        espn_event=s.get('espn_event'), odds_event=ev, fliff_status=status, fliff_line=f[1] if f else None, fliff_price=fp,
                        fliff_line_matches_list=(f is not None and f[1] == s.line), fliff_shop_at=s.fliff_shop_at,
                        beats_shop_at=(status == 'offered' and dec(fp) >= dec(s.fliff_shop_at)),
                        dk_price_list=s.dk_price, dk_line_list=s.line, dk_price_now=k[2] if k else None, dk_line_now=k[1] if k else None,
                        fliff_line_matches_dk=(f is not None and k is not None and f[1] == k[1]) if f else None,
                        capture_time_pt=books.get((ev, '_t')), list_file=os.path.basename(a.list)))
    O = pd.DataFrame(out); fn = os.path.join(a.out_dir, 'fliff_prices', f'{date}_{hhmm}.csv')
    if os.path.exists(fn): fn = fn[:-4] + now.strftime('%S') + '.csv'
    O.to_csv(fn, index=False)
    tot, _ = spent(log)
    rem = next((r['x_requests_remaining'] for r in list(csv.DictReader(open(log)))[-1:]), '?') if os.path.exists(log) else '?'
    print(f'Fliff prices, NHL shots on goal, {date} ({now.strftime("%-I:%M %p")} PT):')
    for x in out:
        if x['fliff_status'] == 'offered':
            v = 'beats' if x['beats_shop_at'] else 'worse than'
            print(f"- {x['player']} {x['side']} {x['line']:g}: Fliff {x['fliff_price']:+d}, {v} shop-at {x['fliff_shop_at']:+d} (DK {x['dk_price_list']:+d})")
        elif x['fliff_status'] == 'different line':
            print(f"- {x['player']} {x['side']} {x['line']:g}: different line on Fliff ({x['side']} {x['fliff_line']:g} at {x['fliff_price']:+d}); shop-at {x['fliff_shop_at']:+d} does not apply")
        else: print(f"- {x['player']} {x['side']} {x['line']:g}: {x['fliff_status']}")
    for n in notes: print('  note:', n)
    print(f'Credits: {tot} of {a.cap} used today; {rem} remaining on the account.  csv -> {fn}')

if __name__ == '__main__': main()
