#!/bin/bash
# one-off (2026-10-17): wait until >=3 of today's tracked games are final on ESPN, then run the grader once and log it.
cd "$(dirname "$0")"; LOG=logs/live_final_check_20261017.log
for i in $(seq 1 120); do
  n=$(python3 -c "
import json,urllib.request,pandas as pd
s=pd.read_csv('snapshots.csv',dtype={'date_pt':str,'event_id':str}); ids=set(s[(s.date_pt=='20261017')&(s.state=='pre')].event_id)
d=json.loads(urllib.request.urlopen(urllib.request.Request('https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?dates=20261017&groups=80&limit=300',headers={'User-Agent':'cfb-lines/0.1'}),timeout=30).read())
print(sum(1 for e in d['events'] if e['id'] in ids and e['status']['type']['state']=='post'))" 2>/dev/null || echo 0)
  echo "$(date '+%F %T %Z') finals=$n" >> $LOG
  if [ "${n:-0}" -ge 3 ]; then python3 grade_lines.py 20261017 >> $LOG 2>&1; echo "$(date '+%F %T %Z') graded" >> $LOG; exit 0; fi
  sleep 600
done
