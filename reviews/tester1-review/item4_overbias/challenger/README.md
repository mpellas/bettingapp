# shadow_shrink50 — paper-only challenger (Tester1, Oct 31 2026)
No live change, nothing scheduled, no API credits. /workspace/nhl-sog was only read (cp -a into `src/`).

## Formula
p_ch_over = sigmoid(0.5*logit(p_model_over) + 0.5*logit(nv_over))   (w fixed at 0.50; item4 fit gave 0.52)
p_blend_ch = 0.95*nv_over + 0.05*p_ch_over;  ev_ch = p_blend_ch*decimal(DK) - 1. Unders are complements.
All gates/status logic = unmodified `src/build_sheet.py` `build_rows` (current rules: thin edge, 5-pt floor on model-minus-no-vig,
12-pt band, slot/milestone/lineup/recent form, top-5 cap). Only p_model_over, p_blend_over, ev_over/ev_under are swapped.
`shrink` and `evidence` modules are disabled (display-only, not used for status).

## Rebuild
    cp -a /workspace/nhl-sog/{build_sheet.py,recent_form.py,picks,graded,captures} src/ ; mkdir -p src/data; cp -a /workspace/nhl-sog/data/catchup_box src/data/
    python3 shadow_shrink50.py slate src/picks/20261029_D_1233.csv src/picks/20261029_D_1233_GATE.csv --out slate_20261029_1233.csv
    python3 shadow_shrink50.py --backtest --through 20261030     # -> backtest_sides.csv, backtest_summary.csv
Backtest: every *_GATE.csv with a matching picks file; keep passes captured >=150 min before puck drop (start_utc from captures/*.json);
latest such pass per (nhl_id, gameId); date = PT game date <= Oct 30. Results: graded/*.csv `actual`, then data/catchup_box box scores.
Units: 1u flat; DK = posted DK price; shop-at = each list's own fliff_shop_at (break-even price at that blend, so a ceiling, not a realistic fill).

## Results (through Oct 30; 41 passes, 1206 player-games)
| list | sides | W-L | u @DK | u @shop-at |
|---|---|---|---|---|
| live | 85 | 50-35 | +3.84 | +9.92 |
| challenger | 30 | 19-11 | +4.64 | +7.05 |
| both | 16 | 11-5 | +3.47 | +4.88 |
| live only | 69 | 39-30 | +0.37 | +5.15 |
| challenger only | 14 | 8-6 | +1.17 | +2.17 |

## Caveats
- 3 passes fail to build (`20261016_D`, `20261017_D`, `20261025_D`: picks/GATE keys don't line up, KeyError) and are skipped, same Oct 17 mismatch as before.
- Both lists use TODAY's rules on every date (not dated rules), so "live" here is not the historical list.
- The 5-pt floor is applied to the challenger's own (shrunk) edge, so it effectively needs ~10 pts raw edge.
- Slate test: no Oct 31 picks yet; Oct 29 12:33 live list reproduces the posted list (Goncalves U, Weegar O, Guenther U, Ehlers O, Aho O); challenger keeps only Ehlers O1.5.
