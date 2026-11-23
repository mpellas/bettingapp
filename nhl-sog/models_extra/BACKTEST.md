# Extra NHL paper models — backtest (22 Nov 2026)

Train 2021–2025, 2026 held out. Units only at real captured DraftKings prices.
Price band enforced only at the −150 end (−155 or worse is outside). All three
models stay in shadow (`models_extra/shadow/`), off the real SOG card, until
~100 graded in-band sides (and a review). No prices were invented or backfilled.

## Player points O/U

Uses skater game logs from the NHL stats API (goals/assists/points, TOI) merged
with PP TOI / attempts from existing `data/s20xx.pkl`. LightGBM Poisson + NB
with as-of rolling points/goals/assists/shots/TOI/PP, career means, rest, B2B,
home, defense flag, opponent points allowed and team points for (prior 20).
Leakage test passed.

Walk-forward (outcome only, no DK prices): MAE 0.52–0.53, mean predicted
matches mean actual (~0.45–0.47).

2026 OOS: 13,166 skater-games, MAE 0.533, mean μ 0.462 vs actual 0.479.

Priced backtest (DK D prices from extra-market captures Nov 15–22; 912 of ~1,005
unique O/U lines joined; pick the side with model edge > 0 at the D price):

- All: 141-189 (42.7%), −56.38u, ROI −17.1%, vs 52.0% break-even, n=330
- In band (price ≥ −150): 103-140 (42.4%), −26.58u, ROI −10.9%, vs 47.0% BE, n=243
- Outside band: 38-49, −29.80u, ROI −34.3%, n=87

The model shrinks toward the league mean and systematically fades market
favorites (stars on 0.5). Early priced results are clearly negative. Leave in
shadow only; do not promote. Already past 100 in-band sides.

## Goalie saves O/U

Uses NHL goalie game logs (saves, shots against, TOI, prior starter rate) plus
opponent shots-for / team shots-against from team games. LightGBM Poisson + NB.
Same-game `gamesStarted` is not a feature (that would leak). Leakage test passed.

Walk-forward: MAE 5.4–5.8 saves, mean μ tracks actual (~24–26).

2026 OOS: 753 goalie-games, MAE 5.41, mean μ 22.27 vs actual 23.48.

Priced backtest (DK D prices, 108 of 115 unique O/U lines joined):

- In band (all 64 priced picks were in band): 39-25 (60.9%), +8.22u, ROI +12.8%, vs 53.7% BE

Small sample (64 < 100). This is the only model with a positive priced start.
Worth tracking in shadow; stay off the real card until ~100 graded in-band sides.

## Game puckline

Uses team GF/GA and shot rates (challenger team logs + a 2026 refresh). Two
Poisson LightGBM models (home GF, away GF) → P(cover −1.5) under independent
Poissons. Leakage test passed. Train 6,469 games; 2026 OOS 372 games.

No DraftKings puckline prices existed before the 22 Nov 2026 capture went live
(first live snapshot: CHI @ VAN, C window, 4:32 PM PT). Units/ROI are therefore
not available yet. Outcome-only:

- Train cover rates (2021–2025): home −1.5 32.8%, home +1.5 72.7%, away −1.5 27.3%
- Walk-forward predicted P(home −1.5) 0.30–0.31 vs actual 0.30–0.35; margin MAE ~2.11
- 2026 OOS: actual home −1.5 30.1% vs predicted 29.0%; margin MAE 2.10

A raw cover-rate rule without prices is not a betting result — +1.5 covers ~70%
of the time but is heavily juiced (tonight VAN +1.5 was −265). Track in shadow
as D/close prices accrue from tonight forward; judge on units once a priced
sample exists.
