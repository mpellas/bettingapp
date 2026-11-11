"""Build reports/REPORT.md (v3): data + versions, leakage checks, pre-game as-of equivalence, the experiment loop
under the v3 promotion rule (projection accuracy on actual outcomes), champion projection metrics 2019-2024, the
FROZEN 2025 real-line holdout (read from experiments/holdout_frozen.json; never re-scored), the v3 stacker fit on
its history, and snapshot-capture status for 2026.

Simulated-line betting numbers are NOT shown next to real results any more (Tester1 N1/N10): the simulator is
learnable, so its ROI / log-loss-vs-market / stacker weights are artefacts. It remains available only as a
diagnostic (`python -m nflprops.run_backtest --simulated`).

    python -m nflprops.summary
"""
from __future__ import annotations

import contextlib
import io
import glob
import json
import logging

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import DATA, EXPERIMENTS, REPORTS, leakage  # noqa: E402
from .backtest import CODE_FILES, walk_forward  # noqa: E402
from .features import FEATURE_VERSION, code_version, load_features  # noqa: E402
from .holdout import FROZEN, POLICY, policy_sha1  # noqa: E402
from .improve import CHAMP, RUNS, proj_metrics  # noqa: E402
from .report import _fmt  # noqa: E402

DECL = EXPERIMENTS / "policy_declared.json"


def history_chart(runs: pd.DataFrame, st: dict, path):
    fig, ax = plt.subplots(figsize=(9, 4.2))
    c = runs[runs["role"] == "candidate"]
    ax.scatter(c["iteration"], 100 * c["val_rel_crps_gain"], c="lightgrey", label="candidate vs champion (validation)")
    ch = [h for h in st["history"] if "sel_gain" in h]
    if ch:
        ax.errorbar([h["iteration"] for h in ch], [100 * h["sel_gain"] for h in ch],
                    yerr=[100 * h["margin"] for h in ch], fmt="x", color="tab:red", capsize=4,
                    label="challenger on selection (bar = required margin z*SE)")
    pro = [h["iteration"] for h in st["history"] if h.get("promoted")]
    for i in pro:
        ax.axvline(i, color="tab:green", ls=":", lw=1)
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xlabel("improvement iteration (green dotted = promotion)")
    ax.set_ylabel("relative CRPS gain vs champion (%)")
    ax.set_title("Experiment loop, v3 rule: projection accuracy on actual yards")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def pit_chart(preds: pd.DataFrame, path):
    fig, axs = plt.subplots(1, 3, figsize=(12, 3.4), sharey=True)
    for ax, (mk, g) in zip(axs, preds.groupby("market")):
        ax.hist(g["pit"], bins=20, range=(0, 1), density=True, color="tab:blue", alpha=0.8)
        ax.axhline(1, color="k", ls="--", lw=0.8)
        ax.set_title(f"{mk}: PIT (flat = calibrated)")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _leak(legacy: bool, name: str):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        ok = leakage.run(legacy=legacy)
    (REPORTS / name).write_text(buf.getvalue())
    return ok, buf.getvalue().strip()


