"""NEW, UNVALIDATED challenger count models (receptions, pass completions, rush attempts).
NOT part of the locked nfl-props paper track. Reads nflprops (data + as-of feature code) READ-ONLY.
Features come only from nflprops.features.build_features / nflprops.pregame.pregame_features (the yards path)."""
from __future__ import annotations
import sys, json, glob, re, pickle
from pathlib import Path
import numpy as np, pandas as pd, lightgbm as lgb
from scipy import stats
from scipy.optimize import minimize_scalar
sys.path.insert(0, "/workspace/nfl-props/src")
from nflprops import data as nfdata, CACHE, DATA as NFDATA
from nflprops.features import feature_columns, load_features
from nflprops import pregame

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
MARKETS = {  # our key: (nflverse stat, ESPN O/U item name, odds-api key)
    "receptions": ("receptions", "Total Receptions", "player_receptions"),
    "pass_completions": ("completions", "Total Pass Completions", "player_pass_completions"),
    "rush_attempts": ("carries", "Total Carries", "player_rush_attempts"),
}
COLS = feature_columns("full", True, True)
LGB = dict(objective="poisson", learning_rate=0.03, n_estimators=500, num_leaves=31, min_child_samples=100,
           subsample=0.8, subsample_freq=1, colsample_bytree=0.7, reg_lambda=1.0, verbose=-1, n_jobs=2)


def universe(f, mk):
    pos = f["position"]
    if mk == "receptions":
        return pos.isin(["WR", "TE", "RB", "FB"]) & (f["p_targets_ewm6"] >= 1.5) & (f["p_n_prior"] > 0)
    if mk == "pass_completions":
        return (pos == "QB") & (f["is_proj_starter"] == 1)
    return ((pos.isin(["RB", "FB"]) & (f["p_carries_ewm6"] >= 3)) |
            ((pos == "QB") & (f["is_proj_starter"] == 1))) & (f["p_n_prior"] > 0)


def baseline_mean(f, stat):
    return (0.5 * f[f"p_{stat}_ewm2"] + 0.5 * f[f"p_{stat}_ewm6"]).fillna(0).clip(lower=0.05)


# ---- negative binomial (mean mu, var = mu + alpha mu^2); alpha≈0 -> Poisson
def nb_logpmf(y, mu, a):
    a = max(a, 1e-6); r = 1 / a; p = r / (r + mu)
    return stats.nbinom.logpmf(y, r, p)

def nb_cdf(k, mu, a):
    a = max(a, 1e-6); r = 1 / a; return stats.nbinom.cdf(k, r, r / (r + mu))

def p_over(mu, a, line):
    """P(X > line) for x.5 lines (also fine for integers: strictly greater)."""
    return 1 - nb_cdf(np.floor(line), np.asarray(mu), a)

def fit_alpha(y, mu):
    res = minimize_scalar(lambda la: -nb_logpmf(y, mu, np.exp(la)).sum(), bounds=(-9, 2), method="bounded")
    return float(np.exp(res.x))

def crps(y, mu, a, kmax=80):
    k = np.arange(kmax + 1)[None, :]
    F = nb_cdf(k, mu[:, None], a)
    return ((F - (k >= y[:, None])) ** 2).sum(1)


class CountModel:
    def fit(self, X, y, seasons):
        # dispersion from out-of-season-fold predictions (avoid in-sample under-dispersion)
        oof = np.full(len(y), np.nan); us = np.unique(seasons)
        for fold in np.array_split(us, 3):
            m = ~np.isin(seasons, fold)
            oof[~m] = lgb.LGBMRegressor(**{**LGB, "n_estimators": 300}).fit(X[m], y[m]).predict(X[~m])
        self.alpha = fit_alpha(y, np.clip(oof, 0.05, None))
        self.m = lgb.LGBMRegressor(**LGB).fit(X, y); return self
    def mean(self, X): return np.clip(self.m.predict(X), 0.05, None)


def train_rows(f, mk, before):
    stat = MARKETS[mk][0]
    r = f[universe(f, mk) & (f["gameday"] < before)]
    if "is_pregame_row" in r: r = r[r["is_pregame_row"] == 0]
    return r[r[stat].notna()], stat


