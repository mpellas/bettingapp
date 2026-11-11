import sys, os, csv, json, datetime as dt
sys.path.insert(0, '/workspace/nhl-sog'); import fliff_prices as fp, fliff_repull as fr
os.chdir('/workspace/nhl-sog')
now = dt.datetime.now(fp.PT); date = now.strftime('%Y%m%d'); hhmm = now.strftime('%H%M'); log = f'fliff_credits_{date}.csv'; CAP = 10
SIDES = [('Wyatt Johnston', 'Dallas Stars at Washington Capitals', 'UNDER', 2.5, 105),
         ('Oliver Bonk', 'Minnesota Wild at Philadelphia Flyers', 'UNDER', 1.5, -134)]
events, _ = fp.get(f'{fp.BASE}/events?apiKey={fp.key()}')
out = []
for player, game, side, line, shop in SIDES:
    e = fp.match_event(game, events); ev = e['id'] if e else None
    puck = dt.datetime.fromisoformat(e['commence_time'].replace('Z', '+00:00')).astimezone(fp.PT) if e else None
    tot, last = fp.spent(log); exp = last or 1
    row = dict(run_time_pt=now.isoformat(timespec='seconds'), date=date, player=player, game=game, side=side, line=line, gameId=None,
               odds_event=ev, puck_drop_pt=puck.isoformat() if puck else None, mins_to_drop=round((puck-now).total_seconds()/60) if puck else None,
               first_status='off-sheet (T2R1239 rerun)', source='manual_T2R1239', fliff_shop_at=shop, dry_run=False)
    if ev is None: row.update(repull_status='game not found in Odds API events', credits_after=tot); out.append(row); print(player, 'no event'); continue
    if tot + exp > CAP: row.update(repull_status=f'skipped: cap reached ({tot}/{CAP})', credits_after=tot); out.append(row); print(player, 'cap'); continue
    d, h = fp.get(f'{fp.BASE}/events/{ev}/odds?apiKey={fp.key()}&markets=player_shots_on_goal&bookmakers=fliff,draftkings&oddsFormat=american')
    t = dt.datetime.now(fp.PT)
    json.dump(d, open(f'captures/fliff_{date}_{hhmm}_{ev}.json', 'w'))
    with open(log, 'a', newline='') as f: csv.writer(f).writerow([t.isoformat(timespec='seconds'), ev, h.get('x-requests-last', ''), h.get('x-requests-remaining', '')])
    book = {}
    for bk in d.get('bookmakers', []):
        for m in bk.get('markets', []):
            if m.get('key') != 'player_shots_on_goal': continue
            for o in m.get('outcomes', []):
                book.setdefault(bk['key'], {}).setdefault(fp.norm(o.get('description', '')), []).append((o['name'].upper(), float(o['point']), int(o['price'])))
    def find(b):
        o = [x for x in book.get(b, {}).get(fp.norm(player), []) if x[0] == side]
        return ([x for x in o if x[1] == line] or o or [None])[0]
    f_, k = find('fliff'), find('draftkings'); beats = None
    if f_ is None: st = 'still not offered'
    elif f_[1] != line: st = 'different line'
    else: st = 'offered'; beats = fp.dec(f_[2]) >= fp.dec(shop)
    row.update(repull_status=st, fliff_line=f_[1] if f_ else None, fliff_price=f_[2] if f_ else None, beats_shop_at=beats,
               dk_line_now=k[1] if k else None, dk_price_now=k[2] if k else None, credits_after=fp.spent(log)[0])
    out.append(row); print(row)
new = not os.path.exists(fr.LOG)
with open(fr.LOG, 'a', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fr.COLS)
    if new: w.writeheader()
    w.writerows(out)
print('credits', fp.spent(log)[0])
