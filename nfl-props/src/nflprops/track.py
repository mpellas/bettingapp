"""2026 out-of-sample tracking (paper track + notional bet track), from frozen pre-game predictions and snapshots.

    python -m nflprops.track stacker                     # fit the hierarchical stacker on its HISTORY (2025 real
                                                         # ESPN lines of uncertain timing) and print the coefficients
    python -m nflprops.track week --season 2026 --week 5 # score one week (needs pregame preds + snapshot D/C lines)

History rule: the 2025 real lines are used ONLY as stacker training history. The frozen 2025 holdout result is
not re-scored and nothing is selected on 2025.
Universe: EVERY line in the decision snapshot D (last capture >=3h before kickoff), never the players who later
appear in stats/snaps. Each D line is scored or VOID with a reason (no matching player row, no pregame prediction
before kickoff, no closing snapshot C, player inactive/DNP); voids go to data/track/<S>_wkWW_voids.csv and are
counted, never silently dropped. Diagnostic bets follow DraftKings rules (pulled line: stands and settles on
the stat if the player played; refund only if he did not). Lines outside the model scope (pre-registered min_proj 20 yds / projected-starter
QB; e.g. QB rushing lines, low receiving lines) are predicted but reported separately (<S>_wkWW_out_of_scope.csv)
and excluded from the primary metric and bets. The primary metric (mean z-CLV) and the bet-track ROI are reported two ways:
voids excluded, and voids counted as zero.
Week scoring uses, per game, the latest SNAPSHOT-mode pregame prediction file created BEFORE that game's kickoff;
P_model(over | line_D) is the champion's prob_over stored by pregame (quantile interpolation fallback); stacked p
from the hierarchical stacker fit on history + earlier tracked weeks; z-CLV = sign(P_model(over|D) - 0.5) *
(line_C - line_D) / sd, sd = (q84 - q16) / 2 of the predictive distribution.
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import hashlib
import json

import numpy as np
import pandas as pd

from . import DATA, EXPERIMENTS
from .backtest import walk_forward
from .betting import add_probs, american_to_decimal, no_vig_over, select_bets
from .calibration import hier_stacked_probs
from .config import deep_update
from .features import load_features
from .pregame import champion_cfg

TRACK = DATA / "track"
QCOLS = [f"q{i:02d}" for i in range(1, 100)]
QLEV = np.linspace(0.01, 0.99, 99)


def history(cfg: dict) -> pd.DataFrame:
    """Champion walk-forward predictions on the 2025 real lines (training history for the stacker only)."""
    csv = cfg["betting"].get("stacker_history_csv")
    if not csv:
        return pd.DataFrame()
    c = deep_update(cfg, {"lines": {"source": "csv", "csv_path": csv},
                          "data": {"last_season": max(2025, cfg["data"]["last_season"])}})
    f = load_features(c["data"]["first_season"], c["data"]["last_season"])
    h = walk_forward(c, [2025], f)
    return add_probs(h, 0.0)


def fit_stacker_now(cfg: dict) -> dict:
    h = history(cfg)
    p = h.iloc[0:0].copy()
    nxt = h.assign(season=2026, week=1).iloc[:3]          # dummy target week: coefficients fit on all history
    _, _, co = hier_stacked_probs(nxt, h, cfg["betting"].get("stacker_prior"))
    out = co.iloc[-1].to_dict()
    out.update({"history_lines": int(len(h)), "history_csv": cfg["betting"].get("stacker_history_csv"),
                "prior": cfg["betting"].get("stacker_prior")})
    _ = p
    return out


def p_over_from_q(q: np.ndarray, line: np.ndarray) -> np.ndarray:
    out = np.full(len(line), np.nan)
    for i, (qq, L) in enumerate(zip(q, line)):
        if np.isfinite(L):
            out[i] = 1 - np.interp(L, qq, QLEV, left=0.0, right=1.0)
    return out


VOID_COLS = ["season", "week", "event_id", "game_id", "player_id", "player_name", "market", "line_D", "line_C",
             "void_reason", "void_detail", "stage"]
PULLED = "pulled_before_close"
NO_C = "no closing snapshot C"           # capture failure: no valid capture in the 30 min before kickoff
INACTIVE = "player inactive / DNP (no stat row and no offensive snap)"
# DraftKings rules for the diagnostic bet track: a bet placed at D stands if the line was later pulled (or our close
# capture failed) as long as the player recorded a snap or any stat; it is settled on the actual stat. Refund only
# if he did not play.
ADVERSE_OVER_Z = -0.25         # pre-registered adverse case: pulled OVER pick -> z-CLV -0.25 SD; pulled UNDER -> 0
BE_HIT_STRONG = 0.535          # without-prices PRIMARY bar: top-20% |lean| hit rate (provisional)
BE_HIT_FULL = 0.535            # full-board hit rate: DIAGNOSTIC only (same point bar; not the success rule)
STRONG_LEAN_FRAC = 0.20        # top share of lines by |mu - line_D| / sd within each week
BOOK_STANDS = (PULLED, NO_C, "duplicate_line at C: more than one closing line for this player+market")
STAT = {"pass_yds": "passing_yards", "rush_yds": "rushing_yards", "rec_yds": "receiving_yards"}


def cluster_boot(v: np.ndarray, groups: np.ndarray, n_boot: int = 4000, seed: int = 0) -> np.ndarray:
    """Game-clustered bootstrap distribution of the mean (4000 resamples, seed 0, pre-registered)."""
    v, groups = np.asarray(v, dtype=float), np.asarray(groups)
    ug = pd.unique(groups)
    idx = {g: np.where(groups == g)[0] for g in ug}
    rng = np.random.default_rng(seed)
    return np.array([v[np.concatenate([idx[g] for g in rng.choice(ug, len(ug))])].mean() for _ in range(n_boot)])


def cluster_ci(v: np.ndarray, groups: np.ndarray, n_boot: int = 4000, seed: int = 0) -> tuple[float, float]:
    """95% game-clustered bootstrap CI of the mean."""
    if len(v) == 0:
        return (float("nan"), float("nan"))
    m = cluster_boot(v, groups, n_boot, seed)
    return (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5)))


def mean_test(v, groups) -> dict:
    """Mean, 95% game-clustered CI and one-sided bootstrap p for mean > 0."""
    v = np.asarray(v, dtype=float)
    if len(v) == 0:
        return {"n": 0, "mean": None, "ci95_game_clustered": None, "p_one_sided_gt0": None}
    m = cluster_boot(v, groups)
    return {"n": int(len(v)), "n_games": int(len(pd.unique(np.asarray(groups)))), "mean": float(v.mean()),
            "ci95_game_clustered": (float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))),
            "p_one_sided_gt0": float((m <= 0).mean())}


def hit_test(h, groups, bar: float = BE_HIT_STRONG, null: float = 0.5) -> dict:
    """Hit rate of the model side at line_D vs actual stats; pass = estimate >= bar AND clustered lower 95% > null."""
    h = np.asarray(h, dtype=float)
    if len(h) == 0:
        return {"n": 0, "hit_rate": None, "ci95_game_clustered": None, "pass": False}
    m = cluster_boot(h, groups)
    lo, hi = float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))
    return {"n": int(len(h)), "hit_rate": float(h.mean()), "ci95_game_clustered": (lo, hi), "bar": bar,
            "pass": bool(h.mean() >= bar and lo > null)}


def two_versions(x: pd.DataFrame, col: str, void: pd.Series) -> dict:
    """Primary metric two ways: voids excluded, and voids counted as zero (kept in the denominator)."""
    ok = ~void & x[col].notna()
    a = x.loc[ok, col].values
    b = np.where(void, 0.0, x[col].fillna(0.0)).astype(float)
    return {"voids_excluded": {"n": int(ok.sum()), "mean": float(a.mean()) if len(a) else None,
                               "ci95_game_clustered": cluster_ci(a, x.loc[ok, "game_id"].values)},
            "voids_as_zero": {"n": int(len(x)), "mean": float(b.mean()) if len(b) else None,
                              "ci95_game_clustered": cluster_ci(b, x["game_id"].values)}}


def add_case_columns(x: pd.DataFrame, q: np.ndarray) -> pd.DataFrame:
    """Per-line columns for the primary metric, the adverse case, the hit-rate bars and the price rule (stored in the
    weekly parquet so the final analysis pools lines across weeks).
      in_scope   : prediction exists and the line is in the pre-registered model scope
      model_side : over if P_model(over | line_D) > 0.5, under if < 0.5 (none at exactly 0.5)
      abs_lean   : |mu - line_D| / sd (raw lean used for the top-20% without-prices bar)
      z_main     : z-CLV on non-void in-scope lines whose game is known (NaN otherwise)
      z_adverse  : z_main, plus pulled_before_close in-scope lines: OVER pick -> -0.25, UNDER pick -> 0
      hit_main   : model side wins at line_D vs actual (non-void, settled, in-scope, pushes excluded)
      hit_adverse: hit_main plus pulled in-scope lines where the player played (scored at line_D vs actual);
                   pulled and did not play -> void (NaN)
      hit_under  : always-under at line_D vs actual (same board as hit_main; blanket-unders control)
      real_prices, q_side_close, be_D_side: inputs of the with-prices rule"""
    x = x.copy()
    pm = x["p_over_model"]
    x["model_side"] = np.where(pm > 0.5, "over", np.where(pm < 0.5, "under", None))
    x["in_scope"] = x["q50"].notna() & (x["in_model_universe"] == True)  # noqa: E712
    known = x["status"] != "pending"
    base = x["in_scope"] & known & ~x["void"]
    pulled = x["in_scope"] & (x["void_reason"] == PULLED)
    sd = x["sd"].replace(0, np.nan)
    x["abs_lean"] = (x["mu"] - x["line_D"]).abs() / sd
    x["z_main"] = np.where(base, x["z_clv"], np.nan)
    x["z_adverse"] = np.where(pulled, np.where(x["model_side"] == "over", ADVERSE_OVER_Z, 0.0), x["z_main"])
    side_ok = x["model_side"].notna()
    push = x["actual"] == x["line_D"]
    win = np.where(x["model_side"] == "over", x["actual"] > x["line_D"], x["actual"] < x["line_D"]).astype(float)
    played = x["final"].fillna(False).astype(bool) & x["actual"].notna()
    settled_board = base & (x["status"] == "settled") & ~push & x["actual"].notna()
    x["hit_main"] = np.where(settled_board & side_ok, win, np.nan)
    x["hit_adverse"] = np.where(pulled & played & side_ok & ~push, win, x["hit_main"])
    x["hit_under"] = np.where(settled_board, (x["actual"] < x["line_D"]).astype(float), np.nan)
    real = (~x["price_assumed"].astype(bool)) & (~x["price_assumed_C"].fillna(True).astype(bool))
    x["real_prices"] = real
    F = lambda L: np.array([np.interp(l, qi, QLEV, left=0.0, right=1.0) if np.isfinite(l) else np.nan
                            for qi, l in zip(q, L)])
    pnv = np.asarray(no_vig_over(x["over_price_C"].astype(float), x["under_price_C"].astype(float)), dtype=float)
    p_over_D_close = np.clip(pnv + F(x["line_C"].values) - F(x["line_D"].values), 0.001, 0.999)
    over = (x["model_side"] == "over").values
    x["q_side_close"] = np.where(over, p_over_D_close, 1 - p_over_D_close)
    x["be_D_side"] = 1 / american_to_decimal(np.where(over, x["over_price"], x["under_price"]).astype(float))
    return x


def mark_strong_lean(t: pd.DataFrame, hit_col: str = "hit_main") -> pd.Series:
    """Within each week, flag the top STRONG_LEAN_FRAC of candidate lines by abs_lean.
    Candidates = rows with a finite abs_lean and a non-null hit_col (so main and adverse can differ when pulled
    lines enter the adverse board). Ties at the cutoff are included (>= week quantile)."""
    out = pd.Series(False, index=t.index)
    weeks = t["week"] if "week" in t.columns else pd.Series(0, index=t.index)
    for w, sub in t.groupby(weeks, sort=False):
        ok = sub[hit_col].notna() & sub["abs_lean"].notna()
        if int(ok.sum()) == 0:
            continue
        cut = float(sub.loc[ok, "abs_lean"].quantile(1.0 - STRONG_LEAN_FRAC))
        pick = ok & (sub["abs_lean"] >= cut)
        out.loc[sub.index[pick.to_numpy()]] = True
    return out


def side_counts(t: pd.DataFrame) -> dict:
    """Over/under counts and shares in the top-20% group (reported; no pass/fail floor)."""
    s = t["model_side"].dropna()
    n = int(len(s))
    if n == 0:
        return {"n": 0, "n_over": 0, "n_under": 0, "share_over": None, "share_under": None}
    no, nu = int((s == "over").sum()), int((s == "under").sum())
    return {"n": n, "n_over": no, "n_under": nu, "share_over": no / n, "share_under": nu / n}


def matched_control(strong: pd.DataFrame, board: pd.DataFrame, hit_col: str) -> dict:
    """Matched control vs blanket side rate PER MARKET (Tester1 fix): on all scored lines (pushes excluded),
    under_share(market) = share with actual < line_D; over_share = 1 - under_share. Do NOT group by model_side
    (that would compare strong leans to the model's weaker leans on the same side). Each strong-lean line gets
    Δ = hit - blanket_rate(market, side); pass if game-clustered 95% LB on mean(Δ) > 0."""
    empty = {"n_strong": 0, "n_board": 0, "strong_lean_hit_rate": None, "matched_control_hit_rate": None,
             "diff": None, "ci95_game_clustered": None, "pass": False, "market_side_rates": {}}
    if len(strong) == 0 or hit_col not in strong.columns or "market" not in strong.columns:
        return {**empty, "n_board": int(len(board))}
    need = board["actual"].notna() & board["line_D"].notna() & board["market"].notna()
    b = board.loc[need].copy()
    b = b[b["actual"] != b["line_D"]]
    s = strong[strong[hit_col].notna() & strong["model_side"].notna() & strong["market"].notna()].copy()
    if len(s) == 0 or len(b) == 0:
        return {**empty, "n_strong": int(len(s)), "n_board": int(len(b))}
    b["_under"] = (b["actual"].astype(float) < b["line_D"].astype(float)).astype(float)
    under_by_mkt = b.groupby(b["market"].astype(str), sort=False)["_under"].mean()
    mkt = s["market"].astype(str).to_numpy()
    side = s["model_side"].astype(str).to_numpy()
    mu = np.empty(len(s), dtype=float)
    for i, (m, side_i) in enumerate(zip(mkt, side)):
        if m not in under_by_mkt.index or side_i not in ("over", "under"):
            mu[i] = np.nan
        else:
            u = float(under_by_mkt[m])
            mu[i] = u if side_i == "under" else 1.0 - u
    hit = s[hit_col].to_numpy(dtype=float)
    ok = np.isfinite(mu)
    rates = {f"{m}|under": float(u) for m, u in under_by_mkt.items()}
    rates.update({f"{m}|over": float(1.0 - u) for m, u in under_by_mkt.items()})
    if not ok.any():
        return {"n_strong": int(len(s)), "n_board": int(len(b)), "strong_lean_hit_rate": float(hit.mean()),
                "matched_control_hit_rate": None, "diff": None, "ci95_game_clustered": None, "pass": False,
                "market_side_rates": rates}
    delta = hit[ok] - mu[ok]
    games = s["game_id"].to_numpy()[ok]
    boot = cluster_boot(delta, games)
    lo, hi = float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))
    matched = float(mu[ok].mean())
    strong_hr = float(hit[ok].mean())
    return {"n_strong": int(ok.sum()), "n_board": int(len(b)),
            "strong_lean_hit_rate": strong_hr, "matched_control_hit_rate": matched,
            "diff": strong_hr - matched, "ci95_game_clustered": (lo, hi),
            "pass": bool(lo > 0.0),
            "market_side_rates": rates,
            "side_counts": side_counts(s)}


def evaluate(t: pd.DataFrame) -> dict:
    """Pre-registered decision on a set of tracked lines (one week, or weeks 5-18 pooled for the final analysis).
    Main: (1) signal check: mean z-CLV (D->C, non-void in-scope lines) > 0 with one-sided game-clustered p < 0.05;
    (2) raw-model LL gain vs ln(2) at line_C: 95% CI upper bound >= 0; (3) break-even: with prices (>= 80% of scored
    lines with captured non-flat prices at D and C) the price rule, otherwise the PRIMARY without-prices bar =
    hit rate of the model side at line_D on each week's TOP 20% of lines by abs_lean = |mu - line_D|/sd
    (pooled across weeks after within-week selection) >= 53.5% with game-clustered 95% lower bound > 50%, AND the
    matched control vs blanket per-market side rates (strong-lean beats under/over share of actuals in that market;
    game-clustered 95% LB on mean Δ > 0). PROVISIONAL only when every skill bar passes but prices are missing.
    Full-board hit rate (53.5% / LB>50%) is DIAGNOSTIC only. Blanket-unders is reported as its own scored result and
    does NOT void the model's PASS. Adverse case: same rule on the adverse top-20% board."""
    t = t.copy()
    if "abs_lean" not in t.columns:
        sd = t["sd"].replace(0, np.nan)
        t["abs_lean"] = (t["mu"] - t["line_D"]).abs() / sd
    zm, za = t[t["z_main"].notna()], t[t["z_adverse"].notna()]
    ll = t[t["ll_gain_C"].notna() & t["z_main"].notna()]
    sig_m, sig_a = mean_test(zm["z_main"], zm["game_id"]), mean_test(za["z_adverse"], za["game_id"])
    llr = mean_test(ll["ll_gain_C"], ll["game_id"])
    ll_ok = llr["ci95_game_clustered"] is not None and llr["ci95_game_clustered"][1] >= 0
    scored = t[t["z_main"].notna() & (t["status"] == "settled")]
    real = scored["real_prices"].astype(bool) if len(scored) else pd.Series(dtype=bool)
    flat = scored.loc[real, ["over_price", "under_price"]].drop_duplicates().shape[0] <= 1 if len(scored) else True
    with_prices = bool(len(scored) and real.mean() >= 0.8 and not flat)
    strong_m = mark_strong_lean(t, "hit_main")
    strong_a = mark_strong_lean(t, "hit_adverse")
    hm = t[strong_m & t["hit_main"].notna()]
    ha = t[strong_a & t["hit_adverse"].notna()]
    scored_board = t[t["hit_under"].notna()]   # all scored lines, pushes out; baseline ignores model_side
    match_m = matched_control(hm, scored_board, "hit_main")
    match_a = matched_control(ha, scored_board, "hit_adverse")
    counts_m, counts_a = side_counts(hm), side_counts(ha)
    hu = t[t["hit_under"].notna()]
    blanket = {"rule": "blanket unders (always under at line_D, full board; reported only, does not void PASS)",
               **hit_test(hu["hit_under"], hu["game_id"], bar=BE_HIT_STRONG)}
    full = t[t["hit_main"].notna()]
    full_diag = {"rule": "DIAGNOSTIC only: full-board model-side hit rate",
                 **hit_test(full["hit_main"], full["game_id"], bar=BE_HIT_FULL)}
    if with_prices:
        p = scored[real]
        lo = float(np.percentile(cluster_boot(p["q_side_close"], p["game_id"]), 2.5))
        be = {"rule": "with prices", "n": int(len(p)), "mean_q_side": float(p["q_side_close"].mean()),
              "break_even_bar": float(p["be_D_side"].mean()), "lower95": lo,
              "pass": bool(p["q_side_close"].mean() >= p["be_D_side"].mean() and lo > 0.5)}
        be_m = be_a = be
    else:
        hit_m = hit_test(hm["hit_main"], hm["game_id"], bar=BE_HIT_STRONG)
        hit_a = hit_test(ha["hit_adverse"], ha["game_id"], bar=BE_HIT_STRONG)
        be_m = {"rule": "without prices: top-20% |lean| hit rate at line_D", **hit_m,
                "side_counts": counts_m, "n_strong_lean": int(len(hm)),
                "matched_control": match_m,
                "pass": bool(hit_m["pass"] and match_m["pass"]),
                "hit_rate_pass": bool(hit_m["pass"]), "matched_control_pass": bool(match_m["pass"])}
        be_a = {"rule": "without prices: top-20% |lean| hit rate at line_D (adverse)", **hit_a,
                "side_counts": counts_a, "n_strong_lean": int(len(ha)),
                "matched_control": match_a,
                "pass": bool(hit_a["pass"] and match_a["pass"]),
                "hit_rate_pass": bool(hit_a["pass"]), "matched_control_pass": bool(match_a["pass"])}
    ok = lambda sig, be: bool(sig["mean"] is not None and sig["mean"] > 0 and sig["p_one_sided_gt0"] < 0.05
                              and ll_ok and be["pass"])
    main_ok, adv_ok = ok(sig_m, be_m), ok(sig_a, be_a)
    label = "FAIL"
    if main_ok:
        notes = [] if with_prices else ["no prices"]
        if not adv_ok:
            notes.append("fails adverse-case sensitivity")
        label = "PASS" if not notes else "PROVISIONAL (" + "; ".join(notes) + ")"
    fail_rule = sig_m["mean"] is not None and (sig_m["mean"] <= 0 or sig_m["ci95_game_clustered"][1] < 0.01)
    pulled = t[t["in_scope"] & (t["void_reason"] == PULLED)]
    return {"label": label, "main_passes": main_ok, "adverse_passes": adv_ok, "failure_rule_triggered": bool(fail_rule),
            "signal_z_clv_main": sig_m, "signal_z_clv_adverse": sig_a, "ll_gain_vs_ln2_at_C": llr,
            "ll_criterion_ok": ll_ok, "break_even_main": be_m, "break_even_adverse": be_a,
            "blanket_unders": blanket, "hit_rate_full_board_diagnostic": full_diag,
            "pulled_in_scope": {"over": int((pulled["model_side"] == "over").sum()),
                                "under": int((pulled["model_side"] == "under").sum())}}


def settle_bets(b: pd.DataFrame) -> pd.DataFrame:
    """DraftKings settlement of diagnostic bets placed at D. Non-void settled line -> settled. Void for a book-stands
    reason (pulled_before_close, no C capture, duplicate at C) -> settled on the actual stat if the player recorded a
    snap or any stat (game final), refunded if he did not play. Inactive/DNP -> refunded. Otherwise pending."""
    b = b.copy()
    final = b["final"].fillna(False).astype(bool)
    played = b["actual"].notna()
    stands = b["void_reason"].isin(BOOK_STANDS)
    settled = final & played & (~b["void"] | stands)
    refunded = final & ~played & (~b["void"] | stands | (b["void_reason"] == INACTIVE))
    refunded |= b["void"] & (b["void_reason"] == INACTIVE)
    b["bet_status"] = np.where(settled, "settled", np.where(refunded, "refunded", "pending"))
    b["flat_profit"] = np.where(settled, b["flat_profit"], np.where(refunded, 0.0, np.nan))
    return b


def _corr(t: pd.DataFrame) -> float | None:
    """Correlation between logit(P_model(over | line_D)) and the standardized line move (pre-registered secondary)."""
    if len(t) < 3:
        return None
    p = t["p_over_model"].clip(1e-4, 1 - 1e-4)
    return float(np.corrcoef(np.log(p / (1 - p)), (t["line_C"] - t["line_D"]) / t["sd"])[0, 1])


def break_even_with_prices(t: pd.DataFrame, q: np.ndarray, min_share: float = 0.8) -> dict:
    """Pre-registered price rule (applies only when real prices exist). Eligible if >= min_share of scored lines have
    captured (not assumed) prices at BOTH D and C and the D prices are not one flat pair on every line.
    q_side = no-vig closing probability of the model's side at line_D: no-vig P(over line_C) at C, shifted to line_D
    with the champion predictive CDF, P(Y > line_D) = P(Y > line_C) + F(line_C) - F(line_D). Bar: mean q_side >=
    mean break-even of the captured D price on the model's side, AND the lower 95% game-clustered bound > 0.500."""
    if len(t) == 0:
        return {"eligible": False, "reason": "no scored lines"}
    real = (~t["price_assumed"].astype(bool)) & (~t["price_assumed_C"].fillna(True).astype(bool))
    share = float(real.mean())
    flat = t.loc[real, ["over_price", "under_price"]].drop_duplicates().shape[0] <= 1
    if share < min_share or flat:
        return {"eligible": False, "share_lines_with_real_prices_D_and_C": share, "flat_prices": bool(flat),
                "reason": "prices absent, flat, or < 80% coverage: the provisional without-prices bar applies"}
    t, qq = t[real], q[real.values]
    F = lambda L: np.array([np.interp(l, qi, QLEV, left=0.0, right=1.0) for qi, l in zip(qq, L)])
    p_over_D_close = (np.asarray(no_vig_over(t["over_price_C"], t["under_price_C"]), dtype=float)
                      + F(t["line_C"].values) - F(t["line_D"].values)).clip(0.001, 0.999)
    over = (t["p_over_model"] > 0.5).values
    q_side = np.where(over, p_over_D_close, 1 - p_over_D_close)
    be = 1 / american_to_decimal(np.where(over, t["over_price"], t["under_price"]).astype(float))
    lo, hi = cluster_ci(q_side, t["game_id"].values)
    return {"eligible": True, "share_lines_with_real_prices_D_and_C": share, "n": int(len(t)),
            "mean_q_side": float(q_side.mean()), "ci95_game_clustered": (lo, hi), "break_even_bar": float(be.mean()),
            "pass": bool(q_side.mean() >= be.mean() and lo > 0.5)}


def actuals(d: dict, season: int, wk: int) -> pd.DataFrame:
    """Actual yards per (player, game) for players who recorded a stat OR an offensive snap (0-yard games kept).
    A player with neither for a completed game is treated as inactive / DNP."""
    from .features import assemble_player_games
    pg = assemble_player_games(d)
    pg = pg[(pg["season"] == season) & (pg["week"] == wk)]
    a = pg.melt(id_vars=["player_id", "game_id"], value_vars=list(STAT.values()), var_name="stat", value_name="actual")
    a["market"] = a["stat"].map({v: k for k, v in STAT.items()})
    return a[["player_id", "game_id", "market", "actual"]]


def week(season: int, wk: int, cfg: dict) -> dict:
    """Score one week starting from EVERY line in the decision snapshot D (never from who later played).

    Each D line ends up either scored or VOID with a reason, written to data/track/<S>_wkWW_voids.csv:
      * carried from pregame: no matching player row (no GSIS match / event not in schedule / no prior data /
        player's last team not in the game)
      * no pregame prediction file created before that game's kickoff
      * pulled_before_close: the game has a C capture (the LAST capture before kickoff) but the line is missing
        from it (never filled from an earlier capture); reported separately, not in the data kill rule
      * no closing snapshot C: no valid capture in the 30 min before kickoff (capture failure; kill rule)
      * player inactive / DNP: completed game and no stat row and no offensive snap
    Lines whose game is not final yet are PENDING (not void). Primary metric reported voids-excluded and
    voids-as-zero."""
    from .data import load
    Dp = DATA / "lines" / f"snap_{season}_wk{wk}_D.csv"
    if not Dp.exists():
        raise SystemExit(f"no decision snapshot {Dp}: run nflprops.snapshot (>=3h before kickoff) and snaplines")
    D = pd.read_csv(Dp, dtype={"player_id": str, "event_id": str, "espn_id": str})
    Cp = DATA / "lines" / f"snap_{season}_wk{wk}_C.csv"
    C = pd.read_csv(Cp, dtype={"player_id": str, "event_id": str, "espn_id": str}) if Cp.exists() else D.iloc[0:0]
    for t in (D, C):
        if "void_reason" not in t:
            t["void_reason"] = np.nan
    D = D.rename(columns={"void_reason": "d_void"})
    ckeys = ["espn_id", "event_id", "market"]
    c_dup = C.loc[C["void_reason"].notna(), ckeys].drop_duplicates().assign(c_dup=True)
    C = C[C["void_reason"].isna()]
    assert not C.duplicated(ckeys).any(), "non-void duplicate lines in the C file"
    d = load(cfg["data"]["first_season"], season, max_age_h=1e9)
    sch = d["schedules"]
    g = sch[(sch["season"] == season) & (sch["week"] == wk)][["game_id", "espn", "gameday", "gametime",
                                                                  "home_score"]].copy()
    g["espn"] = g["espn"].astype(str)
    g["kick"] = pd.to_datetime(g["gameday"] + " " + g["gametime"]).dt.tz_localize("America/New_York")
    if "kickoff_actual_utc" in D:              # actual kickoff = earliest of nflverse and the snapshots' earliest
        ka = pd.to_datetime(D.groupby("event_id")["kickoff_actual_utc"].min(), utc=True)
        g["kick"] = [min(k, ka[e]) if e in ka.index and pd.notna(k) else k for k, e in zip(g["kick"], g["espn"])]
    g["final"] = g["home_score"].notna()
    now = pd.Timestamp.now(tz="UTC")
    x = D.rename(columns={"line": "line_D"}).merge(g[["espn", "game_id", "kick", "final"]], left_on="event_id",
                                                   right_on="espn", how="left").drop(columns="espn")
    if "price_assumed" not in C:
        C["price_assumed"] = True
    x = x.merge(C[ckeys + ["line", "over_price", "under_price", "price_assumed"]].rename(
        columns={"line": "line_C", "over_price": "over_price_C", "under_price": "under_price_C",
                 "price_assumed": "price_assumed_C"}), on=ckeys, how="left")
    x = x.merge(c_dup, on=ckeys, how="left")
    x["c_dup"] = x["c_dup"].fillna(False).astype(bool)
    # pregame predictions: per game, the latest file created BEFORE kickoff; carry its void reasons
    parts, pvoid = [], []
    for m in sorted(glob.glob(str(DATA / "predictions" / f"{season}_wk{wk:02d}" / "pregame_*.meta.json"))):
        meta = json.loads(open(m).read())
        if not str(meta.get("mode", "")).startswith("snapshot"):
            continue                                   # dry-run (recent-appearance) files never feed tracking
        created = pd.Timestamp(meta["created_at_utc"])
        pr = pd.read_parquet(DATA.parent / meta["files"][0]).merge(g[["game_id", "kick"]], on="game_id")
        pr = pr[created < pr["kick"]].assign(created=created, pred_file=meta["files"][0],
                                             pred_sha256=meta["sha256_parquet"])
        parts.append(pr)
        if meta.get("void_report"):
            v = pd.read_csv(DATA.parent / meta["void_report"], dtype={"player_id": str, "event_id": str})
            v = v.merge(g[["espn", "kick"]], left_on="event_id", right_on="espn", how="left")
            pvoid.append(v[v["kick"].isna() | (created < v["kick"])].assign(created=created))
    keys = ["player_id", "game_id", "market"]
    if parts:
        P = pd.concat(parts).sort_values("created").groupby(keys).tail(1)
        x = x.merge(P[keys + QCOLS + ["mu", "median", "p_over_D", "line_D", "in_model_universe", "created",
                                      "pred_file", "pred_sha256"]].rename(columns={"line_D": "pred_line_D"}),
                    on=keys, how="left")
    else:
        x = x.assign(**{c: np.nan for c in QCOLS + ["mu", "median", "p_over_D", "pred_line_D", "in_model_universe",
                                                    "created", "pred_file", "pred_sha256"]})
    if pvoid:
        V = pd.concat(pvoid).sort_values("created").groupby(["event_id", "player_name", "market"]).tail(1)
        x = x.merge(V[["event_id", "player_name", "market", "void_reason"]].rename(columns={"void_reason": "pv"}),
                    on=["event_id", "player_name", "market"], how="left")
    else:
        x["pv"] = np.nan
    act = actuals(d, season, wk)
    x = x.merge(act, on=keys, how="left")
    if len(x) != len(D):                       # every D line exactly once: merges must never multiply/drop lines
        raise ValueError(f"track merge changed the line count: {len(D)} D lines -> {len(x)} rows")
    started = x["kick"].notna() & (x["kick"] <= now)
    reason = pd.Series(pd.NA, index=x.index, dtype="object")
    have_pred = x["q50"].notna()
    reason[x["d_void"].notna()] = x["d_void"]             # snapshot-level: kickoff_moved / duplicate_line
    reason[reason.isna() & ~have_pred & x["pv"].notna()] = x["pv"]
    reason[reason.isna() & ~have_pred] = "no pregame prediction file created before kickoff"
    reason[reason.isna() & x["c_dup"]] = "duplicate_line at C: more than one closing line for this player+market"
    # C comes ONLY from the last capture before kickoff (snaplines). Game has a C capture but the line is missing
    # from it -> pulled_before_close (never an earlier capture). No C capture for the game -> capture failure.
    has_c = x["event_id"].isin(C["event_id"].astype(str))
    reason[reason.isna() & started & has_c & x["line_C"].isna()] = PULLED
    reason[reason.isna() & started & ~has_c & x["line_C"].isna()] = NO_C
    reason[reason.isna() & x["final"].fillna(False) & x["actual"].isna()] = INACTIVE
    x["void"] = reason.notna()
    x["void_reason"] = reason
    pp = DATA / "lines" / f"snap_{season}_wk{wk}_pulled.csv"
    x["void_detail"] = None
    if pp.exists():
        pu = pd.read_csv(pp, dtype={"event_id": str, "espn_id": str})
        x = x.merge(pu[["event_id", "espn_id", "market", "last_seen_pt", "first_missing_pt"]],
                    on=["event_id", "espn_id", "market"], how="left")
        ix = (x["void_reason"] == PULLED) & x["last_seen_pt"].notna()
        x.loc[ix, "void_detail"] = ("pulled between " + x.loc[ix, "last_seen_pt"] + " (last seen) and "
                                    + x.loc[ix, "first_missing_pt"].fillna("?") + " (first missing)")
    x["status"] = np.where(x["void"], "void", np.where(x["final"].fillna(False), "settled", "pending"))
    # model scope (pre-registered): min_proj 20 yds / projected-starter QB, from as-of features. Out-of-scope lines are
    # predicted and kept, but reported separately and excluded from the primary metric (never silently dropped).
    x["out_of_scope"] = ~x["void"] & have_pred & (x["in_model_universe"] == False)  # noqa: E712
    q = x[QCOLS].values
    # P_model(over | line_D): the champion's own prob_over stored by pregame; quantile interpolation as fallback
    same_line = x["pred_line_D"].notna() & np.isclose(x["pred_line_D"].fillna(-1e9), x["line_D"])
    x["p_over_model"] = x["p_over_D"].where(same_line & x["p_over_D"].notna(), pd.Series(p_over_from_q(q, x["line_D"].values),
                                                                               index=x.index))
    x["sd"] = (x["q84"] - x["q16"]) / 2
    x["z_clv"] = np.sign(x["p_over_model"] - 0.5) * (x["line_C"] - x["line_D"]) / x["sd"]
    # pre-registered success criterion (2): raw-model log loss at the CLOSING line vs ln(2), pushes excluded
    x["p_over_C_model"] = p_over_from_q(q, x["line_C"].values)
    pc = pd.Series(x["p_over_C_model"]).clip(1e-4, 1 - 1e-4).values
    okc = x["actual"].notna().values & x["line_C"].notna().values & (x["actual"] != x["line_C"]).values
    ll = np.where(x["actual"] > x["line_C"], -np.log(pc), -np.log(1 - pc))
    x["ll_gain_C"] = np.where(okc, np.log(2) - ll, np.nan)
    x = add_case_columns(x, q)
    x["line"] = x["line_D"]
    x["p_mkt_over"] = no_vig_over(x["over_price"], x["under_price"])
    x["over_hit"] = np.where(x["actual"].notna(), (x["actual"] > x["line"]).astype(float), np.nan)
    x["push"] = x["actual"] == x["line"]
    # stacked betting probability (history = 2025 real lines + earlier tracked, settled, non-void weeks)
    hist = history(cfg)
    prev = [pd.read_parquet(f) for f in sorted(glob.glob(str(TRACK / f"{season}_wk[0-9][0-9].parquet")))
            if int(f.split("_wk")[1][:2]) < wk]
    if prev:
        hist = pd.concat([hist] + [p_[(p_["status"] == "settled") & p_["actual"].notna()] for p_ in prev],
                         ignore_index=True)
    x["p_over"] = np.nan
    x["logit_sd"] = np.nan
    co = pd.DataFrame()
    if have_pred.any():
        sub = x[have_pred]
        p_, lsd, co = hier_stacked_probs(sub, hist, cfg["betting"].get("stacker_prior"))
        x.loc[have_pred, "p_over"] = np.asarray(p_)
        x.loc[have_pred, "logit_sd"] = np.asarray(lsd)
    # bet track: decisions on every in-scope line with a prediction and a valid (non-void) D line
    bc = dict(cfg["betting"], **cfg.get("diagnostic_policy", {}))
    b = select_bets(x[have_pred & ~x["out_of_scope"] & x["d_void"].isna()], bc)
    b = settle_bets(b)
    st_ = b[b["bet_status"] == "settled"]
    paper = st_[~st_["void"]]
    roi = lambda t: float(t["flat_profit"].mean()) if len(t) else None
    bet_res = {"n_bets_decided": int(len(b)), "n_pending_bets": int((b["bet_status"] == "pending").sum()),
               "n_settled_on_void_line_dk_rules": int((st_["void"]).sum()),
               "n_refunded": int((b["bet_status"] == "refunded").sum()),
               "voids_excluded": {"n": int(len(st_)), "flat_roi": roi(st_),
                                  "note": "DraftKings settlement; refunds excluded"},
               "voids_as_zero": {"n": int(b["flat_profit"].notna().sum()),
                                 "flat_roi": float(b["flat_profit"].dropna().mean())
                                 if b["flat_profit"].notna().any() else None,
                                 "note": "refunds counted as 0 profit"},
               "paper_non_void_lines_only": {"n": int(len(paper)), "flat_roi": roi(paper)}}
    TRACK.mkdir(parents=True, exist_ok=True)
    out = TRACK / f"{season}_wk{wk:02d}.parquet"
    x.drop(columns=QCOLS).to_parquet(out, index=False)
    b.drop(columns=[c for c in QCOLS if c in b]).to_parquet(TRACK / f"{season}_wk{wk:02d}_bets.parquet", index=False)
    vf = TRACK / f"{season}_wk{wk:02d}_voids.csv"
    vr = x[x["void"]].assign(stage=lambda t: np.where(t["void_reason"].str.startswith("no player row"), "pregame",
                                                       "track"), line_D=lambda t: t["line_D"])
    vr.reindex(columns=VOID_COLS).to_csv(vf, index=False)
    x[x["out_of_scope"]].reindex(columns=["season", "week", "event_id", "game_id", "player_id", "player_name",
                                          "market", "line_D", "line_C", "mu", "status"]).to_csv(
        TRACK / f"{season}_wk{wk:02d}_out_of_scope.csv", index=False)
    known = (x["status"] != "pending").values
    zc = x[known]
    q_all = q[known]                     # primary metric over lines whose outcome is known
    s = {"season": season, "week": wk, "scored_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
         "universe": "every line in the decision snapshot D (>=3h before kickoff)", "n_lines_D": int(len(x)),
         "n_scored": int((x["status"] == "settled").sum()), "n_void": int(x["void"].sum()),
         "n_pending": int((x["status"] == "pending").sum()),
         "voids_by_reason": x.loc[x["void"], "void_reason"].value_counts().to_dict(),
         "voids_by_market": x.loc[x["void"], "market"].value_counts().to_dict(),
         "lines_by_market": x["market"].value_counts().to_dict(),
         "n_with_C": int(x["line_C"].notna().sum()),
         # data kill rule: capture failures only; pulled lines are reported separately and NOT counted
         "share_started_no_C_capture_failure": float((x["void_reason"] == NO_C).sum() / started.sum())
         if started.any() else None,
         "n_pulled_before_close": int((x["void_reason"] == PULLED).sum()),
         "n_pulled_before_close_by_model_side": {
             "over": int(((x["void_reason"] == PULLED) & (x["model_side"] == "over")).sum()),
             "under": int(((x["void_reason"] == PULLED) & (x["model_side"] == "under")).sum()),
             "no_prediction": int(((x["void_reason"] == PULLED) & x["model_side"].isna()).sum())},
         "share_started_pulled_before_close": float((x["void_reason"] == PULLED).sum() / started.sum())
         if started.any() else None,
         "n_out_of_model_scope": int(x["out_of_scope"].sum()),
         "out_of_scope_by_market": x.loc[x["out_of_scope"], "market"].value_counts().to_dict(),
         "corr_logit_p_model_vs_move": _corr(zc[zc["z_clv"].notna() & ~zc["void"] & ~zc["out_of_scope"]]),
         "z_clv": two_versions(zc[~zc["out_of_scope"]], "z_clv", zc.loc[~zc["out_of_scope"], "void"])
         if (~zc["out_of_scope"]).any() else None,
         "break_even_with_prices": (lambda m: break_even_with_prices(zc[m], q_all[m.values]))(
             ~zc["void"] & ~zc["out_of_scope"] & zc["line_C"].notna() & (zc["status"] == "settled")),
         "ll_gain_vs_ln2_at_C": (lambda t: {"n": int(len(t)), "mean": float(t["ll_gain_C"].mean()),
                                             "ci95_game_clustered": cluster_ci(t["ll_gain_C"].values,
                                                                               t["game_id"].values)}
                                 if len(t) else None)(
             zc[~zc["void"] & ~zc["out_of_scope"] & zc["ll_gain_C"].notna()]),
         "z_clv_incl_out_of_scope": two_versions(zc, "z_clv", zc["void"]) if len(zc) else None,
         "decision_this_week_only": evaluate(x),
         "bet_track": bet_res, "prices_assumed": bool(x["price_assumed"].any()),
         "stacker": co.iloc[-1].to_dict() if len(co) else {}, "file": str(out.relative_to(DATA.parent)),
         "void_report": str(vf.relative_to(DATA.parent)),
         "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
         "sha256_voids": hashlib.sha256(vf.read_bytes()).hexdigest()}
    (TRACK / f"{season}_wk{wk:02d}.summary.json").write_text(json.dumps(s, indent=1, default=str))
    return s


def final(season: int, first: int, last: int) -> dict:
    """Final analysis: pool every tracked week's lines (data/track/<S>_wkWW.parquet) and apply `evaluate`."""
    fs = [p for p in sorted(glob.glob(str(TRACK / f"{season}_wk[0-9][0-9].parquet")))
          if first <= int(p.split("_wk")[1][:2]) <= last]
    if not fs:
        raise SystemExit("no tracked weeks in range")
    t = pd.concat([pd.read_parquet(p) for p in fs], ignore_index=True)
    r = {"season": season, "weeks": [first, last], "weeks_found": [int(p.split("_wk")[1][:2]) for p in fs],
         "n_lines_D": int(len(t)), "n_void": int(t["void"].sum()),
         "voids_by_reason": t.loc[t["void"], "void_reason"].value_counts().to_dict(),
         "n_pulled_before_close": int((t["void_reason"] == PULLED).sum()),
         "z_clv_voids_as_zero": two_versions(t[t["status"] != "pending"].loc[lambda u: u["in_scope"] | u["void"]],
                                             "z_clv", t[t["status"] != "pending"].loc[
                                                 lambda u: u["in_scope"] | u["void"], "void"]),
         "decision": evaluate(t), "files": fs,
         "computed_at": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
    out = TRACK / f"{season}_final_wk{first:02d}-{last:02d}.json"
    out.write_text(json.dumps(r, indent=1, default=str))
    return r


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["stacker", "week", "final"])
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", type=int)
    ap.add_argument("--weeks", default="5-18", help="final: week range")
    a = ap.parse_args()
    cfg = champion_cfg()[0]
    from .config import load_config
    cfg = deep_update(cfg, {"betting": load_config()["betting"], "diagnostic_policy": load_config()["diagnostic_policy"]})
    if a.cmd == "stacker":
        r = fit_stacker_now(cfg)
        (EXPERIMENTS / "stacker_2026_start.json").write_text(json.dumps(r, indent=1, default=float))
        print(json.dumps(r, indent=1, default=float))
    elif a.cmd == "final":
        w0, w1 = (int(v) for v in a.weeks.split("-"))
        print(json.dumps(final(a.season, w0, w1), indent=1, default=str))
    else:
        print(json.dumps(week(a.season, a.week, cfg), indent=1, default=str))