# ------------------------------------------------------------------ walk-forward backtest
def backtest(first=2019, last=2025):
    f = load_features(2015, 2026, max_age_h=1e9)
    f = f[f["season_type"].fillna("REG") == "REG"] if "season_type" in f else f
    rows = []
    for mk in MARKETS:
        for s in range(first, last + 1):
            cp = OUT / f"bt_{mk}_{s}.parquet"
            if cp.exists():
                rows.append(pd.read_parquet(cp)); continue
            start = f.loc[f.season == s, "gameday"].min()
            tr, stat = train_rows(f, mk, start)
            te = f[universe(f, mk) & (f.season == s) & f[stat].notna()]
            m = CountModel().fit(tr[COLS].values, tr[stat].values.astype(float), tr["season"].values)
            mu = m.mean(te[COLS].values); y = te[stat].values.astype(float)
            bmu_tr = baseline_mean(tr, stat); ab = fit_alpha(tr[stat].values, bmu_tr.values)
            bmu = baseline_mean(te, stat).values
            line = np.floor(bmu) + 0.5               # synthetic line ~ public rolling average
            rows.append(pd.DataFrame({"market": mk, "season": s, "player_id": te.player_id.values,
                "week": te.week.values, "y": y, "mu": mu, "alpha": m.alpha, "b_mu": bmu, "b_alpha": ab,
                "line": line}))
            rows[-1].to_parquet(cp)
            print(mk, s, len(te), "alpha", round(m.alpha, 4), flush=True)
    bt = pd.concat(rows, ignore_index=True); bt.to_parquet(OUT / "backtest_rows.parquet"); return bt


def summarize(bt):
    out = []
    for (mk, hold), g in bt.groupby(["market", bt.season == 2025]):
        a, ab = g.alpha.iloc[0], g.b_alpha.iloc[0]
        ll = -np.mean([nb_logpmf(y, m, a) for y, m, a in zip(g.y, g.mu, g.alpha)])
        bll = -np.mean([nb_logpmf(y, m, a) for y, m, a in zip(g.y, g.b_mu, g.b_alpha)])
        cr = np.mean(np.concatenate([crps(x.y.values, x.mu.values, x.alpha.iloc[0]) for _, x in g.groupby("season")]))
        bcr = np.mean(np.concatenate([crps(x.y.values, x.b_mu.values, x.b_alpha.iloc[0]) for _, x in g.groupby("season")]))
        po = np.concatenate([p_over(x.mu.values, x.alpha.iloc[0], x.line.values) for _, x in g.groupby("season")])
        bpo = np.concatenate([p_over(x.b_mu.values, x.b_alpha.iloc[0], x.line.values) for _, x in g.groupby("season")])
        gg = pd.concat([x for _, x in g.groupby("season")]); hit = (gg.y > gg.line).values
        out.append({"market": mk, "split": "holdout_2025" if hold else "dev_2019_2024", "n": len(g),
                    "nll_model": ll, "nll_base": bll, "crps_model": cr, "crps_base": bcr,
                    "mae_model": np.mean(abs(gg.y - gg.mu)), "mae_base": np.mean(abs(gg.y - gg.b_mu)),
                    "brier_model_synthline": np.mean((po - hit) ** 2), "brier_base_synthline": np.mean((bpo - hit) ** 2)})
    return pd.DataFrame(out)


def calibration_2025(bt):
    g = bt[bt.season == 2025]; res = []
    for mk, x in g.groupby("market"):
        po = p_over(x.mu.values, x.alpha.iloc[0], x.line.values); hit = (x.y > x.line).values
        b = pd.cut(po, [0, .3, .4, .45, .5, .55, .6, .7, 1])
        t = pd.DataFrame({"bin": b, "p": po, "hit": hit}).groupby("bin", observed=True).agg(n=("p", "size"), pred=("p", "mean"), actual=("hit", "mean"))
        t["market"] = mk; res.append(t.reset_index())
    return pd.concat(res)


# ------------------------------------------------------------------ live / pregame prediction
def _models_for(season, week, d=None, f_all=None):
    """Frozen models: trained on all real rows before the season's week-1 game (2026 data before that = 2015-2025).
    In-season block refit: rows before this week's first game day (data truncated by pregame path)."""
    p = OUT / f"models_{season}_wk{week}.pkl"
    if p.exists(): return pickle.loads(p.read_bytes())
    return None


