"""Independent checks of Tester1's claims against the v1 pipeline (run BEFORE the v2 fixes).
Uses only cached v1 artefacts; writes audit/verify_tester1_v1.txt."""
import json
import numpy as np
import pandas as pd
import sys
sys.path.insert(0, "src")
from nflprops.betting import add_probs, select_bets, american_to_decimal

out = []
P = lambda *a: out.append(" ".join(str(x) for x in a))

# B5: ESPN timestamps vs kickoff; multiple main pairs
s = pd.read_parquet("data/cache/schedules.parquet")
s = s[s.season == 2025][["espn", "gameday", "gametime"]].dropna()
s["kick_utc"] = (pd.to_datetime(s.gameday + " " + s.gametime).dt.tz_localize("America/New_York").dt.tz_convert("UTC"))
for f in ["data/lines/espn_open.csv", "data/lines/espn_current.csv"]:
    L = pd.read_csv(f, dtype={"event_id": str})
    m = L.merge(s.assign(espn=s.espn.astype(str)), left_on="event_id", right_on="espn")
    ts = pd.to_datetime(m.timestamp, utc=True)
    P(f"B5 {f}: {len(m)} rows, share timestamp after kickoff = {(ts > m.kick_utc).mean():.3f}")
import glob, re
multi = 0
for fn in glob.glob("/workspace/prop-finder/data/hist_props/nfl/*.json"):
    raw = json.load(open(fn)); cnt = {}
    for it in raw.get("props", {}).get("58", []):
        nm = re.sub(r"\s*\(incl\.? overtime\)\s*$", "", (it.get("type") or {}).get("name", ""), flags=re.I).strip()
        if nm not in ("Total Passing Yards", "Total Rushing Yards", "Total Receiving Yards") or "athlete" not in it:
            continue
        o = it.get("open") or {}
        if "over" in o or "under" in o:
            k = (it["athlete"]["$ref"], nm, "over" if "over" in o else "under")
            cnt[k] = cnt.get(k, 0) + 1
    multi += len({(a, n) for (a, n, sd), c in cnt.items() if c > 1})
P(f"B5 athlete-markets with >1 main over/under item (open block): {multi}")

# B2: blend used by every logged run
runs = [json.loads(l) for l in open("experiments/runs.jsonl")]
P("B2 market_blend values in v1 runs:", sorted({r["betting"]["market_blend"] for r in runs}))
P("B2 v1 grid:", "market_blend [0.0, 0.25, 0.5, 0.75, 0.9] (no 1.0) per configs/default.yaml")

# B6 + D1: clustered CI for the 995-bet diagnostic result
pr = pd.read_parquet("data/cache/preds/preds_04cd0d349a_2025.parquet")
p = add_probs(pr, 0.5); b = select_bets(p, {"edge_threshold": 0.04})
P(f"B6 diagnostic bets {len(b)}, flat ROI {b.flat_profit.mean():.4f}, iid 95% half-width {1.96*b.flat_profit.std(ddof=1)/np.sqrt(len(b)):.4f}")
rng = np.random.default_rng(0)
for key in ["game_id", "week"]:
    g = b.groupby(key).flat_profit.agg(["sum", "size"])
    idx = rng.integers(0, len(g), (4000, len(g)))
    r = g["sum"].values[idx].sum(1) / g["size"].values[idx].sum(1)
    P(f"B6 cluster={key} ({len(g)} clusters): 95% CI [{np.quantile(r,.025):.4f}, {np.quantile(r,.975):.4f}]")
P(f"B6 bets per game mean {b.groupby('game_id').size().mean():.2f} max {b.groupby('game_id').size().max()}")

# B8: EV>0 filter makes small thresholds no-ops
for thr in [0.02, 0.03, 0.04]:
    P(f"B8 real 2025 blend 0.5 threshold {thr}: bets {len(select_bets(p, {'edge_threshold': thr}))}")
P("B8 break-even no-vig edge at -115/-115:", round(1/american_to_decimal(-115)[()] - 0.5, 4), " at -110/-110:",
  round(1/american_to_decimal(-110)[()] - 0.5, 4))

# B1 (starter): how often is the actual starter not last game's starter?
f = pd.read_parquet("data/cache/features_2015_2025.parquet")
st = f[f.is_starting_qb == 1].sort_values(["team", "gameday"])
st["prev_starter"] = st.groupby("team").player_id.shift(1)
P(f"B1 actual starter != team's previous-game starter in {(st.player_id != st.prev_starter).mean():.3f} of starts (2015-25)")
open("audit/verify_tester1_v1.txt", "w").write("\n".join(out) + "\n")
print("\n".join(out))
