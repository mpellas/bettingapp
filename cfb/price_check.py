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
# ---- Off-number conversion (added Oct 24). Empirical CFB landing tables, NOT NFL key numbers. See NOTES.md + hist/.
LT = json.load(open('/workspace/cfb/hist/landing_tables.json'))
def _anchor(tab, x, lo, hi):
    a = min(max(round(x * 2) / 2, lo), hi); return f'{a:g}', tab[f'{a:g}']['p']
def _mass(h, a, b):
    """P(X in [a,b]) for integer-valued X, endpoints that are integers count half (push half-way); a<=b."""
    tot, ks = 0.0, []
    for k in range(math.ceil(a), math.floor(b) + 1):
        w = 0.5 if k in (a, b) else 1.0; v = w * h.get(str(k), 0.0); tot += v; ks.append(f"{k}:{w:g}x{h.get(str(k), 0.0):.3f}")
    return tot, ';'.join(ks)
def convert_spread(fair, ld, lf, is_fav, home_abs):
    """Side gets ld points at DK, lf at Fliff. Side wins iff side_margin + L > 0. Moving ld->lf adds/removes the
    probability that side_margin lands in [-max,-min]. side_margin = fav margin if side is favorite, else -fav margin.
    Table conditioned on closing |spread| near the DK number (kernel +/-3)."""
    an, h = _anchor(LT['spread'], home_abs, 0.5, 30)
    hs = h if is_fav else {str(-int(k)): v for k, v in h.items()}
    lo, hi = sorted((-lf, -ld)); m, ks = _mass(hs, lo, hi)
    return min(max(fair + (m if lf > ld else -m), 0.01), 0.99), f'spread|{an}', ks
def convert_total(fair, ld, lf, side):
    an, h = _anchor(LT['total'], ld, 35, 85)
    lo, hi = sorted((ld, lf)); m, ks = _mass(h, lo, hi)
    better = (lf > ld) if side == 'under' else (lf < ld)
    return min(max(fair + (m if better else -m), 0.01), 0.99), f'total|{an}', ks
now = dt.datetime.now(dt.timezone.utc)
if REUSE:  # evaluate the window as of the saved run time, so a replay matches what that pass saw
    now = dt.datetime.strptime(DATE + HHMM, '%Y%m%d%H%M').replace(tzinfo=dt.timezone(dt.timedelta(hours=-7))).astimezone(dt.timezone.utc)
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
            fsame = [x for x in fl if x['name'] == o['name'] and x.get('point') == o.get('point')]
            foff = [x for x in fl if x['name'] == o['name'] and x.get('point') is not None and x.get('point') != o.get('point')]
            for fx, mt in ([(fsame[0], 'same_number')] if fsame else []) + ([(foff[0], 'off_number_converted')] if foff and not fsame else []):
                fp = fx['price']; fpt = fx['point']; be = imp(fp)
                if mk == 'spreads':
                    side = 'home' if o['name'] == g['home_team'] else 'away'
                    ab = e['ha'] if side == 'home' else e['aa']
                    label = f"{o['name']} {fpt:+g}"; ev_side = f"{ab} {fpt:+g}"
                    home_pt = o['point'] if side == 'home' else -o['point']
                    conv, anchor, ksum = convert_spread(fair, o['point'], fpt, is_fav=o['point'] < 0, home_abs=abs(home_pt))
                else:
                    side = o['name'].lower(); label = f"{o['name'].upper()} {fpt:g}"; ev_side = label
                    conv, anchor, ksum = convert_total(fair, o['point'], fpt, side)
                edge = (conv - be) * 100; gap = GAP[e['level']]
                rows.append(dict(level=e['level'], event_id=e['id'], odds_id=g['id'], game=f"{g['away_team']} @ {g['home_team']}", kickoff_pt=ko.astimezone(PT).strftime('%-I:%M %p'), kickoff_utc=g['commence_time'],
                    market='spread' if mk == 'spreads' else 'total', side=side, line=fpt, label=label, ev_side=ev_side, dk_price=o['price'], dk_fair=round(fair, 4),
                    fliff_price=fp, fliff_be=round(be, 4), edge_pts=round(edge, 2), gap_req=gap, worst_fliff=worst(conv - gap / 100), qualifies=edge >= gap,
                    match_type=mt, dk_line=o['point'], fliff_line=fpt, line_diff=round(fpt - o['point'], 2),
                    conv_anchor=anchor, conv_integers=ksum, conv_shift_pts=round((conv - fair) * 100, 2), dk_fair_at_fliff_line=round(conv, 4)))
