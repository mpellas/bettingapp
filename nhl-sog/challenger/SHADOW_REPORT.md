# Challenger shadow track

Challenger `3386583f18` (features: 29, groups ['shrink'], trees 856, k 16.20, trained through 2026-10-16) vs champion `c3ab760178` vs DraftKings no-vig.
Scored slates: 20261017 onward (see challenger/PREREG_3386583f18.md).

Rows: 1994 OK lines with a challenger prediction (142 games, 22 slates); 1 OK lines had no challenger prediction; 0 predictions were produced late (inputs cut at the prior day, so not leaky); 22 flagged stale inputs. 94 rows marked excluded_pre_noon (puck drop before 12:00 PM PT; same rule as grade_report.py).

| model | log-loss | Brier | log-loss minus market | lean z-CLV | lean hit vs implied |
|---|---|---|---|---|---|
| DK no-vig | 0.6838 | 0.2453 | – | – | – |
| champion c3ab760178 | 0.6885 | 0.2476 | +0.0047 [-0.0002, +0.0099] | +0.0088 [+0.0058, +0.0121] | 0.515 vs 0.508 |
| challenger 3386583f18 | 0.6879 | 0.2473 | +0.0041 [-0.0006, +0.0094] | +0.0096 [+0.0064, +0.0128] | 0.510 vs 0.507 |

**Primary 1 (log-loss, challenger - champion):** -0.0006 [-0.0024, +0.0013] over 142 games. Pass needs the upper bound < 0.
**Primary 2 (lean z-CLV, challenger - champion):** +0.0008 [-0.0010, +0.0026]. Pass needs the lower bound > 0.
Window/decision rules: see the prereg. Fewer than 300 lines or 60 games = INCONCLUSIVE, report only.
