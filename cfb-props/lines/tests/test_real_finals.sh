#!/bin/bash
# grade_lines.py on REAL ESPN finals (Oct 16 2026: TULN 31-17 MEM, PUR 26-38 WASH, CCU 32-35 APP) with hand-set lines.
# Expected (hand-computed): TULN +6.5 home covers, total 48 < 50.5 under; PUR +9.5 away covers (-12+9.5), 64 > 55.5 over;
# CCU +3 push (-3+3), 67 = 67 push.
set -e; T=$(mktemp -d); cp "$(dirname "$0")/../grade_lines.py" "$T/"; cd "$T"
python3 - <<'PY'
import pandas as pd
cols = open('/workspace/cfb-props/lines/snapshots.csv').readline().strip().split(',')
rows = []
for ev, away, home, L, T in [('401862801','MEM','TULN',6.5,50.5),('401858493','WASH','PUR',9.5,55.5),('401869844','APP','CCU',3.0,67.0)]:
    for cap, mtk, Lx in [('2026-10-16T20:00:00+00:00', 200, L - 1), ('2026-10-16T23:20:00+00:00', 10, L)]:
        r = {c: None for c in cols}; r.update(captured_utc=cap, minutes_to_kickoff=mtk, event_id=ev, date_pt='20261016', kickoff_utc='2026-10-16T23:30Z',
            state='pre', away=away, home=home, provider='Draft Kings', spread_home_line=Lx, spread_home_price=-110, spread_away_line=-Lx,
            spread_away_price=-110, total=T, over_price=-110, under_price=-110, ml_home=150, ml_away=-170, open_spread_home_line=L - 1, open_total=T)
        rows.append(r)
pd.DataFrame(rows)[cols].to_csv('snapshots.csv', index=False)
PY
CFB_SCOREBOARD_FILE="$OLDPWD/$(dirname "$0")/scoreboard_20261016_finals.json" python3 grade_lines.py 20261016 >/dev/null
python3 -c "
import pandas as pd; g=pd.read_csv('graded_20261016.csv').set_index('game')
exp={'MEM @ TULN':('home','under'),'WASH @ PUR':('away','over'),'APP @ CCU':('push','push')}
for k,(c,t) in exp.items(): assert (g.loc[k,'home_cover_close'],g.loc[k,'total_result_close'])==(c,t), (k,g.loc[k].to_dict())
assert (g.state=='post').all(); print('PASS: real ESPN finals graded correctly (3 games)')"
