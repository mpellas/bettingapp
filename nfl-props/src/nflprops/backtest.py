"""Walk-forward (expanding-window) engine.

For each test season S and each block of `retrain_every_weeks` weeks:
    train on every universe row with gameday < first game of the block (all prior seasons + earlier weeks of S),
    predict the block. The residual/scale model (needs internal OOF fits) is refit once per test season.
Predictions are cached per (model config, season) so betting-parameter searches are cheap.
"""
from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd

from . import CACHE
from .config import chash, model_key
from .features import code_version, data_version_for, feature_columns, load_features
from .lines import make_line_source
from .markets import MARKETS, universe_mask
from .model import DistModel, crps_from_quantiles
from .reference import attach_reference

log = logging.getLogger(__name__)
PRED_CACHE = CACHE / "preds"


def _prep(feats: pd.DataFrame, cfg: dict, market: str) -> pd.DataFrame:
    u = cfg.get("universe", {})
    m = universe_mask(feats, market, u.get("min_proj", 20.0))
    return feats[m].copy()


def predict_season(feats: pd.DataFrame, cfg: dict, market: str, season: int) -> pd.DataFrame:
    mc = cfg["model"]
    cols = feature_columns(mc["feature_set"], mc.get("use_snaps", True), mc.get("use_market_proj", True))
    stat = MARKETS[market]["stat"]
    df = _prep(feats, cfg, market)
    test = df[(df["season"] == season) & (df["game_type"] == "REG")]
    weeks = sorted(test["week"].unique())
    k = int(mc.get("retrain_every_weeks", 4))
    src = make_line_source(cfg, feats)
    model = DistModel(mc.get("lgbm", {}), mc.get("dist", "empirical"), mc.get("n_folds", 3))
    out = []
    for i in range(0, len(weeks), k):
        blk = weeks[i:i + k]
        tb = test[test["week"].isin(blk)]
        start = tb["gameday"].min()
        tr = df[df["gameday"] < start]
        Xtr, ytr = tr[cols], tr[stat].values
        if i == 0:
            model.fit_dist(Xtr, ytr, tr["season"].values)
        model.fit_mean(Xtr, ytr)
        mu, s = model.predict(tb[cols])
        qp = model.quantiles(mu, s)
        r = tb[["season", "week", "gameday", "game_id", "player_id", "player_display_name", "team", "opponent",
                "position", stat, f"mkt_proj_{market}", f"naive_{market}"]].copy()
        r = r.rename(columns={stat: "actual", f"mkt_proj_{market}": "mkt_proj", f"naive_{market}": "naive"})
        r["mu"], r["s"] = mu, s
        r["crps"] = crps_from_quantiles(qp, r["actual"].values)
        r["pit"] = 1.0 - model.prob_over(mu, s, r["actual"].values)       # PIT = F(actual); uniform if calibrated
        r["n_train"] = len(tr)
        # lines + model P(over) at the line (needs the model's residual distribution, so done here)
        L = src.get_lines(tb, market)
        r[["line", "over_price", "under_price"]] = L.values
        r["p_over_model"] = np.where(r["line"].notna(), model.prob_over(mu, s, r["line"].fillna(0).values), np.nan)
        out.append(r)
    res = pd.concat(out)
    res["market"] = market
    res["line_source"] = src.name
    res["line_simulated"] = src.simulated
    return res


CODE_FILES = ["data.py", "features.py", "markets.py", "model.py", "lines.py", "reference.py", "backtest.py"]


def pred_key(cfg: dict, data_version: str | None = None) -> str:
    """Prediction-cache key = config hash (paths relative, CSV content hashed) + code/feature version + data version
    (Tester1 B7 / N3 / N9)."""
    dv = data_version or data_version_for(cfg["data"]["first_season"], cfg["data"]["last_season"])
    return f"{chash(model_key(cfg))}_{code_version(CODE_FILES)}_{dv}"


def walk_forward(cfg: dict, seasons: list[int], feats: pd.DataFrame | None = None, use_cache=True) -> pd.DataFrame:
    PRED_CACHE.mkdir(parents=True, exist_ok=True)
    key = pred_key(cfg, feats.attrs.get("data_version") if feats is not None else None)
    parts = []
    for s in seasons:
        p = PRED_CACHE / f"preds_{key}_{s}.parquet"
        if use_cache and p.exists():
            parts.append(pd.read_parquet(p))
            continue
        if feats is None:
            feats = load_features(cfg["data"]["first_season"], cfg["data"]["last_season"])
        feats = attach_reference(feats, cfg)
        t = time.time()
        ps = pd.concat([predict_season(feats, cfg, m, s) for m in cfg["markets"]])
        ps.to_parquet(p, index=False)
        log.info("season %s predicted in %.1fs (%s rows) [model %s]", s, time.time() - t, len(ps), key)
        parts.append(ps)
    return pd.concat(parts, ignore_index=True)
