"""Walk-forward backtest of one config + report.

    python -m nflprops.run_backtest                                # default config, validation+selection seasons
    python -m nflprops.run_backtest --champion --seasons 2019-2024  # current champion from experiments/champion.json
    python -m nflprops.run_backtest --config configs/default.yaml --lines-csv data/lines/my_lines.csv --seasons 2025
Betting params: taken from the config (or champion) unless --tune (validation-season tuning, see tuning.py).
Probabilities: rolling per-market stacker (config betting.prob_method), fit on strictly earlier weeks of the run.
The holdout season is refused here — it is scored once via `python -m nflprops.holdout`.
"""
from __future__ import annotations

import argparse
import json
import logging

from . import EXPERIMENTS, REPORTS, ROOT
from .backtest import walk_forward
from .config import deep_update, load_config
from .features import load_features
from .metrics import evaluate
from .report import write_report
from .tuning import tune_betting


def parse_seasons(s: str) -> list[int]:
    out = []
    for part in s.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return out


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=None)
    ap.add_argument("--champion", action="store_true")
    ap.add_argument("--seasons", default=None, help="e.g. 2019-2024 (default: validation+selection seasons)")
    ap.add_argument("--lines-csv", default=None, help="use real lines from this CSV instead of simulated")
    ap.add_argument("--tune", action="store_true", help="tune betting params on the validation seasons first")
    ap.add_argument("--name", default=None)
    a = ap.parse_args()
    cfg = load_config(a.config)
    bet = dict(cfg["betting"])
    if a.champion:
        st = json.loads((EXPERIMENTS / "champion.json").read_text())
        cfg = st["champion"]
        bet.update({k: st["betting"][k] for k in ("edge_threshold", "kelly_fraction")})
    seasons = parse_seasons(a.seasons) if a.seasons else cfg["periods"]["validation_seasons"] + cfg["periods"]["selection_seasons"]
    if cfg["periods"]["holdout_season"] in seasons:
        raise SystemExit(f"holdout season {cfg['periods']['holdout_season']} is frozen: use python -m nflprops.holdout")
    feats = load_features(cfg["data"]["first_season"], cfg["data"]["last_season"])
    if a.tune:
        t = tune_betting(walk_forward(cfg, cfg["periods"]["validation_seasons"], feats), cfg)
        bet.update({k: t[k] for k in ("edge_threshold", "kelly_fraction")})
    if a.lines_csv:
        cfg = deep_update(cfg, {"lines": {"source": "csv", "csv_path": str((ROOT / a.lines_csv).resolve())
                                          if not a.lines_csv.startswith("/") else a.lines_csv}})
    preds = walk_forward(cfg, seasons, feats)
    ev = evaluate(preds, bet)
    sim = bool(preds["line_simulated"].iloc[0])
    name = a.name or f"backtest_{'champion' if a.champion else 'config'}_{seasons[0]}_{seasons[-1]}{'_sim' if sim else '_real'}"
    path = write_report(ev, cfg, bet, REPORTS / name, f"Walk-forward backtest {seasons[0]}–{seasons[-1]}", sim,
                        preds["line_source"].iloc[0], preds=preds)
    print(f"report: {path}")
    o = ev["overall"]
    print({k: o.get(k) for k in ("n_bets", "hit_rate", "flat_roi", "final_bankroll", "max_drawdown", "logloss_raw",
                                 "logloss", "logloss_market")})


if __name__ == "__main__":
    main()