def predict(week: int, season: int = 2026, lines: pd.DataFrame | None = None, max_age_h: float = 12.0):
    """Returns one row per (player, market) with mu, alpha, and p_over_<line> helper columns.
    Use p_over(mu, alpha, line) for any line. Features via nflprops.pregame.pregame_features (as-of, data truncated
    before the week's first game day). `lines` (optional) = DataFrame[event_id, player_id, player_name, market,
    line, void_reason] for snapshot-based rows; else the dry-run candidate universe (players from last 2 games)."""
    d = nfdata.load(2015, season, max_age_h=max_age_h)
    f, dt_, extra, cutoff, voids = pregame.pregame_features(d, season, week, 2, lines)
    out = []
    cache = OUT / f"models_{season}_wk{week}.pkl"
    models = pickle.loads(cache.read_bytes()) if cache.exists() else {}
    for mk, (stat, _, okey) in MARKETS.items():
        if mk not in models:
            tr, _ = train_rows(f, mk, cutoff)
            models[mk] = CountModel().fit(tr[COLS].values, tr[stat].values.astype(float), tr["season"].values)
        te = f[(f.get("is_pregame_row", 0) == 1) & (f.season == season) & (f.week == week) & universe(f, mk)]
        m = models[mk]; mu = m.mean(te[COLS].values)
        r = te[["season", "week", "game_id", "player_id", "player_display_name", "team", "opponent", "position"]].copy()
        r["market"] = mk; r["odds_api_key"] = okey; r["mu"] = mu; r["alpha"] = m.alpha
        r["baseline_mu"] = baseline_mean(te, stat).values
        r["n_prior_games"] = te["p_n_prior"].values; r["model_status"] = "NEW_UNVALIDATED_CHALLENGER"
        out.append(r)
    cache.write_bytes(pickle.dumps(models))
    P = pd.concat(out, ignore_index=True)
    P["cutoff"] = str(cutoff)
    return P


# ------------------------------------------------------------------ real ESPN lines from raw captures
def espn_lines(since="2026-10-04"):
    """Last capture strictly before kickoff per (event, player, market) for the 3 count markets, plus the D capture
    (last capture >= 3h before kickoff). Read-only parse of data/snapshots; no hash-checked file is modified."""
    log = [json.loads(l) for l in open(NFDATA / "snapshots/capture_log.jsonl")]
    names = {v[1]: k for k, v in MARKETS.items()}
    pl = pd.read_parquet(CACHE / "players.parquet")[["gsis_id", "display_name", "espn_id"]].dropna(subset=["espn_id"])
    pl["espn_id"] = pl["espn_id"].astype(str).str.replace(r"\.0$", "", regex=True)
    rows = []
    for rec in log:
        cap = pd.Timestamp(rec["captured_at_utc"]); kick = pd.Timestamp(rec["kickoff_utc"])
        if cap < pd.Timestamp(since, tz="UTC") or cap >= kick or rec.get("season_type", 2) != 2: continue
        day = NFDATA / "snapshots" / cap.tz_convert("America/Los_Angeles").strftime("%Y-%m-%d")
        for fi in rec["files"]:
            if "_odds_" in fi["file"] or not (day / fi["file"]).exists(): continue
            for it in json.load(open(day / fi["file"])).get("items", []):
                nm = re.sub(r"\s*\(incl\.? overtime\)\s*$", "", it.get("type", {}).get("name", ""), flags=re.I).strip()
                if nm not in names or "athlete" not in it: continue
                a = re.search(r"/athletes/(\d+)", it["athlete"]["$ref"]); cur = it.get("current") or {}
                t = (cur.get("target") or {}).get("value")
                if a is None or t is None: continue
                rows.append({"season": rec["season"], "week": rec["week"], "event_id": str(rec["event_id"]),
                             "espn_id": a.group(1), "market": names[nm], "line": float(t),
                             "over_price": (cur.get("over") or {}).get("american"),
                             "under_price": (cur.get("under") or {}).get("american"),
                             "captured": cap, "kick": kick})
    L = pd.DataFrame(rows).drop_duplicates()
    L = L.merge(pl.rename(columns={"gsis_id": "player_id", "display_name": "player_name"}), on="espn_id", how="left")
    # only clean single-line (player, market) per capture
    n = L.groupby(["event_id", "espn_id", "market", "captured"])["line"].transform("nunique")
    L = L[n == 1]
    last = L.sort_values("captured").groupby(["event_id", "espn_id", "market"]).tail(1).assign(kind="close")
    D = L[L.captured <= L.kick - pd.Timedelta(hours=3)].sort_values("captured").groupby(
        ["event_id", "espn_id", "market"]).tail(1).assign(kind="D")
    return pd.concat([last, D], ignore_index=True)
