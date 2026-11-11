"""Missing-closing-snapshot watch for nhl-sog (Tester1, process item #2, 2026-10-26). READ-ONLY on nhl-sog.
For every NHL game on the given dates whose puck drop has passed, checks captures/<date>/ for at least one snapshot
taken 0-30 min before puck drop (same window as close.py). A game with none (no files at all, D only, or only
snapshots outside the window) is MISSING_CLOSE. Alerts go to stdout as '!!! CLOSE SNAPSHOT MISSING ...' lines and are
appended (deduped) to <out>/close_alerts.log, which the room-posting routine relays. Exit 2 when any new alert.
Usage: python3 close_watch.py [--root /workspace/nhl-sog] [--out DIR] [--offline] YYYYMMDD [...]
Schedule comes from the ESPN scoreboard (retried); --offline uses only games found on disk."""
import json, glob, os, sys, time, datetime as dt
WIN = (0, 30)
SITE = 'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard'
def get_json(url, params=None, tries=4, base=2.0, _sleep=time.sleep):
    import requests
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers={'User-Agent': 'Mozilla/5.0'}, timeout=(10, 20)); r.raise_for_status(); return r.json()
        except Exception as e:
            last = e
            if i < tries - 1: _sleep(base * 2 ** i)
    raise last
def schedule(date):
    """{eid: (name, start_utc)} for games ESPN lists on date (local scoreboard date)."""
    ev = get_json(SITE, {'dates': date}).get('events', [])
    return {e['id']: (e.get('name'), e['date']) for e in ev}
def on_disk(root, date):
    d = f'{root}/captures/{date}'; S = {}
    for f in glob.glob(f'{d}/archive/*.json') + glob.glob(f'{d}/*_*.json'):
        if f.endswith('_CLOSE.json'): continue
        try: s = json.load(open(f))
        except Exception: continue
        S.setdefault(str(s.get('event') or os.path.basename(f).split('_')[0]), []).append(s)
    return S
def check(root, dates, sched=None, now=None):
    now = now or dt.datetime.now(dt.timezone.utc); out = []; done = set()
    for date in dates:
        # capture.py files a game under its UTC start date, ESPN's scoreboard under the US date: look at date-1..date+1
        d0 = dt.datetime.strptime(date, '%Y%m%d'); S = {}
        for k in (-1, 0, 1):
            for eid, ss in on_disk(root, (d0 + dt.timedelta(days=k)).strftime('%Y%m%d')).items(): S.setdefault(eid, []).extend(ss)
        if sched: games = dict(sched(date))
        else: games = {eid: (ss[0].get('name'), ss[0].get('start_utc')) for eid, ss in on_disk(root, date).items()}
        for eid, (name, start) in sorted(games.items()):
            if not start or eid in done: continue
            done.add(eid)
            st = dt.datetime.fromisoformat(start.replace('Z', '+00:00'))
            if st > now: continue  # not started yet: the capture loop may still land a C snapshot
            ss = S.get(eid, [])
            inw = [s for s in ss if WIN[0] <= (s.get('minutes_to_start') if s.get('minutes_to_start') is not None else -1) <= WIN[1]]
            status = 'OK' if inw else ('NO_FILES' if not ss else 'NO_IN_WINDOW_SNAPSHOT')
            out.append(dict(date=date, event=eid, name=name, start_utc=start, n_snapshots=len(ss), n_in_window=len(inw), status=status,
                            nearest_min=min((s.get('minutes_to_start') for s in ss if s.get('minutes_to_start') is not None), default=None, key=abs)))
    return out
def alert(rows, outdir):
    os.makedirs(outdir, exist_ok=True); p = f'{outdir}/close_alerts.log'
    seen = set(l.split('\t')[1] for l in open(p)) if os.path.exists(p) else set(); new = []
    for r in rows:
        if r['status'] == 'OK' or r['event'] in seen: continue
        msg = (f"!!! CLOSE SNAPSHOT MISSING {r['date']} {r['name']} (event {r['event']}, puck drop {r['start_utc']}): {r['status']}, "
               f"{r['n_snapshots']} snapshots, nearest {r['nearest_min']} min out. Sides on this game get no CLV; do not backfill.")
        new.append(msg); open(p, 'a').write(f"{dt.datetime.now(dt.timezone.utc).isoformat()}\t{r['event']}\t{msg}\n")
    return new
if __name__ == '__main__':
    a = sys.argv[1:]; root = '/workspace/nhl-sog'; outdir = os.path.dirname(os.path.abspath(__file__)); off = False
    while a and a[0].startswith('--'):
        k = a.pop(0)
        if k == '--root': root = a.pop(0)
        elif k == '--out': outdir = a.pop(0)
        elif k == '--offline': off = True
    dates = a or [dt.date.today().strftime('%Y%m%d')]
    rows = check(root, dates, None if off else schedule)
    for r in rows: print(r['date'], r['event'], r['name'], r['status'], f"snaps={r['n_snapshots']} in_window={r['n_in_window']}")
    new = alert(rows, outdir); [print(m) for m in new]
    print(f"close watch: {len(rows)} started games, {sum(r['status'] != 'OK' for r in rows)} missing close, {len(new)} new alerts")
    sys.exit(2 if new else 0)