out = f'/workspace/cfb/leans/{DATE}_{HHMM}.csv'
with open(out, 'w', newline='') as f:
    if rows:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    else: f.write('note\nno games (any level) in window with both DK and Fliff\n')
print('unmatched odds games in window:', unmatched); print('window games (any level):'); [print(' ', x) for x in window_major]
same = [r for r in rows if r['match_type'] == 'same_number']; off = [r for r in rows if r['match_type'] == 'off_number_converted']
print('sides scored: same_number', len(same), '| off_number_converted', len(off), '| DK sides considered', considered)
for lab, rr in (('same_number', same), ('off_number_converted', off)):
    print(f'-- top {lab}:')
    for r in sorted(rr, key=lambda r: -r['edge_pts'])[:12]:
        print(' ', r['game'], f"DK {r['dk_line']:g} {r['dk_price']} -> Fliff {r['fliff_line']:g} {r['fliff_price']} [{r['market']} {r['side']}]", 'shift', r['conv_shift_pts'], 'edge', r['edge_pts'], r['qualifies'], r['level'])
json.dump([r for r in rows if r['qualifies']], open(f'/workspace/cfb/leans/{DATE}_{HHMM}_q.json', 'w'))
# Off-number qualifiers -> separate paper track cfb_offnum in the game-line picks file graded by grade_lines.py
offq = [r for r in off if r['qualifies']]
PK = os.environ.get('CFB_PICKS', '/workspace/cfb-props/lines/picks.csv')
if offq and not REUSE:
    cols = ['event_id', 'market', 'side', 'line', 'price', 'logged_utc', 'track', 'match_type', 'dk_line', 'dk_price', 'dk_fair', 'dk_fair_at_fliff_line', 'conv_anchor', 'conv_shift_pts', 'edge_pts', 'shop_at', 'level', 'game', 'run']
    have = set()
    if os.path.exists(PK):
        have = {(r['event_id'], r['market'], r['side'], r.get('track', '')) for r in csv.DictReader(open(PK))}
    new = not os.path.exists(PK)
    with open(PK, 'a', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if new: w.writeheader()
        for r in offq:
            if (str(r['event_id']), r['market'], r['side'], 'cfb_offnum') in have: continue
            w.writerow(dict(event_id=r['event_id'], market=r['market'], side=r['side'], line=r['fliff_line'], price=r['fliff_price'], logged_utc=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                track='cfb_offnum', match_type=r['match_type'], dk_line=r['dk_line'], dk_price=r['dk_price'], dk_fair=r['dk_fair'], dk_fair_at_fliff_line=r['dk_fair_at_fliff_line'],
                conv_anchor=r['conv_anchor'], conv_shift_pts=r['conv_shift_pts'], edge_pts=r['edge_pts'], shop_at=r['worst_fliff'], level=r['level'], game=r['game'], run=f'{DATE}_{HHMM}'))
    print('appended off-number leans to', PK)
# Room-post section text (the routine posts it; separate from the same-number list)
def fl(r, x): return f'{x:+g}' if r['market'] == 'spread' else f"{r['side'].upper()} {x:g}"
def fa(a): return f'{a:+d}' if a > 0 else f'{a}'
lines = ['OFF-NUMBER (CONVERTED), SEPARATE TRACK (cfb_offnum, paper only)']
if not offq: lines.append(f'None qualified ({len(off)} off-number sides scored; best {max([r["edge_pts"] for r in off], default=float("nan")):+.1f} pts).')
for r in sorted(offq, key=lambda r: -r['edge_pts']):
    lines.append(f"- {r['game']} ({r['kickoff_pt']} PT, {r['level']}): {r['ev_side']} | DK {fl(r, r['dk_line'])} @ {fa(r['dk_price'])} (fair {r['dk_fair']*100:.1f}%) -> Fliff {fl(r, r['fliff_line'])} @ {fa(r['fliff_price'])}"
                 f" | conversion {r['conv_shift_pts']:+.1f} pts ({r['conv_anchor']}; integers {r['conv_integers']}) -> {r['dk_fair_at_fliff_line']*100:.1f}% | edge {r['edge_pts']:+.1f} (need {r['gap_req']:g}) | shop-at {fa(r['worst_fliff'])} or better at Fliff {fl(r, r['fliff_line'])}")
open(f'/workspace/cfb/leans/{DATE}_{HHMM}_offnum_post.txt', 'w').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
