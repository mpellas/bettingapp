# Challenger shadow track

Challenger `3386583f18` (features: 29, groups ['shrink'], trees 856, k 16.20, trained through 2026-10-16) vs champion `c3ab760178` vs DraftKings no-vig.
Scored slates: 20261017 onward (see challenger/PREREG_3386583f18.md).

Rows: 1428 OK lines with a challenger prediction (89 games, 15 slates); 1 OK lines had no challenger prediction; 0 predictions were produced late (inputs cut at the prior day, so not leaky); 0 flagged stale inputs. 94 rows marked excluded_pre_noon (puck drop before 12:00 PM PT; same rule as grade_report.py).

| model | log-loss | Brier | log-loss minus market | lean z-CLV | lean hit vs implied |
|---|---|---|---|---|---|
| DK no-vig | 0.6826 | 0.2448 | – | – | – |
| champion c3ab760178 | 0.6866 | 0.2467 | +0.0040 [-0.0022, +0.0101] | +0.0091 [+0.0053, +0.0128] | 0.521 vs 0.509 |
| challenger 3386583f18 | 0.6858 | 0.2463 | +0.0032 [-0.0029, +0.0091] | +0.0099 [+0.0060, +0.0135] | 0.515 vs 0.507 |

**Primary 1 (log-loss, challenger - champion):** -0.0008 [-0.0029, +0.0012] over 89 games. Pass needs the upper bound < 0.
**Primary 2 (lean z-CLV, challenger - champion):** +0.0008 [-0.0009, +0.0027]. Pass needs the lower bound > 0.
Window/decision rules: see the prereg. Fewer than 300 lines or 60 games = INCONCLUSIVE, report only.
