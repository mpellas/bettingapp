# Oct 25 2026 wk7 price-shop finish (0 credits; reads all_sides_stage1.csv + evidence)
import pandas as pd
A = pd.read_csv('analysis/oct25/all_sides_stage1.csv')
mv = {('Darnell Mooney','reception_yds'): 'DK line 15.5 (open) to 17.5 now, up 2 yds: moved toward the over, against this under; PP 19.5 still sits 2 yds above DK.',
      ('J.J. McCarthy','rush_yds'): 'DK line 25.5 (open) to 23.5 now, down 2 yds: moved toward the under; PP 24.5 sits 1 yd above DK.'}
A['movement'] = ''
for (pl, mk), txt in mv.items():
    A.loc[(A.player == pl) & (A.market == mk) & (A.status == 'PASS'), 'movement'] = txt
A.loc[A.movement == '', 'movement'] = 'not computed (side did not pass)'
ev = pd.concat([pd.read_csv('analysis/analysis_2026_wk7_live_20261025T0732_evidence.csv').assign(src='DK'),
                pd.read_csv('analysis/oct25/pp_legs_for_evidence_evidence.csv').assign(src='PP')])
ev['market'] = ev.market.replace({'rec_yds': 'reception_yds'})
A['evidence'] = ''
for r in ev.dropna(subset=['evidence_summary']).itertuples():
    m = (A.player == r.player) & (A.market == r.market) & (A.line == r.line) & (A.side == r.side) & (A.source.str.startswith('Prize') == (r.src == 'PP'))
    A.loc[m, 'evidence'] = r.evidence_summary
A.loc[A.evidence == '', 'evidence'] = 'not run (not a candidate)'
A['shop_at'] = ''
for pl, txt in {'Darnell Mooney': 'PP standard 19.5 only; at DK/Fliff 17.5 Under, +104 or better (now DK -113, Fliff -120, so no)',
                'J.J. McCarthy': 'PP standard 24.5 only; at DK/Fliff 23.5 Under, +104 or better (now DK -111, Fliff -125, so no)'}.items():
    A.loc[(A.player == pl) & (A.status == 'PASS') & (A.book == 'prizepicks'), 'shop_at'] = txt
A = A.sort_values(['status', 'ev_pct'], ascending=[True, False], key=lambda s: s.map({'PASS': 0, 'skip': 1, 'fail': 2}) if s.name == 'status' else s)
cols = ['status', 'source', 'game', 'kickoff_pt', 'player', 'market', 'line', 'side', 'book', 'price', 'fair_prob', 'fair_price', 'ev_pct', 'n_books',
        'pp_types', 'injury', 'reason', 'shop_at', 'movement', 'recheck', 'evidence', 'alt_lines', 'event_id']
with pd.ExcelWriter('analysis/oct25/nfl_wk7_oct25_priceshop.xlsx') as w:
    A[A.status == 'PASS'][cols].to_excel(w, sheet_name='Picks', index=False)
    A[cols].to_excel(w, sheet_name='All sides considered', index=False)
    pd.DataFrame({'note': ['Raw Odds API pull saved for CLV grading: /workspace/props-finder/raw/20261025T1432 (11 games, 33 credits, balance 113 after).',
        'DK/Fliff rule: keep if DK or Fliff beats the Pinnacle-weighted (x3) median no-vig fair price at the exact same line by >= 2% EV, with >= 3 books.',
        'PrizePicks rule: leg win probability at the PP line (books shifted to the PP number, Pinnacle x3) must clear the entry type break-even by >= 1 point.',
        'ev_pct for PP rows = edge over the 6-pick flex break-even (54.2%), not the same scale as DK EV.',
        'Injury: ESPN game summaries at ~7:33 AM PT; any Questionable/Doubtful/Out/IR player skipped (Puka Nacua O83.5 would have qualified but is Questionable).',
        'Movement and evidence are context only, never a gate, and never fed to the frozen paper test. Separate from the prereg paper track.']}).to_excel(w, sheet_name='Notes', index=False)
A[cols].to_csv('analysis/oct25/nfl_wk7_oct25_all_sides.csv', index=False)
print(A[A.status == 'PASS'][['player', 'ev_pct', 'recheck']].to_string()); print(len(A))
