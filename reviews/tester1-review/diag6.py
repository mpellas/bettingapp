"""Ablation on the 2025 real-line holdout: how much of the model's signal vs ESPN *opening* lines comes from
features that are only known later (nflverse CLOSING spread/total -> implied_tt/mkt_proj; game-day wind/temp)?
Re-implements backtest.predict_season with a column override; writes nothing into the project."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/nfl-props/src")
from nflprops.features import feature_columns
from nflprops.markets import universe_mask, MARKETS
from nflprops.model import DistModel
from nflprops.lines import CsvLines
from nflprops.betting import add_probs, select_bets
from nflprops.metrics import _ll
from scipy import stats
feats = pd.read_parquet("/workspace/nfl-props/data/cache/features_2015_2025.parquet")
src = CsvLines("/workspace/nfl-props/data/lines/espn_open.csv")
cu = pd.read_csv("/workspace/nfl-props/data/lines/espn_current.csv", dtype={"player_id": str})[["season", "week", "player_id", "market", "line"]].rename(columns={"line": "line_cur"})
full = feature_columns("full", True, True)
LATE = ["team_spread", "total_line", "implied_tt", "wind", "temp", "mkt_proj_pass_yds", "mkt_proj_rush_yds", "mkt_proj_rec_yds"]
variants = {"champion (full)": full, "no closing-vegas/weather/mkt_proj": [c for c in full if c not in LATE]}
def run(cols, S=2025, k=4):
    out = []
    for mk in ["pass_yds", "rush_yds", "rec_yds"]:
        stat = MARKETS[mk]["stat"]; df = feats[universe_mask(feats, mk, 20.0)]
        test = df[(df.season == S) & (df.game_type == "REG")]; weeks = sorted(test.week.unique())
        model = DistModel({}, "empirical", 3)
        for i in range(0, len(weeks), k):
            tb = test[test.week.isin(weeks[i:i + k])]; tr = df[df.gameday < tb.gameday.min()]
            if i == 0: model.fit_dist(tr[cols], tr[stat].values, tr.season.values)
            model.fit_mean(tr[cols], tr[stat].values); mu, s = model.predict(tb[cols])
            r = tb[["season", "week", "game_id", "player_id", "player_display_name", "team", stat]].rename(columns={stat: "actual"}).copy()
            r["mu"], r["s"] = mu, s; L = src.get_lines(tb, mk); r[["line", "over_price", "under_price"]] = L.values
            r["p_over_model"] = np.where(r.line.notna(), model.prob_over(mu, s, r.line.fillna(0).values), np.nan); r["market"] = mk
            out.append(r)
    return pd.concat(out)
cached = pd.read_parquet("/workspace/nfl-props/data/cache/preds/preds_04cd0d349a_2025.parquet")
for name, cols in variants.items():
    pr = run(cols)
    if name.startswith("champion"):
        mm = pr.merge(cached[["player_id", "game_id", "market", "mu"]], on=["player_id", "game_id", "market"])
        print("determinism check: max |mu - cached mu| =", float(np.abs(mm.mu_x - mm.mu_y).max()))
    p0 = add_probs(pr, 0.0); p0 = p0[~p0.push]
    res = {"MAE mu": float((p0.mu - p0.actual).abs().mean())}
    for w in [1.0, 0.5, 0.3]:
        q = w * p0.p_over_model + (1 - w) * p0.p_mkt_over; res[f"LL w={w}"] = float(_ll(q, p0.over_hit).mean())
    res["LL mkt"] = float(_ll(p0.p_mkt_over, p0.over_hit).mean())
    b = select_bets(add_probs(pr, 0.5), {"edge_threshold": 0.04})
    res["diag bets"] = len(b); res["diag ROI"] = float(b.flat_profit.mean()); res["under share"] = float((b.side == "under").mean())
    bb = b.merge(cu, on=["season", "week", "player_id", "market"], how="left").dropna(subset=["line_cur"])
    mv = np.where(bb.side == "under", bb.line - bb.line_cur, bb.line_cur - bb.line)
    up, dn = int((mv > 0).sum()), int((mv < 0).sum())
    res["open->current our way / against"] = f"{up}/{dn} (sign-test p={stats.binomtest(up, up + dn, 0.5).pvalue:.2g})"
    res["mean move (yds)"] = float(mv.mean())
    # direction of disagreement vs line movement on ALL priced lines (not just bets)
    a = p0.merge(cu, on=["season", "week", "player_id", "market"]); dis = a.p_over_model - a.p_mkt_over; mvall = a.line_cur - a.line
    res["corr(model-mkt P(over), line move) all lines"] = float(stats.spearmanr(dis, mvall).correlation)
    print(f"\n== {name} ({len(cols)} features) =="); [print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}") for k, v in res.items()]
