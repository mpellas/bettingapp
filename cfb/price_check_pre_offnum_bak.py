"""CFB Saturday price check: one Odds API call (spreads,totals; draftkings,fliff). Daily cap 20 credits."""
import json, os, sys, csv, math, datetime as dt, urllib.request, difflib
HHMM = sys.argv[1]; DATE = os.environ.get('CFB_DATE') or dt.datetime.now().strftime('%Y%m%d'); CAP = 20
if not (len(HHMM) == 4 and HHMM.isdigit()): print('usage: price_check.py HHMM [--reuse oddsfile]'); sys.exit(1)
REUSE = sys.argv[sys.argv.index('--reuse') + 1] if '--reuse' in sys.argv else None
LED = f'/workspace/cfb/credits_{DATE}.csv'
K = os.environ.get('ODDS_API_KEY') or open('/workspace/nfl-props/data/secrets/odds_api_key').read().strip()
def get(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r), r.headers.get('x-requests-remaining'), r.headers.get('x-requests-last'), r.headers.get('x-requests-used')
used_today = 0
if os.path.exists(LED):
    used_today = sum(int(r['credits']) for r in csv.DictReader(open(LED)))
if REUSE:
    data = json.load(open(REUSE)); print('reusing saved odds', REUSE, 'events', len(data), 'used today', used_today)
else:
    _, rem0, _, _ = get(f'https://api.the-odds-api.com/v4/sports?apiKey={K}')  # free
    print('remaining before', rem0, 'used today before', used_today)
    if used_today + 2 > CAP: print('CAP STOP'); sys.exit(2)
    data, rem, last, used = get(f'https://api.the-odds-api.com/v4/sports/americanfootball_ncaaf/odds?apiKey={K}&regions=us&markets=spreads,totals&bookmakers=draftkings,fliff&oddsFormat=american')
    cost = int(last or 0) if last else int(rem0) - int(rem)
    new = not os.path.exists(LED)
    with open(LED, 'a', newline='') as f:
        w = csv.writer(f)
        if new: w.writerow(['run_hhmm', 'credits', 'remaining_after'])
        w.writerow([HHMM, cost, rem])
    json.dump(data, open(f'/workspace/cfb/oddsapi_{DATE}_{HHMM}.json', 'w'))
    print('cost', cost, 'remaining after', rem, 'events', len(data))
# ESPN capture for event ids / conferences
# Any level (user Go, Oct 17): FBS (groups=80) + FCS (groups=81) captures merged; level per team, mixed game = lower level.
P4 = {'1', '4', '5', '8'}; G5 = {'151', '12', '15', '17', '37', '9', '18'}
def tlevel(t):
    c = t.get('conferenceId')
    if c in P4 or t.get('id') == '87': return 'Power 4'
    if c in G5: return 'Group of 5'
    return 'FCS'
RANK = {'Power 4': 0, 'Group of 5': 1, 'FCS': 2}
GAP = {'Power 4': 3.0, 'Group of 5': 5.0, 'FCS': 5.0}
esp_events = {}
for gp in ('g80', 'g81'):
    fp_ = f'/workspace/cfb/captures/{DATE}_{HHMM}_{gp}.json'
    if not os.path.exists(fp_): fp_ = f'/workspace/cfb/captures/{DATE}_{HHMM}.json'
    for e in json.load(open(fp_))['events']: esp_events[e['id']] = e
eg = []
for e in esp_events.values():
    c = e['competitions'][0]; t = {x['homeAway']: x['team'] for x in c['competitors']}
    level = max((tlevel(t[s]) for s in t), key=RANK.get)
    eg.append(dict(id=e['id'], ko=dt.datetime.fromisoformat(e['date'].replace('Z', '+00:00')), home=t['home']['displayName'], away=t['away']['displayName'], ha=t['home']['abbreviation'], aa=t['away']['abbreviation'], level=level))
