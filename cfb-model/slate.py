"""PAPER ONLY. Model fair lines vs DraftKings/Fliff for today's CFB slate; flags sides clearing
thresholds (P4 3 pts, G5/FCS/mixed 5 pts) vs the actual book number. Never places bets.
Usage: python3 slate.py --reuse /workspace/cfb/oddsapi_X.json   (0 credits)
       python3 slate.py --live        (1 Odds API call: spreads,totals x us = 2 credits; refuses if remaining < 50)
       add --refresh to re-pull CFBD games for current season first (CFBD, not Odds API)."""
import sys, os, json, csv, datetime as dt, urllib.request
from model import *
NOW = dt.datetime.now(dt.timezone.utc); Y = NOW.year
def cfbd(path):
    rq = urllib.request.Request('https://api.collegefootballdata.com' + path, headers={'Authorization': 'Bearer ' + os.environ['CFBD_API_KEY']})
    return json.load(urllib.request.urlopen(rq, timeout=60))
if '--refresh' in sys.argv:
    json.dump(cfbd(f'/games?year={Y}&seasonType=both'), open(f'{D}/games_{Y}.json', 'w'))
if '--live' in sys.argv:
    url = f"https://api.the-odds-api.com/v4/sports/americanfootball_ncaaf/odds?apiKey={os.environ['ODDS_API_KEY']}&regions=us&markets=spreads,totals&bookmakers=draftkings,fliff&oddsFormat=american"
    r = urllib.request.urlopen(url, timeout=60); odds = json.load(r)
    rem = r.headers.get('x-requests-remaining'); used = r.headers.get('x-requests-last')
    os.makedirs(f'{D}/odds', exist_ok=True); fn = f"{D}/odds/oddsapi_{NOW.astimezone().strftime('%Y%m%d_%H%M')}.json"
    json.dump(odds, open(fn, 'w')); open(f'{D}/odds/credits.csv', 'a').write(f'{fn},{used},{rem}\n')
    print(f'Odds API: last call cost {used}, remaining {rem}; saved {fn}')
else:
    odds = json.load(open(sys.argv[sys.argv.index('--reuse') + 1]))
HOURS = float(sys.argv[sys.argv.index('--hours') + 1]) if '--hours' in sys.argv else 30  # only games starting within this window
games = load_games([Y - 1, Y]); m = fit(games, NOW)
upc = [g for g in games if not g['completed'] and g['season'] == Y]
def find(o):
    best = None
    for g in upc:
        ct = dt.datetime.fromisoformat(o['commence_time'].replace('Z', '+00:00'))
        if abs((ct - g['_t']).total_seconds()) > 36 * 3600: continue
        if o['home_team'].startswith(g['homeTeam'] + ' ') and o['away_team'].startswith(g['awayTeam'] + ' '):
            k = len(g['homeTeam']) + len(g['awayTeam'])
            if not best or k > best[0]: best = (k, g)
    return best and best[1]
pt = lambda t: dt.datetime.fromisoformat(t.replace('Z', '+00:00')).astimezone().strftime('%a %-I:%M %p PT')
rows = []
for o in odds:
    g = find(o)
    ct = dt.datetime.fromisoformat(o['commence_time'].replace('Z', '+00:00'))
    if not g or ct <= NOW or ct > NOW + dt.timedelta(hours=HOURS): continue
    pr = predict(m, g['homeTeam'], g['awayTeam'], g['neutralSite'])
    if not pr: continue
    lv = sorted([level(g['homeConference'], g['homeClassification'], g['homeTeam']), level(g['awayConference'], g['awayClassification'], g['awayTeam'])])
    lvl = 'P4' if lv == ['P4', 'P4'] else ('G5' if set(lv) <= {'P4', 'G5'} else '/'.join(lv)); thr = 3 if lvl == 'P4' else 5
    ng = min(m['n'].get(g['homeTeam'], 0), m['n'].get(g['awayTeam'], 0))
    for b in o.get('bookmakers', []):
        for mk in b['markets']:
            for oc in mk['outcomes']:
                if mk['key'] == 'spreads':
                    fair = pr[0] if oc['name'] == o['home_team'] else -pr[0]
                    edge = oc['point'] - fair; side = f"{oc['name']} {oc['point']:+g}"; fl = f'{fair:+.1f}'
                else:
                    edge = (pr[1] - oc['point']) * (1 if oc['name'] == 'Over' else -1)
                    side = f"**{oc['name'].upper()}** {oc['point']:g}"; fl = f'{pr[1]:.1f}'
                rows.append(dict(time=pt(o['commence_time']), game=f"{g['awayTeam']} @ {g['homeTeam']}", odds_event=f"{o['away_team']} @ {o['home_team']}", level=lvl, book=b['key'],
                    market=mk['key'], side=side, price=oc['price'], model_fair=fl, edge_pts=round(edge, 1), thr=thr,
                    min_games=ng, clears=edge >= thr and ng >= 4))
os.makedirs('picks', exist_ok=True); fn = f"picks/slate_{NOW.astimezone().strftime('%Y%m%d_%H%M')}.csv"
if rows:
    with open(fn, 'w', newline='') as f: w = csv.DictWriter(f, rows[0].keys()); w.writeheader(); w.writerows(rows)
q = sorted([r for r in rows if r['clears']], key=lambda r: -r['edge_pts'])
print(f'{len(odds)} odds events, {len({r["game"] for r in rows})} matched; {len(q)} sides clear (PAPER ONLY; edge = model fair vs posted number, juice not priced in; backtest shows no proven edge). Saved {fn}')
for r in q: print(f"  {r['time']} | {r['game']} [{r['level']}] {r['book']}: {r['side']} ({r['price']:+d}) model {r['model_fair']} edge {r['edge_pts']}")
