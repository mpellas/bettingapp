"""Score the FROZEN count models (no tuning) against real ESPN lines from raw captures since Oct 4, 2026."""
import numpy as np, pandas as pd, counts
from nflprops import data as nfdata
L = counts.espn_lines()
d = nfdata.load(2015, 2026, max_age_h=12)
ps = d["player_stats"]; ps = ps[ps.season == 2026]
res = []
for wk in sorted(L.week.unique()):
    lw = L[L.week == wk]
    inp = lw.drop_duplicates(["event_id", "player_id"])[["event_id", "player_id", "player_name", "market", "line"]].assign(void_reason=np.nan)
    P = counts.predict(int(wk), 2026, lines=inp)
    m = lw.merge(P[["player_id", "market", "mu", "alpha", "baseline_mu"]], on=["player_id", "market"], how="left")
    st = ps[ps.week == wk][["player_id", "receptions", "completions", "carries"]]
    m = m.merge(st, on="player_id", how="left")
    m["actual"] = np.select([m.market == "receptions", m.market == "pass_completions"], [m.receptions, m.completions], m.carries)
    res.append(m)
R = pd.concat(res, ignore_index=True)
R["p_over"] = counts.p_over(R.mu.values, 1.0, R.line.values) * np.nan
R["p_over"] = [counts.p_over(mu, a, l) if pd.notna(mu) else np.nan for mu, a, l in zip(R.mu, R.alpha, R.line)]
R.to_csv("out/espn_line_scoring_rows.csv", index=False)
done = R[R.actual.notna() & R.mu.notna()].copy()
done["over_hit"] = done.actual > done.line
done["pick_over"] = done.p_over > 0.5
done["pick_win"] = done.pick_over == done.over_hit
done["brier"] = (done.p_over - done.over_hit) ** 2
print("rows total", len(R), "scored (game played + model row)", len(done), "missing model row", R.mu.isna().sum())
print(done.groupby(["kind", "market"]).agg(n=("line", "size"), over_rate=("over_hit", "mean"), mean_p_over=("p_over", "mean"),
      lean_hit_rate=("pick_win", "mean"), brier=("brier", "mean"), mean_mu_minus_line=("mu", lambda s: (s - done.loc[s.index, "line"]).mean()),
      mae_model=("mu", lambda s: (s - done.loc[s.index, "actual"]).abs().mean()), mae_line=("line", lambda s: (s - done.loc[s.index, "actual"]).abs().mean())).to_string())
for k in ("close", "D"):
    x = done[done.kind == k]; print(k, "ALL n", len(x), "lean hit", round(x.pick_win.mean(), 3), "brier", round(x.brier.mean(), 4), "brier@0.5", 0.25)