def match(g):
    ko = dt.datetime.fromisoformat(g['commence_time'].replace('Z', '+00:00'))
    best, bs = None, 0
    for e in eg:
        if abs((e['ko'] - ko).total_seconds()) > 3 * 3600: continue
        s = difflib.SequenceMatcher(None, g['home_team'], e['home']).ratio() + difflib.SequenceMatcher(None, g['away_team'], e['away']).ratio()
        if s > bs: best, bs = e, s
    return best if bs > 1.4 else None
def imp(a): return 100 / (a + 100) if a > 0 else -a / (-a + 100)
def worst(p):
    a = 100 * (1 - p) / p if p < 0.5 else -100 * p / (1 - p)
    return math.ceil(a - 1e-9)
now = dt.datetime.now(dt.timezone.utc)
lo, hi = now + dt.timedelta(minutes=30), now + dt.timedelta(hours=4.5)
PT = dt.timezone(dt.timedelta(hours=-7))
rows = []; considered = 0; window_major = []; unmatched = []
for g in data:
    ko = dt.datetime.fromisoformat(g['commence_time'].replace('Z', '+00:00'))
    if not (lo <= ko <= hi): continue
    e = match(g)
    if not e: unmatched.append(f"{g['away_team']} @ {g['home_team']}"); continue
    bk = {b['key']: {m['key']: m['outcomes'] for m in b['markets']} for b in g.get('bookmakers', [])}
    window_major.append(f"[{e['level']}] {g['away_team']} @ {g['home_team']} ({ko.astimezone(PT):%-I:%M %p} PT) books={sorted(bk)}")
    if 'draftkings' not in bk or 'fliff' not in bk: continue
    for mk in ('spreads', 'totals'):
        dk, fl = bk['draftkings'].get(mk), bk['fliff'].get(mk)
        if not dk or not fl or len(dk) != 2: continue
        pa, pb = imp(dk[0]['price']), imp(dk[1]['price'])
        for i, o in enumerate(dk):
            considered += 1
            fair = (pa if i == 0 else pb) / (pa + pb)
            fo = [x for x in fl if x['name'] == o['name'] and x.get('point') == o.get('point')]
            if not fo: continue
            fp = fo[0]['price']; be = imp(fp); edge = (fair - be) * 100
            if mk == 'spreads':
                side = 'home' if o['name'] == g['home_team'] else 'away'
                label = f"{o['name']} {o['point']:+g}"
                ev_side = f"{e['ha'] if side=='home' else e['aa']} {o['point']:+g}"
            else:
                side = o['name'].lower(); label = f"{o['name'].upper()} {o['point']:g}"; ev_side = f"{o['name'].upper()} {o['point']:g}"
            rows.append(dict(level=e['level'], event_id=e['id'], odds_id=g['id'], game=f"{g['away_team']} @ {g['home_team']}", kickoff_pt=ko.astimezone(PT).strftime('%-I:%M %p'), kickoff_utc=g['commence_time'],
                market='spread' if mk == 'spreads' else 'total', side=side, line=o['point'], label=label, ev_side=ev_side, dk_price=o['price'], dk_fair=round(fair, 4),
                fliff_price=fp, fliff_be=round(be, 4), edge_pts=round(edge, 2), gap_req=GAP[e['level']], worst_fliff=worst(fair - GAP[e['level']] / 100), qualifies=edge >= GAP[e['level']]))
out = f'/workspace/cfb/leans/{DATE}_{HHMM}.csv'
with open(out, 'w', newline='') as f:
    if rows:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    else: f.write('note\nno games (any level) in window with both DK and Fliff\n')
print('unmatched odds games in window:', unmatched); print('window games (any level):'); [print(' ', x) for x in window_major]
print('sides with same-line on both books', len(rows), 'of', considered)
for r in sorted(rows, key=lambda r: -r['edge_pts'])[:12]: print(r['game'], r['label'], r['dk_price'], r['fliff_price'], r['edge_pts'], r['qualifies'], r['level'])
json.dump([r for r in rows if r['qualifies']], open(f'/workspace/cfb/leans/{DATE}_{HHMM}_q.json', 'w'))
