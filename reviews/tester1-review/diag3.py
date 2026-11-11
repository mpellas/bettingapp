"""Re-derive the per-season empirical Z (exactly as backtest.predict_season / DistModel.fit_dist) to run
distribution diagnostics. Reads the builder's feature cache + cached predictions; writes only to tester1-review/out."""
import sys, pickle, numpy as np, pandas as pd
sys.path.insert(0, "/workspace/nfl-props/src")
from sklearn.model_selection import GroupKFold
from nflprops.features import feature_columns
from nflprops.markets import universe_mask, MARKETS
from nflprops.model import _lgbm, DistModel
feats = pd.read_parquet("/workspace/nfl-props/data/cache/features_2015_2025.parquet")
cols = feature_columns("full", True, True)
out = {}
for S in range(2019, 2026):
    for mk in ["pass_yds", "rush_yds", "rec_yds"]:
        stat = MARKETS[mk]["stat"]
        df = feats[universe_mask(feats, mk, 20.0)]
        test = df[(df.season == S) & (df.game_type == "REG")]
        tr = df[df.gameday < test.gameday.min()]
        X, y, groups = tr[cols], tr[stat].values, tr["season"].values
        m = DistModel({}, "empirical", 3)
        # replicate fit_dist but keep the training residuals
        oof = np.full(len(y), np.nan)
        for a, b in GroupKFold(n_splits=3).split(X, y, groups):
            oof[b] = _lgbm({}).fit(X.iloc[a], y[a]).predict(X.iloc[b])
        res = y - oof
        m.scale_model = _lgbm({}, n_estimators=200, num_leaves=7, min_child_samples=200).fit(X, np.abs(res))
        s = m._scale(X); z = res / s
        m.z_sorted = np.sort(np.clip(z, -8, 8))
        tr_info = pd.DataFrame({"z": z, "oof": oof, "s": s, "y": y, "position": tr.position.values, "player_id": tr.player_id.values,
                                "season": tr.season.values})
        out[(S, mk)] = {"z_sorted": m.z_sorted, "train": tr_info, "scale_model": m.scale_model}
        print(S, mk, "train rows", len(tr), "median z %.3f  skew-ish mean z %.3f  P(z<0) %.3f" % (np.median(z), z.mean(), (z < 0).mean()), flush=True)
pickle.dump(out, open("/workspace/tester1-review/out/zfits.pkl", "wb"))
