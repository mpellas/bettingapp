# DRAFT — NOT PUBLISHED — NHL player shots-on-goal paper track (pre-registration)

Status: draft for yinzerduck's review. Nothing here is binding until published with a git tag.

## Frozen model
- Model: LightGBM Poisson mean + negative-binomial dispersion, features strictly from prior games (features.py; leakage test in model.py).
- Frozen hash: `c3ab760178` (models/model_c3ab760178.txt, k = 21.86, trained through 2026-10-10, 231,750 skater-games, 1,067 trees).
- No retraining, feature, or threshold changes during the tracked window. Any change = new hash = new track, starting from zero.

## Window
- Starts the first slate after publication; runs through 2026-12-31 or 300 graded leans, whichever comes first. Interim looks are report-only.

## Data / snapshots
- Lines: DraftKings via free ESPN core API (provider 100), "Total Shots on Goal" O/U. Over/under resolved by matching the over-only "Shots on Goal Milestones" (ceil(line))+ price; if unresolvable, listing order (first = over; held for 41/41 verified pairs on 2026-10-11) and flagged `order_fallback`.
- D snapshot = last capture 150–210 min before puck drop. C = last capture 0–40 min before puck drop (after projected lineups). Captured by ops/capture_supervisor.sh loop.
- Lineups/PP units: DailyFaceoff, recorded at D and C; report-only (not a model input in this hash).

## Scored leans (the track)
- On every eligible D line, the lean is the side where model P(side) > DK no-vig P(side). Ties are skipped. One side per line.
- Graded set: each slate, rank leans by edge = model P(side) − no-vig P(side); only the top 20% (rounded up) are graded. The rest are logged, report-only.
- Eligible games are those with puck drop at or after 12:00 PM PT; games starting earlier are excluded from the start. Exclusions: player not mapped to an NHL id, team mismatch (trade), or fewer than 5 prior NHL games.
- Separate report (not scored): the blended-EV bet list, using p_blend = 0.95 × no-vig + 0.05 × model and EV > 0 at the D price. Every leg is flagged `DK-only` until ≥3 books are available.

## Grading (grade.py, next-day NHL box scores)
- Hit/miss on the bet side at the D line; units at D price, 1 unit flat.
- VOID: player did not play; no D capture (capture failure); no C capture (capture failure). Voids are reported, not counted.
- Stop rule: if capture failures exceed 20% of eligible games over any rolling two weeks, the track halts and is reported as a capture failure, not a model result.
- z-CLV D→C: logit(P_C(side)) − logit(P_D(side)), where P_C is the C market's no-vig probability re-expressed at the D line via NB(mu_C, k) when the line moved.

## Pass bar (same structure as NFL)
1. Signal check: mean z-CLV > 0 with game-clustered 95% lower bound > 0.
2. Skill: hit rate ≥ break-even + 2 points, with game-clustered 95% lower bound > average break-even of the picks.
3. Matched control: Δ = lean hit − blanket per-line-side rate (share of all scored DK lines that went over/under at the same line); clustered lower bound on mean(Δ) > 0.
4. Units are report-only (sample too small to be the criterion).
- FAIL if any of 1–3 fails at window end. Fewer than 100 graded leans = INCONCLUSIVE, not pass.

## Known caveat stated up front
- Skill (2) uses each graded lean's own DK break-even + 2 points (no fixed 53.5% bar, since SOG prices range ~+110 to −165). The blended list is expected to be mostly empty with DK-only prices.