def holdout_md(fr: dict) -> str:
    r = fr["real_espn_uncertain_timing"]
    rows = []
    for mk, v in list(r["per_market"].items()) + [("ALL", r)]:
        ci = v["roi_ci95_game_clustered"]
        lr, ls = v["ll_gain_raw_vs_market"], v["ll_gain_stacked_vs_market"]
        rows.append({"market": mk, "lines": v["n_lines"], "bets": v["n_bets"], "games bet": v["n_games_bet"],
                     "hit rate": _fmt(v["hit_rate"], True),
                     "flat ROI [95% CI, game-clustered]": f"{_fmt(v['flat_roi'], True)} [{_fmt(ci[0], True)}, {_fmt(ci[1], True)}]",
                     "LL gain raw vs mkt [95% CI]": f"{lr['gain_nats_per_line']:+.4f} [{lr['ci95'][0]:+.4f}, {lr['ci95'][1]:+.4f}]",
                     "LL gain stacked vs mkt [95% CI]": f"{ls['gain_nats_per_line']:+.4f} [{ls['ci95'][0]:+.4f}, {ls['ci95'][1]:+.4f}]"})
    return (f"Scored once at {fr['scored_at']} PT with the pre-declared v2 policy (sha1 `{fr['policy_sha1']}`), "
            f"champion `{fr['champion_hash']}` and the v2 ridge stacker. Read from `experiments/holdout_frozen.json`; "
            "it is not re-scored and is not used to select anything. Lines: **ESPN BET lines of uncertain timing** "
            "(real prices, 2025 REG weeks 1-13).\n\n" + pd.DataFrame(rows).to_markdown(index=False) +
            f"\n\nBankroll 1000 → {r['final_bankroll']:.0f}. Tester1 showed the 18 bets were all rush-yds unders in "
            "weeks 8-10 and were driven mainly by the stacker's intercept, not the model (N4). **Null result.**\n")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    REPORTS.mkdir(exist_ok=True)
    st = json.loads(CHAMP.read_text())
    cfg = st["champion"]
    V, S, H = cfg["periods"]["validation_seasons"], cfg["periods"]["selection_seasons"], cfg["periods"]["holdout_season"]
    feats = load_features(cfg["data"]["first_season"], cfg["data"]["last_season"])
    ok, leak_txt = _leak(False, "leakage_check.txt")
    ok_old, leak_old = _leak(True, "leakage_check_legacy_v1.txt")

    preds = walk_forward(cfg, V + S, feats)
    pm = proj_metrics(preds)
    pit_chart(preds, REPORTS / "champion_pit_2019_2024.png")
    prow = []
    for mk, v in list(pm["per_market"].items()) + [("ALL", pm["overall"])]:
        prow.append({"market": mk, "player-games": v["n"], "CRPS": round(v["crps"], 2), "MAE model": round(v["mae"], 2),
                     "MAE naive EWMA": round(v["mae_naive"], 2), "MAE public proj": round(v["mae_public"], 2),
                     "80% interval coverage (PIT in [0.1,0.9])": f"{v['pit_cov80'] * 100:.1f}%",
                     "mean PIT": round(v["pit_mean"], 3)})
    srow = [{"season": s, "CRPS": round(v["crps"], 2), "MAE": round(v["mae"], 2),
             "80% coverage": f"{v['pit_cov80'] * 100:.1f}%"} for s, v in pm["per_season"].items()]

    runs = pd.json_normalize([json.loads(line) for line in open(RUNS)])
    history_chart(runs, st, REPORTS / "experiment_history.png")
    hist_rows = []
    for h in st["history"]:
        hist_rows.append({"iter": h["iteration"], "event": h.get("event"),
                          "best candidate change": ", ".join(h.get("changes", [])),
                          "val rel CRPS gain": _fmt(h.get("val_rel_crps_gain"), d=5),
                          "val seasons better": h.get("val_seasons_better", "–"),
                          "sel rel CRPS gain": _fmt(h.get("sel_gain"), d=5), "SE (game-clustered)": _fmt(h.get("sel_se"), d=5),
                          "required margin (z*SE)": _fmt(h.get("margin"), d=5),
                          "test # of max": f"{h.get('test_no', '–')} / {st['max_promotion_tests']}",
                          "real-line gate": (h.get("real_gate") or {}).get("status", "–")})
    cand = runs[runs["role"] == "candidate"][["run_id", "iteration", "changes", "val_rel_crps_gain",
                                              "metrics.overall.crps", "metrics.overall.mae",
                                              "metrics.overall.pit_cov80"]]
    cand = cand.assign(changes=cand["changes"].map(lambda x: ", ".join(x)))
    cand.columns = ["run", "iter", "changes", "val rel CRPS gain", "val CRPS", "val MAE", "val 80% coverage"]
    v2 = json.loads((EXPERIMENTS / "archive_v2" / "champion.json").read_text())

    fr = json.loads(FROZEN.read_text()) if FROZEN.exists() else None
    decl = json.loads(DECL.read_text()) if DECL.exists() else {}
    stk = EXPERIMENTS / "stacker_2026_start.json"
    stk = json.loads(stk.read_text()) if stk.exists() else None
    capl = DATA / "snapshots" / "capture_log.jsonl"
    caps = [json.loads(line) for line in capl.read_text().splitlines()] if capl.exists() else []
    cap_md = "_no captures yet_"
    if caps:
        c = pd.DataFrame([{"captured_at_pt": r["captured_at_pt"][:16], "week": r["week"], "event": r["name"],
                           "min to kickoff": r["minutes_to_kickoff"],
                           "lines (pass/rush/rec)": "/".join(str(sum(p["lines_by_market"].get(m, 0)
                                                                     for p in r["providers"].values()))
                                                             for m in ("pass_yds", "rush_yds", "rec_yds")),
                           "priced": sum(p["n_with_prices"] for p in r["providers"].values()),
                           "providers": ",".join(r["providers"]) or "none listed"} for r in caps])
        cap_md = c.tail(40).to_markdown(index=False)
    asof = [json.loads(open(p).read()) for p in sorted(glob.glob(str(REPORTS / "pregame_asof_check_*.json")))] or None
    trk = [json.loads(open(p).read()) for p in sorted(glob.glob(str(DATA / "track" / "*_wk[0-9][0-9].summary.json")))]
    trk_rows = []
    fmt = lambda v: "–" if not v or v.get("mean") is None else (
        f"{v['mean']:+.3f} [{v['ci95_game_clustered'][0]:+.3f}, {v['ci95_game_clustered'][1]:+.3f}] (n={v['n']})")
    for t in trk:
        z = t.get("z_clv") or {}
        trk_rows.append({"season": t["season"], "week": t["week"], "scored at": t["scored_at"][:16],
                         "D lines": t["n_lines_D"], "scored": t["n_scored"], "void": t["n_void"],
                         "pending": t["n_pending"], "out of model scope": t.get("n_out_of_model_scope", "–"),
                         "with C": t["n_with_C"], "pulled_before_close (over/under picks)": (
                             f"{t.get('n_pulled_before_close', '–')} ("
                             f"{(t.get('n_pulled_before_close_by_model_side') or {}).get('over', '–')}/"
                             f"{(t.get('n_pulled_before_close_by_model_side') or {}).get('under', '–')})"),
                         "z-CLV adverse case": fmt((t.get("decision_this_week_only") or {}).get("signal_z_clv_adverse")),
                         "hit rate strong-lean main / adverse": "/".join(
                             "–" if (t.get("decision_this_week_only") or {}).get(k, {}).get("hit_rate") is None
                             else f"{t['decision_this_week_only'][k]['hit_rate']:.3f}"
                             for k in ("break_even_main", "break_even_adverse")),
                         "blanket unders / full-board diagnostic": (
                             lambda d: "–" if not d else "/".join(
                                 "–" if (d.get(k) or {}).get("hit_rate") is None else f"{d[k]['hit_rate']:.3f}"
                                 for k in ("blanket_unders", "hit_rate_full_board_diagnostic")))(
                             t.get("decision_this_week_only") or {}),
                         "C capture failure share (kill rule)": t.get("share_started_no_C_capture_failure", "–"),
                         "void reasons": "; ".join(f"{k}: {v}" for k, v in t["voids_by_reason"].items()) or "–",
                         "z-CLV voids excluded": fmt(z.get("voids_excluded")),
                         "z-CLV voids as zero": fmt(z.get("voids_as_zero")),
                         "bets decided": t["bet_track"]["n_bets_decided"]})
    trk_md = pd.DataFrame(trk_rows).to_markdown(index=False) if trk_rows else "_no tracked weeks yet_"
    fin = sorted(glob.glob(str(DATA / "track" / "*_final_wk*.json")))
    if fin:
        fr_ = json.loads(open(fin[-1]).read())
        dd = fr_["decision"]
        trk_md += (f"\n\n**Final analysis** ({fr_['season']} weeks {fr_['weeks_found']}): **{dd['label']}**. "
                   f"Signal (main) {fmt(dd['signal_z_clv_main'])}, one-sided p {dd['signal_z_clv_main']['p_one_sided_gt0']}; "
                   f"adverse case {fmt(dd['signal_z_clv_adverse'])}; LL criterion ok: {dd['ll_criterion_ok']}; "
                   f"break-even main: {dd['break_even_main']}; adverse: {dd['break_even_adverse']}; "
                   f"blanket unders: {dd.get('blanket_unders')}; "
                   f"full-board diagnostic: {dd.get('hit_rate_full_board_diagnostic')}; "
                   f"pulled in-scope picks over/under: {dd['pulled_in_scope']}.")

    md = f"""# NFL player-prop research pipeline — summary report (v3, after Tester1's second review)

> **Read this first.** No real historical prop odds exist here for 2015-2024, and the line simulator turned out to be
> learnable (Tester1 N1), so **no betting result from simulated lines is reported or used for any decision**. Models
> are now promoted on projection accuracy against actual yards. The only real-price test is the frozen 2025 holdout
> against **ESPN BET lines of uncertain timing** (a null result). The 2026 test runs on free DraftKings-via-ESPN line
> snapshots, which have **no prices**.

## Versions
* code version `{code_version(CODE_FILES)}`; features `{FEATURE_VERSION}`; feature/prediction caches are keyed on code + config
  + a content hash of the data actually used (data version `{feats.attrs.get('data_version')}` for {cfg['data']['first_season']}-{cfg['data']['last_season']}).
* Periods: validation {V}, selection {S}, frozen holdout {H}.

## Leakage check — current: {"PASS" if ok else "FAIL"}; legacy v1: {"PASS (test is blind!)" if ok_old else "FAIL (as it should)"}
```
{leak_txt}
```
<details><summary>legacy v1 output</summary>

```
{leak_old}
```
</details>

## Pre-game scoring (Tester1 N2)
`python -m nflprops.pregame --season S --week W` builds rows for scheduled, unplayed games from data before the
week's first game day only. **Universe = every line in the decision snapshot D** (last capture ≥ 3 h before
kickoff), never the players who later appear in stats/snaps. A D line with no matching player row (no GSIS match,
event not in schedule, no prior NFL data, player's last team not in the game) is written to a per-run void report.
Without a D file the command runs as a clearly labelled DRY RUN (recent-appearance candidates), which never feeds
tracking. As-of equivalence on a played week (pre-game rows vs the post-game build of the same player-games):
{chr(10).join('* `' + json.dumps(a_) + '`' for a_ in asof) if asof else '_not run_'}

## Improvement loop, v3 rule (projection accuracy; no lines)
Candidates are walk-forwarded on validation with **no lines** and scored by CRPS of the predictive distribution
against actual yards. The score is the per-market relative CRPS gain over the champion, averaged over player-games.
A challenger must gain overall **and in at least {cfg['improve']['min_val_seasons_better']} of the 4 validation seasons** (3/4, not 4/4).
On selection {S} it must then clear z × SE (paired game-clustered bootstrap), with z = Φ⁻¹(1 − {cfg['improve']['alpha']}/{st['max_promotion_tests']}) =
{st['z']:.3f}. This is a fixed Bonferroni over a pre-declared maximum of {st['max_promotion_tests']} tests (FWER ≤ α; v2's sequential m bound
was α·H_m, Tester1 N6). The real-line gate applies only where real lines exist outside the frozen holdout (none yet).
Start: the v2 champion's model (`{v2['champion_hash']}`, chosen on simulated lines). Candidates tried: **{st['n_candidates_tried']}**,
promotion tests: **{st['n_promotion_tests']}**, promotions: **{sum(bool(h.get('promoted')) for h in st['history'])}**.
Current champion `{st['champion_hash']}`: `{json.dumps(cfg['model'])}`

![history](experiment_history.png)

{pd.DataFrame(hist_rows).to_markdown(index=False)}

<details><summary>all candidates</summary>

{cand.to_markdown(index=False)}
</details>

## Champion projection accuracy, walk-forward 2019-2024 (actual yards; no lines involved)
{pd.DataFrame(prow).to_markdown(index=False)}

{pd.DataFrame(srow).to_markdown(index=False)}

![pit](champion_pit_2019_2024.png)

## Frozen 2025 holdout (real prices; v2 policy; null result)
{holdout_md(fr) if fr else "_not scored_"}

The v2 pre-declared policy (`configs/holdout_policy.yaml`, sha1 **`{policy_sha1()}`**, published {decl.get('declared_at', '?')}) is kept for
the record; it is frozen and was used once.

## v3 stacker (Tester1 N4/N5)
Hierarchical logistic stacker `logit p = a_m + b·logit(p_mkt) + c_m·logit(p_model)`. Priors: a_m ~ N(0, 0.02²)
(tight, so it cannot bet the season's base rate); b ~ N(1, 0.1²) (shared); c_m ~ N(c0, 0.05²), pooled across markets;
c0 ~ N(0, 0.1²). MAP fit on strictly earlier lines; **no minimum line count**. History for 2026 = the 2025 real lines
(used ONLY as training history, never re-scored for selection) plus earlier 2026 weeks.
Coefficients after fitting on that history (the starting point for 2026 week 5). The pooled model weight c is
small relative to its posterior SE, so stacked p stays close to the market. With the free snapshots' assumed
−110/−110 prices, p_mkt = 0.5 for every line and b cannot be identified from 2026 data:
`{json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in stk.items()}) if stk else 'not fitted yet: python -m nflprops.track stacker'}`

## 2026 tracking (paper z-CLV + diagnostic bet track) with void accounting
`python -m nflprops.track week --season S --week W` starts from every D line. Each line is scored, pending, or VOID
with a reason: carried pregame voids, no pregame prediction before kickoff, **pulled_before_close** (missing from the
last capture before kickoff; C is never taken from an earlier capture), **no closing snapshot C** (capture failure;
the only reason counted in the 20% data kill rule), **player inactive/DNP** (completed game, no stat row and no offensive snap). Weekly void report:
`data/track/<S>_wkWW_voids.csv`. The primary metric is reported two ways: voids excluded, and voids counted as zero.
Diagnostic bets follow DraftKings rules: a bet placed at D on a line later pulled stands if the player recorded a
snap or any stat and is settled on the actual stat; it is refunded only if he did not play. Lines outside
the model scope (min_proj 20 yds / projected-starter QB; e.g. QB rushing) are predicted but listed separately and
excluded from the primary metric and from bets. Pre-registered adverse case: pulled OVER picks get z-CLV −0.25 SD,
pulled UNDER picks 0; for hit rate a pulled line is scored at line_D if the player played (void if not). Passing the
main rule but failing the adverse case = PROVISIONAL. Without prices the PRIMARY break-even bar is the model side's hit rate at line_D on each week's top 20% of
lines by |mu − line_D|/sd (≥ 53.5% and game-clustered 95% lower bound > 50%), and that strong-lean rate must beat a
matched control vs blanket per-market side rates (under/over share of actuals; LB on mean Δ > 0).
PROVISIONAL only when skill bars pass but prices are missing. Full-board 53.5% is diagnostic only. Blanket unders is
reported and does not void the model PASS. `python -m nflprops.track final` pools weeks 5-18.

{trk_md}

## 2026 line snapshots (free; DraftKings via ESPN; no prices)
`python -m nflprops.snapshot` (raw JSON + sha256 manifest under `data/snapshots/<date>/`), `python -m nflprops.snaplines`
(D and C = last NON-EMPTY capture in the decision / close window; empty passes skipped). Captures so far:

{cap_md}

## Appendix: why simulated-line results were removed
Tester1's structure-only decoder (inputs: the simulated line and its construction inputs; no football model) beats
the simulated lines: pass +11.0% ROI on 234 bets in simulated 2023-24. It loses on the real 2025 lines. I re-ran
their script and got identical output. Simulated ROI, log loss vs market and stacker weights are artefacts. Model
*rankings* on simulated lines did agree with CRPS on actual yards (Tester1: Spearman 0.975), which is why
promotion now uses CRPS directly.
"""
    (REPORTS / "REPORT.md").write_text(md)
    print(REPORTS / "REPORT.md")


if __name__ == "__main__":
    main()
