"""Pluggable prop-line sources.

Every source returns, for a frame of candidate player-games of one market, a DataFrame indexed like the input with
columns: line, over_price, under_price (American odds). Rows without a line are NaN (no bet possible).

* SimulatedSharpLines  -- SIMULATED lines (default). NOT real odds. Results on them cannot prove real profitability.
* CsvLines             -- real historical lines from a CSV (schema below). Drop a file in data/lines/ and set
                          `lines.source: csv` + `lines.csv_path` in the config.

CSV schema (one row per player / game / market / book; header required):
    season        int     e.g. 2025
    week          int     NFL week (regular season 1-18)
    player_id     str     nflverse GSIS id (e.g. 00-0033873). Optional if player_name is given.
    player_name   str     display name (used to match when player_id is blank; normalised, case/punctuation-free)
    team          str     optional nflverse team abbr, disambiguates name matches
    market        str     pass_yds | rush_yds | rec_yds
    line          float   e.g. 254.5
    over_price    int     American odds, e.g. -115
    under_price   int     American odds, e.g. -105
    book          str     optional
    timestamp     str     optional ISO time the line was observed (should be PRE-kickoff)
If several rows match one player-game-market the first row (file order) is used — pre-sort by your book preference.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.stats import norm

from .markets import MARKETS


_VOL = {"pass_yds": ("attempts", "p_ypa", 6.8), "rush_yds": ("carries", "p_ypc", 4.2),
        "rec_yds": ("targets", "p_ypt", 7.5)}


def info_projection(rows: pd.DataFrame, market: str) -> pd.Series:
    """ACTUAL in-game volume x PRE-game efficiency. Uses in-game volume => ONLY for simulating the market's
    information edge; never a model feature."""
    vol, eff, prior = _VOL[market]
    e = rows[eff].astype(float)
    n = rows[f"p_{vol}_ewm6"].astype(float).fillna(0)
    e = ((e.fillna(prior) * n) + prior * 3) / (n + 3)            # light shrink toward a generic prior rate
    return rows[vol].astype(float) * e


def _hash_uniform(keys: pd.DataFrame, salt: str) -> np.ndarray:
    h = pd.util.hash_pandas_object(keys.astype(str).assign(_s=salt), index=False).values
    return (h % (2**53)).astype(np.float64) / 2**53 * 0.999998 + 0.000001


@dataclass
class SimulatedSharpLines:
    """SIMULATED sharp line (not real odds):

        base   = r * ref_median + (1 - r) * c * public_proj
        signal = c * (info_proj - public_proj) + e,   e ~ N(0, sigma_m^2)   (the market's NOISY inside info)
        line   = floor( base + beta_m * signal + noise ) + 0.5,              priced `price` on both sides

    v2 change: beta_m is the regression coefficient of (actual - base) on signal (fit on pre-validation seasons), i.e.
    the market uses its information EFFICIENTLY. v1 used an arbitrary small weight w on a noiseless signal; such a line
    under-reacts to information it has, and a stacker could decode the inside info from (line - model) and bet the
    line's direction for +40% simulated ROI — a simulator artefact. Sharpness is now controlled by sigma_m (solved so
    MAE(line)/MAE(public_proj) hits the target ratio), not by under-weighting.

    * public_proj: simple usage-EWMA x Vegas-implied-team-total projection (features.mkt_proj_*).
    * ref_median:  out-of-sample MEDIAN forecast of a fixed reference LightGBM model on public pre-game data
                   (reference.py). r = `ref_share`: r=1 => the market knows everything a strong public model knows
                   (strict/sharp); r=0 => the market is only the simple projection (soft, easy to "beat").
    * info_proj:   what a sharp market "knows" that public pre-game data doesn't: the player's ACTUAL volume in the
                   game (pass attempts / carries / targets) times his PRE-game efficiency. Stands in for injury /
                   role / game-plan news. It deliberately excludes realised per-touch efficiency luck, which nobody
                   can forecast (a variant mixing in realised yards made the 'market' clairvoyant: unrealistic).
                   Enters as a shift (info_proj - public_proj) with weight w, solved per market so that
                   MAE(line)/MAE(public_proj) matches `target_mae_ratio` on pre-validation seasons.
    * c:           per-market median multiplier for the public projection (over-rate 50% on pre-validation seasons;
                   yardage is right-skewed, so mean-type projections overshoot the median).
    * noise:       small, deterministic per (player, game, market): every experiment sees identical lines."""
    info_weight: float = 0.0
    noise_frac: float = 0.01
    seed: int = 7
    price: int = -110
    ref_share: float = 1.0
    median_mult: dict = field(default_factory=dict)
    market_w: dict = field(default_factory=dict)      # per-market beta (efficient weight on the signal)
    info_noise: dict = field(default_factory=dict)    # per-market sigma of the noise on the inside-info signal
    name: str = "simulated_sharp"
    simulated: bool = True

    def get_lines(self, rows: pd.DataFrame, market: str) -> pd.DataFrame:
        pub = rows[f"mkt_proj_{market}"].astype(float)
        c = self.median_mult.get(market, 1.0)
        r = self.ref_share
        ref = rows[f"ref_med_{market}"].astype(float) if r > 0 else 0.0
        base = r * ref + (1 - r) * c * pub
        info = info_projection(rows, market).fillna(pub)
        w = self.market_w.get(market, self.info_weight)
        z2 = norm.ppf(_hash_uniform(rows[["player_id", "game_id"]], f"{market}-info-{self.seed}"))
        signal = c * (info - pub) + self.info_noise.get(market, 0.0) * z2
        proj = base + w * signal
        u = _hash_uniform(rows[["player_id", "game_id"]], f"{market}-{self.seed}")
        noise = norm.ppf(u) * self.noise_frac * proj.clip(lower=10)
        line = np.floor((proj + noise).clip(lower=0.0)) + 0.5
        return pd.DataFrame({"line": line, "over_price": float(self.price), "under_price": float(self.price)},
                            index=rows.index)


def _norm_name(s: pd.Series) -> pd.Series:
    s = s.fillna("").str.lower().str.replace(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", regex=True)
    return s.str.replace(r"[^a-z]", "", regex=True)


@dataclass
class CsvLines:
    path: str
    name: str = "csv"
    simulated: bool = False

    def __post_init__(self):
        df = pd.read_csv(self.path, dtype={"player_id": str})
        need = {"season", "week", "market", "line", "over_price", "under_price"}
        miss = need - set(df.columns)
        if miss:
            raise ValueError(f"lines CSV missing columns {miss}")
        if "player_id" not in df and "player_name" not in df:
            raise ValueError("lines CSV needs player_id or player_name")
        df["name_key"] = _norm_name(df.get("player_name", pd.Series("", index=df.index)))
        self.df = df

    def get_lines(self, rows: pd.DataFrame, market: str) -> pd.DataFrame:
        L = self.df[self.df["market"] == market]
        out = pd.DataFrame(index=rows.index, columns=["line", "over_price", "under_price"], dtype=float)
        r = rows[["season", "week", "player_id", "player_display_name", "team"]].copy()
        r["name_key"] = _norm_name(r["player_display_name"])
        r["_idx"] = rows.index
        cols = ["line", "over_price", "under_price"]
        if "player_id" in L:
            byid = L.dropna(subset=["player_id"]).drop_duplicates(["season", "week", "player_id"])
            m = r.merge(byid[["season", "week", "player_id"] + cols], on=["season", "week", "player_id"])
            out.loc[m["_idx"], cols] = m[cols].values
        todo = r[out["line"].isna().values]
        if len(todo) and L["name_key"].str.len().gt(0).any():
            keys = ["season", "week", "name_key"] + (["team"] if "team" in L and L["team"].notna().all() else [])
            byname = L[L["name_key"].str.len() > 0].drop_duplicates(keys)
            m = todo.merge(byname[keys + cols], on=keys)
            out.loc[m["_idx"], cols] = m[cols].values
        return out


_CALIB: dict = {}


def calibrate_sim(feats: pd.DataFrame, cfg: dict) -> dict:
    """Per market, using ONLY seasons before the first validation season:
      * c: median multiplier of the public projection (over-rate 50%), seasons 2016-2018;
      * sigma (noise on the inside-info signal) solved so MAE(line)/MAE(public projection) = `target_mae_ratio`
        (ratios measured on the ESPN BET 2025 lines, see README), with beta = efficient regression weight given sigma,
        on the seasons with reference forecasts (2017-2018).
    Returns {market: {"beta", "info_noise_sd", "c", "calib_ratio", ...}}."""
    from .markets import universe_mask
    s = cfg["lines"].get("sim", {})
    first_eval = min(cfg["periods"]["validation_seasons"])
    tgt = s.get("target_mae_ratio") or {}
    r = float(s.get("ref_share", 1.0))
    key = chash_small((first_eval, s, cfg.get("universe", {}), cfg["markets"]))
    if key in _CALIB:
        return _CALIB[key]
    out = {}
    nf, seed = s.get("noise_frac", 0.01), s.get("seed", 7)
    for mk in cfg["markets"]:
        rows = feats[universe_mask(feats, mk, cfg.get("universe", {}).get("min_proj", 20.0))
                     & (feats["season"] < first_eval) & (feats["season"] > feats["season"].min())
                     & (feats["game_type"] == "REG")]
        y0, pub0 = rows[MARKETS[mk]["stat"]].values, rows[f"mkt_proj_{mk}"].values
        lo, hi = 0.5, 1.5
        for _ in range(30):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if (y0 > np.floor(mid * pub0) + 0.5).mean() > 0.5 else (lo, mid)
        c = (lo + hi) / 2
        if r > 0:
            rows = rows[rows[f"ref_med_{mk}"].notna()]
        y = rows[MARKETS[mk]["stat"]].values
        mae_pub = np.abs(rows[f"mkt_proj_{mk}"].values - y).mean()

        base = (r * rows[f"ref_med_{mk}"].astype(float) if r > 0 else 0.0) + (1 - r) * c * rows[f"mkt_proj_{mk}"]
        d = (c * (info_projection(rows, mk).fillna(rows[f"mkt_proj_{mk}"]) - rows[f"mkt_proj_{mk}"])).values
        z2 = norm.ppf(_hash_uniform(rows[["player_id", "game_id"]], f"{mk}-info-{seed}"))
        resid = y - np.asarray(base, float)

        def make(k):
            sig = k * d.std()
            sgn = d + sig * z2
            beta = float(np.cov(resid, sgn)[0, 1] / sgn.var(ddof=1))
            src = SimulatedSharpLines(0.0, nf, seed, ref_share=r, median_mult={mk: c}, market_w={mk: beta},
                                      info_noise={mk: sig})
            return src.get_lines(rows, mk)["line"].values, beta, sig
        if mk in tgt:
            lo, hi = np.log(0.01), np.log(100.0)        # bisection on log(noise multiplier k)
            for _ in range(30):
                mid = (lo + hi) / 2
                L, _, _ = make(np.exp(mid))
                lo, hi = (lo, mid) if np.abs(L - y).mean() / mae_pub > tgt[mk] else (mid, hi)
            k = float(np.exp((lo + hi) / 2))
        else:
            k = float(s.get("info_noise_mult", 1.0))
        L, beta, sig = make(k)
        out[mk] = {"beta": round(beta, 4), "info_noise_sd": round(sig, 3), "noise_mult": round(k, 4),
                   "c": round(float(c), 4), "calib_ratio": round(float(np.abs(L - y).mean() / mae_pub), 4),
                   "calib_over_rate": round(float((y > L).mean()), 4),
                   "calib_seasons": sorted(int(x) for x in rows["season"].unique())}
    _CALIB[key] = out
    return out


def chash_small(obj) -> str:
    import hashlib, json
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:10]


def make_line_source(cfg: dict, feats: pd.DataFrame | None = None):
    lc = cfg["lines"]
    if lc["source"] == "simulated":
        s = lc.get("sim", {})
        cal = calibrate_sim(feats, cfg) if feats is not None else {}
        return SimulatedSharpLines(info_weight=s.get("info_weight", 0.0), noise_frac=s.get("noise_frac", 0.01),
                                   seed=s.get("seed", 7), price=s.get("price", -110),
                                   median_mult={m: v["c"] for m, v in cal.items()},
                                   market_w={m: v["beta"] for m, v in cal.items()},
                                   info_noise={m: v["info_noise_sd"] for m, v in cal.items()},
                                   ref_share=float(s.get("ref_share", 1.0)))
    if lc["source"] == "csv":
        from . import ROOT
        from pathlib import Path
        p = Path(lc["csv_path"])
        return CsvLines(str(p if p.is_absolute() else ROOT / p))
    if lc["source"] == "none":
        return NoLines()
    raise ValueError(lc["source"])


class NoLines:
    """No lines at all: projection-only walk-forward (promotion is on projection accuracy since v3, Tester1 N1)."""
    name = "none"
    simulated = False

    def get_lines(self, rows: pd.DataFrame, market: str) -> pd.DataFrame:
        return pd.DataFrame(np.nan, index=rows.index, columns=["line", "over_price", "under_price"])
