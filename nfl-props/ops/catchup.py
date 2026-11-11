#!/usr/bin/env python3
"""NFL outage catch-up (Enhancement 3). Read-only: 0 Odds API credits, never prices, never touches prereg/track.py.
Per event_id, using the repo's decision-snapshot definition (track.py: D = last capture >=3h before kickoff):
an event is COVERED if capture_log.jsonl has a row for that event_id captured at or before kickoff-3h.
Otherwise, once strictly inside 3h of kickoff (minutes_to_kickoff < 180; exactly 180 = PENDING), it is MISSED
and logged to logs/missed_games.csv (no late pricing). Results are graded later via nflverse as usual.
Usage: python3 ops/catchup.py [--dry-run]"""
import json, os, sys, csv, datetime as dt, urllib.request
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECISION_MIN=180
def ts(r):
    t=dt.datetime.fromisoformat(r['captured_at_utc'] if 'captured_at_utc' in r else r['captured_at_pt'])
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
last=None; caps={}
for l in open(os.path.join(ROOT,'data/snapshots/capture_log.jsonl')):
    try: r=json.loads(l); t=ts(r)
    except Exception: continue
    last=max(last,t) if last else t
    if r.get('event_id') is not None: caps.setdefault(str(r['event_id']),[]).append(t)
now=dt.datetime.now(dt.timezone.utc); print('last snapshot',last,'gap h',round((now-last).total_seconds()/3600,1))
evs={}; d=last.date()
while d<=now.date()+dt.timedelta(days=1):
    for e in json.load(urllib.request.urlopen('https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates='+d.strftime('%Y%m%d'),timeout=30)).get('events',[]): evs[e['id']]=e
    d+=dt.timedelta(days=1)
rows=[]
for e in evs.values():
    ko=dt.datetime.fromisoformat(e['date'].replace('Z','+00:00'))
    cut=ko-dt.timedelta(minutes=DECISION_MIN)
    if any(t<=cut for t in caps.get(str(e['id']),[])): continue  # has decision snapshot
    mins=(ko-now).total_seconds()/60
    if mins>=DECISION_MIN: print([e['id'],e['shortName'],ko.isoformat(),'PENDING',round(mins)]); continue
    rows.append([e['id'],e['shortName'],ko.isoformat(),e['status']['type']['name'],'MISSED','no decision snapshot for this event_id (>=3h before kickoff); not priced late',now.isoformat(timespec='seconds')])
for r in rows: print(r[:5])
out=os.path.join(ROOT,'logs/missed_games.csv')
old={r[0] for r in csv.reader(open(out))} if os.path.exists(out) else set()
rows=[r for r in rows if r[0] not in old]
if rows and '--dry-run' not in sys.argv:
    with open(out,'a',newline='') as f:
        w=csv.writer(f)
        if not old: w.writerow(['event_id','game','kickoff_utc','status','flag','note','logged_at'])
        w.writerows(rows)
print(len(rows),'new missed games')
