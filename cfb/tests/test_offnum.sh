#!/bin/bash
# Replays the saved 11:02 Oct 24 odds (no API call) and checks same-number rows match the original run.
set -e; cd /workspace/cfb
CFB_DATE=20261024 python3 price_check.py 1102 --reuse oddsapi_20261024_1102.json > /tmp/offnum_test.out
python3 - <<'P'
import pandas as pd
b=pd.read_csv('/workspace/cfb/leans/20261024_1102.csv')
assert set(b.match_type)=={'same_number','off_number_converted'}
s=b[b.match_type=='same_number']; o=b[b.match_type=='off_number_converted']
assert len(s)==64 and len(o)==16, (len(s),len(o))
assert (s.conv_shift_pts==0).all() and (o.line_diff!=0).all()
print('OK same',len(s),'off',len(o),'qualifying off',int(o.qualifies.sum()))
P
