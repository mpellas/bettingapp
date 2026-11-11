"""Reference ("market-knowledge") model for the simulated sharp lines.

A sharp market already knows everything a competent public-data model knows. So the simulated line is built on the
out-of-sample median forecast of a FIXED reference LightGBM model (full feature set, default hyper-parameters,
expanding window, retrained once per season), not on a naive projection. Candidate models therefore only show an
edge if they genuinely improve on a strong public baseline — and the market additionally gets a small "inside info"
term (see lines.SimulatedSharpLines). Predictions are cached in data/cache/ref_preds_<hash>.parquet.
The reference model is part of the *environment* (like the lines) and is never changed by the experiment loop.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import CACHE
from .config import chash
from .features import code_version, feature_columns
from .markets import MARKETS, universe_mask
from .model import DistModel

log = logging.getLogger(__name__)


def get_reference(feats: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    rc = cfg["lines"]["sim"].get("reference", {})
    first = int(rc.get("first_season", 2017))
    seasons = [s for s in sorted(feats["season"].unique()) if s >= first]
    key = chash({"ref": rc, "markets": cfg["markets"], "universe": cfg.get("universe", {}), "seasons": seasons,
                 "n": len(feats), "code": code_version(["features.py", "model.py", "markets.py", "reference.py"])})
    p = CACHE / f"ref_preds_{key}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    cols = feature_columns(rc.get("feature_set", "full"), True, True)
    out = []
    for mk in cfg["markets"]:
        stat = MARKETS[mk]["stat"]
        df = feats[universe_mask(feats, mk, cfg.get("universe", {}).get("min_proj", 20.0))]
        for s in seasons:
            tr, te = df[df["season"] < s], df[df["season"] == s]
            m = DistModel(rc.get("lgbm", {}), "empirical", 3)
            m.fit_dist(tr[cols], tr[stat].values, tr["season"].values)
            m.fit_mean(tr[cols], tr[stat].values)
            mu, sc = m.predict(te[cols])
            med = mu + sc * float(np.median(m.z_sorted))
            out.append(pd.DataFrame({"player_id": te["player_id"].values, "game_id": te["game_id"].values,
                                     "market": mk, "ref_med": med}))
        log.info("reference model %s done", mk)
    ref = pd.concat(out).pivot_table(index=["player_id", "game_id"], columns="market", values="ref_med")
    ref.columns = [f"ref_med_{c}" for c in ref.columns]
    ref = ref.reset_index()
    ref.to_parquet(p, index=False)
    return ref


def attach_reference(feats: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    if cfg["lines"]["source"] != "simulated" or float(cfg["lines"]["sim"].get("ref_share", 1.0)) <= 0:
        return feats
    if "ref_med_pass_yds" in feats.columns:
        return feats
    return feats.merge(get_reference(feats, cfg), on=["player_id", "game_id"], how="left")
