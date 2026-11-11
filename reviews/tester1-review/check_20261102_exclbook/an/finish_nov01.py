# Nov 1 2026 wk8 price-shop finish (0 credits; reads all_sides_stage1.csv + evidence)
import pandas as pd
A = pd.read_csv('analysis/nov01/all_sides_stage1.csv')
mv = {('Jared Goff','pass_yds'): 'DK line 267.5 to 259.5 now, down 8 yds: market already moved toward the under; Fliff sits lower at 255.5.',
      ('Aaron Jones','rush_yds'): 'DK 29.5 vs Fliff 28.5; open-to-now move not captured in this pull.',
      ('Reggie Virgil','reception_yds'): 'DK line 11.5 to 8.5 now, down 3 yds: moved toward the under; PP 11.5 sits 3 yds above DK.',
      ('Joshua Palmer','reception_yds'): 'DK line 11.5 to 8.5 now, down 3 yds: moved against the over; PP 8.5 sits 1 yd below DK 9.5.',
      ('Ty Johnson','rush_yds'): 'No open-to-now move captured; PP 1.5 matches DK 1.5 (FanDuel/Pinnacle 3.5).'}
A['movement'] = ''
for (pl, mk), txt in mv.items():
    A.loc[(A.player == pl) & (A.market == mk) & (A.status == 'PASS'), 'movement'] = txt
A.loc[A.movement == '', 'movement'] = 'not computed (side did not pass)'
ev = pd.concat([pd.read_csv('analysis/analysis_2026_wk8_live_20261101T0909_evidence.csv').assign(src='DK'),
                pd.read_csv('analysis/nov01/pp_legs_for_evidence_evidence.csv').assign(src='PP')])
ev['market'] = ev.market.replace({'rec_yds': 'reception_yds'})
A['evidence'] = ''
for r in ev.dropna(subset=['evidence_summary']).itertuples():
    m = (A.player == r.player) & (A.market == r.market) & (A.line == r.line) & (A.side == r.side) & (A.source.str.startswith('Prize') == (r.src == 'PP'))
    A.loc[m, 'evidence'] = r.evidence_summary
A.loc[A.evidence == '', 'evidence'] = 'not run (not a candidate)'
A['shop_at'] = ''
for pl, txt in {'Jared Goff': 'DK 259.5 Under, shop at -119 or better (DK now -113). Fliff only 255.5 (-120), no.',
                'Aaron Jones': 'DK 29.5 Under, shop at -115 or better (DK now -114). Fliff 28.5 Under -125, no.'}.items():
    A.loc[(A.player == pl) & (A.status == 'PASS'), 'shop_at'] = txt
for pl, txt in {}.items():
    A.loc[(A.player == pl) & (A.status == 'PASS') & (A.book == 'prizepicks'), 'shop_at'] = txt
A = A.sort_values(['status', 'ev_pct'], ascending=[True, False], key=lambda s: s.map({'PASS': 0, 'skip': 1, 'fail': 2}) if s.name == 'status' else s)
cols = ['status', 'source', 'game', 'kickoff_pt', 'player', 'market', 'line', 'side', 'book', 'price', 'fair_prob', 'fair_price', 'ev_pct', 'n_books',
        'pp_types', 'injury', 'reason', 'shop_at', 'movement', 'recheck', 'evidence', 'alt_lines', 'event_id']
with pd.ExcelWriter('analysis/nov01/nfl_wk8_nov01_priceshop.xlsx') as w:
    A[A.status == 'PASS'][cols].to_excel(w, sheet_name='Picks', index=False)
    A[cols].to_excel(w, sheet_name='All sides considered', index=False)
    pd.DataFrame({'note': ['Raw Odds API pull saved for CLV grading: /workspace/props-finder/raw/20261101T1709 (8 games at 10:00 AM PT, 24 credits, balance 476 after).',
        'DK/Fliff rule: keep if DK or Fliff beats the Pinnacle-weighted (x3) median no-vig fair price at the exact same line by >= 2% EV, with >= 3 books.',
        'PrizePicks rule: leg win probability at the PP line (books shifted to the PP number, Pinnacle x3) must clear the entry type break-even by >= 1 point.',
        'ev_pct for PP rows = edge over the 6-pick flex break-even (54.2%), not the same scale as DK EV.',
        'Injury: ESPN game summaries + inactives snapshot nfl-props/data/snapshots_inactives/2026-11-01 (8:46 AM PT); Out/Questionable skipped (Justin Jefferson Out).',
        'Movement and evidence are context only, never a gate, and never fed to the frozen paper test. Separate from the prereg paper track.']}).to_excel(w, sheet_name='Notes', index=False)
A[cols].to_csv('analysis/nov01/nfl_wk8_nov01_all_sides.csv', index=False)
print(A[A.status == 'PASS'][['player', 'ev_pct', 'recheck']].to_string()); print(len(A))
