import pandas as pd
A = pd.read_csv('analysis/oct18/all_sides_stage1.csv')
mv = {('Omarion Hampton','reception_yds'): ('Under', 'DK line 6.5 (Sat 12:09 AM PT) to 5.5 now, down 1 yd: moved toward the under, but leaves 1 yd less cushion. ESPN snapshots carry no DK prices.'),
      ('Ray Davis','rush_yds'): ('Over', 'DK line 6.5 (Sat 12:09 AM PT) to 9.5 now, up 3 yds: moved toward the over; PP 7.5 now sits 2 yds under DK.'),
      ('Darren Waller','reception_yds'): ('Under', 'DK line 28.5 (Sat 12:09 AM PT) to 24.5 now, down 4 yds: moved toward the under; PP 26.5 sits 2 yds above DK.'),
      ('Tyler Higbee','reception_yds'): ('Under', 'DK line 34.5 (Sat 12:09 AM PT) to 32.5 now, down 2 yds: moved toward the under; PP 34.5 sits 2 yds above DK.'),
      ('Dak Prescott','rush_yds'): ('Under', 'DK line 10.5 Saturday and 10.5 now: no move.')}
A['movement'] = ''
for (pl, mk), (sd, txt) in mv.items():
    m = (A.player == pl) & (A.market == mk) & (A.status == 'PASS'); A.loc[m, 'movement'] = txt
A.loc[A.movement == '', 'movement'] = 'not computed (side did not pass)'
ev = pd.concat([pd.read_csv('analysis/analysis_2026_wk6_live_20261018T0741_evidence.csv').assign(src='DK'),
                pd.read_csv('analysis/oct18/pp_legs_for_evidence_evidence.csv').assign(src='PP')])
ev['market'] = ev.market.replace({'rec_yds': 'reception_yds'})
A['evidence'] = ''
for r in ev.dropna(subset=['evidence_summary']).itertuples():
    m = (A.player == r.player) & (A.market == r.market) & (A.line == r.line) & (A.side == r.side) & (A.source.str.startswith('Prize') == (r.src == 'PP'))
    A.loc[m, 'evidence'] = r.evidence_summary
A.loc[A.evidence == '', 'evidence'] = 'not run (not a candidate)'
A['shop_at'] = ''
A.loc[(A.player == 'Omarion Hampton') & (A.status == 'PASS') & (A.book == 'draftkings'), 'shop_at'] = 'DK -110 or better; Fliff -110 or better (Fliff not listing 5.5 at pull time)'
for pl, txt in {'Ray Davis': 'PP standard 7.5 only; at DK/Fliff 9.5 Over, even money (-100) or better (now DK -116, Fliff -115, so no)',
                'Darren Waller': 'PP standard 26.5 only; at DK 24.5 Under, -100 or better (now -112, so no)',
                'Tyler Higbee': 'PP standard 34.5 only; DK/Fliff 32.5 has under 3 books at that line, no shop-at price',
                'Dak Prescott': 'PP standard 10.5 only; DK 10.5 has under 3 books at that line, no shop-at price',
                'Omarion Hampton': 'PP standard 6.5'}.items():
    A.loc[(A.player == pl) & (A.status == 'PASS') & (A.book == 'prizepicks'), 'shop_at'] = txt
A['rank_metric'] = A.ev_pct
A = A.sort_values(['status', 'ev_pct'], ascending=[True, False], key=lambda s: s.map({'PASS': 0, 'skip': 1, 'fail': 2}) if s.name == 'status' else s)
cols = ['status', 'source', 'game', 'kickoff_pt', 'player', 'market', 'line', 'side', 'book', 'price', 'fair_prob', 'fair_price', 'ev_pct', 'n_books',
        'pp_types', 'injury', 'reason', 'shop_at', 'movement', 'recheck', 'evidence', 'alt_lines', 'event_id']
with pd.ExcelWriter('analysis/oct18/nfl_wk6_oct18_priceshop.xlsx') as w:
    A[A.status == 'PASS'][cols].to_excel(w, sheet_name='Picks', index=False)
    A[cols].to_excel(w, sheet_name='All sides considered', index=False)
    pd.DataFrame({'note': ['Raw Odds API pull saved for CLV grading: /workspace/props-finder/raw/20261018T1440 (11 games, 33 credits, balance 184 after).',
        'DK/Fliff rule: keep if DK or Fliff beats the Pinnacle-weighted (x3) median no-vig fair price at the exact same line by >= 2% EV, with >= 3 books.',
        'PrizePicks rule: leg win probability at the PP line (books shifted to the PP number, Pinnacle x3) must clear the entry type break-even by >= 1 point.',
        'ev_pct for PP rows = edge over the 6-pick flex break-even (54.2%), not the same scale as DK EV.',
        'Injury: ESPN game summaries at ~7:42 AM PT; any Questionable/Doubtful/Out/IR player skipped.',
        'Movement and evidence are context only, never a gate, and never fed to the frozen paper test. Separate from the prereg paper track.']}).to_excel(w, sheet_name='Notes', index=False)
A[cols].to_csv('analysis/oct18/nfl_wk6_oct18_all_sides.csv', index=False)
print(A[A.status == 'PASS'][['player', 'ev_pct']].to_string()); print(len(A))
