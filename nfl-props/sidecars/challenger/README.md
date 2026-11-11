# NFL challenger candidate: recalibrated champion + pre-game context (sidecar; 2026-10-17)
Pinned code, the locked prereg and the champion aa4d70b859 are untouched. Spec: `nflchal.py` docstring. Pre-game
inputs only: ESPN OPENING spread/total (`fetch_pregame.py` -> `data/open_lines.csv`; ESPN has openers only for
2024-2026), nflverse weekly injury report, Open-Meteo historical-forecast archive (`data/wx_fc.csv`, 2022+).
Walk-forward (`walkforward.py`, `walkforward.out`): train 2024, test 2025 (only seasons with opening lines).
Freeze rule was written in `walkforward.py` before running. **Result: rule NOT met -> NOT frozen, no shadow track.**
  real 2025 ESPN BET lines (2,363, 193 games): challenger - champion log-loss +0.0005 [-0.0058, +0.0069]
  synthetic lines (3,721, 272 games): +0.0023 [-0.0025, +0.0068]; recal-only (intercept + 2024 residual CDF) +0.0024
  [+0.0009, +0.0038] = refitting the scale on one season hurts; context features add ~0 over recal-only.
Note: preds_557e6ab3e4_f9247893_2025 carries SIMULATED lines; real 2025 lines come from the cfe6d96714 file (same mu/s).
