"""Grade NHL SOG majority-list sides (agrees_n >= 4 of 7).

Each window or line-capture pass is read from the frozen build_sheet workbook
(sheets/<YYYYMMDD>_D_<HHMM>_picks.xlsx), which is the scored evidence posted
to the room. D / GATE CSVs supply nhl_id and gameId. Text room posts are not
parsed, so an incomplete majority note cannot drop a side that was on the sheet.

Sides are deduped by (date, game, player, side, line). The earliest pass keeps
its posted price and list id; every pass the side appeared on is recorded in
appeared_on.

Shots come from the same sources as the existing graders: graded/<date>.csv
(from grade.py's NHL stats API pull), shadow/s2026_live.pkl (shadow/gamelog.py),
then a live NHL API pull for dates those files do not yet cover. Only finished
games are graded.

Price is the actual posted Fliff price when fliff_prices captured an offer for
that side on the earliest list, otherwise the DK list price. Shop-at and later
re-pulls are never used. Missing prices still get a win-loss, with profit n/a.

Usage:  python3 majority/grade_majority.py
        python3 majority/grade_majority.py 20261105 20261109

Writes majority/graded_sides.csv idempotently (re-runs do not duplicate; pending
rows are updated when a game finishes). Paper only: no bets, no Fliff/Odds
credits, no edits to frozen model files, picks/, or sheets/.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
import time
import urllib.request
from datetime import date, datetime
from urllib.error import URLError, HTTPError

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
os.chdir(ROOT)

FROM_DATE = date(2026, 11, 5)  # first day 4-of-7 majority lists were posted
OUT = os.path.join(HERE, "graded_sides.csv")
UA = {"User-Agent": "Mozilla/5.0"}

SHEET_RE = re.compile(r"^(\d{8})_D_(\d{4})_picks\.xlsx$")
D_RE = re.compile(r"^(\d{8})_D_(\d{4})\.csv$")
DAY_D_RE = re.compile(r"^(\d{8})_D\.csv$")

# Columns written to graded_sides.csv (stable order for diffs / re-runs).
COLS = [
    "date", "list_id", "appeared_on", "game", "gameId", "nhl_id", "player",
    "side", "line", "agrees_n", "dk_price", "fliff_price", "fliff_status",
    "price", "price_source", "in_band", "actual", "game_finished", "result",
    "units",
]

FINAL_STATES = {"OFF", "FINAL", "FINAL_OT", "FINAL_SO"}


def ymd(d: date | str) -> str:
    if isinstance(d, date):
        return d.strftime("%Y%m%d")
    return str(d)


def iso(d: str) -> str:
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def am2dec(a) -> float:
    a = float(a)
    return 1 + (a / 100.0 if a > 0 else 100.0 / -a)


def parse_american(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return np.nan
    s = str(v).strip().replace("+", "")
    if s == "" or s.lower() in {"nan", "none", "n/a"}:
        return np.nan
    try:
        return int(float(s))
    except ValueError:
        return np.nan


def key_of(row) -> tuple:
    game = str(row["game"]).strip()
    # Prefer NHL gameId when present so a naming typo cannot split a side.
    gid = row.get("gameId", np.nan)
    if pd.notna(gid):
        game = f"id:{int(gid)}"
    return (
        str(row["date"]),
        game,
        str(row["player"]).strip(),
        str(row["side"]).strip().upper(),
        float(row["line"]),
    )


def dates_in_range(args) -> list[str]:
    if args:
        return [ymd(a) for a in args]
    today = date.today()
    out = []
    d = FROM_DATE
    while d <= today:
        out.append(ymd(d))
        d = date.fromordinal(d.toordinal() + 1)
    return out


# ---- pass discovery -------------------------------------------------------

def discover_passes(dates: list[str]) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Return ([(date, hhmm, sheet_or_empty)], skipped_dates).

    A date is skipped when it has no D-window scored file and no sheet.
    The 9:12 Nov 9 line-capture (no D, no sheet) is not a skipped date if
    later passes that day have scored files.
    """
    passes = []
    skipped = []
    for d in dates:
        stamps = {}
        for f in glob.glob(os.path.join("sheets", f"{d}_D_*_picks.xlsx")):
            m = SHEET_RE.match(os.path.basename(f))
            if m:
                stamps[m.group(2)] = f
        d_stamps = set()
        for f in glob.glob(os.path.join("picks", f"{d}_D_*.csv")):
            m = D_RE.match(os.path.basename(f))
            if m:
                d_stamps.add(m.group(2))
        has_day_d = os.path.exists(os.path.join("picks", f"{d}_D.csv"))
        for hhmm in d_stamps:
            stamps.setdefault(hhmm, "")
        if not stamps and not has_day_d:
            skipped.append(d)
            continue
        for hhmm in sorted(stamps):
            passes.append((d, hhmm, stamps[hhmm]))
    return passes, skipped


def load_d_index(day: str) -> pd.DataFrame:
    """Union of that day's D CSVs, for nhl_id / gameId / DK prices."""
    files = []
    for f in glob.glob(os.path.join("picks", f"{day}_D*.csv")):
        base = os.path.basename(f)
        if "GATE" in base or "recent" in base or "verify" in base:
            continue
        files.append(f)
    if not files:
        return pd.DataFrame()
    frames = []
    for f in files:
        df = pd.read_csv(f)
        keep = [c for c in ("player", "nhl_id", "gameId", "game", "line", "over", "under", "event") if c in df.columns]
        frames.append(df[keep])
    out = pd.concat(frames, ignore_index=True)
    out["line"] = out["line"].astype(float)
    out["player"] = out["player"].astype(str).str.strip()
    if "game" in out.columns:
        out["game"] = out["game"].astype(str).str.strip()
    subset = [c for c in ("player", "line", "game") if c in out.columns]
    return out.drop_duplicates(subset)


def load_fliff(day: str) -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join("fliff_prices", f"{day}_*.csv")))
    if not files:
        return pd.DataFrame()
    F = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    F["line"] = F["line"].astype(float)
    F["side"] = F["side"].astype(str).str.upper()
    F["player_key"] = F["player"].astype(str).str.strip()
    return F


def fliff_for(F: pd.DataFrame, list_id: str, player: str, side: str, line: float):
    """Return (price, status) from the capture tied to this list, if any."""
    empty = (np.nan, "")
    if F is None or F.empty:
        return empty
    side = side.upper()
    player = str(player).strip()
    cand = F[(F.player_key == player) & (F.side == side) & (np.isclose(F.line, float(line)))]
    if cand.empty:
        return empty
    # Prefer the row whose list_file points at this pass (e.g. 20261109_1537_post.txt).
    if "list_file" in cand.columns:
        tied = cand[cand.list_file.astype(str).str.replace("_D_", "_", regex=False).str.startswith(list_id)]
        if len(tied):
            cand = tied
    row = cand.iloc[-1]
    status = str(row.get("fliff_status") or "")
    price = parse_american(row.get("fliff_price"))
    offered = status.strip().lower() == "offered" and pd.notna(price)
    if offered:
        # Only accept an offer at the listed line.
        fline = row.get("fliff_line")
        if pd.notna(fline) and not np.isclose(float(fline), float(line)):
            return (np.nan, f"offered_different_line_{fline}")
        return (int(price), "offered")
    return (np.nan, status)


def price_side(dk, fliff_price, fliff_status):
    """Fliff if offered, else DK. Never invent a price."""
    if fliff_status == "offered" and pd.notna(fliff_price):
        p = int(fliff_price)
        return p, "fliff"
    dk = parse_american(dk)
    if pd.notna(dk):
        return int(dk), "dk"
    return np.nan, "none"


def in_band(price) -> "pd._libs.missing.NAType | bool":
    """Outside the band only when the posted price is worse than -150."""
    if pd.isna(price):
        return pd.NA
    return int(price) >= -150


# ---- collect majority sides ----------------------------------------------

def sides_from_sheet(path: str, day: str, hhmm: str, d_index: pd.DataFrame, F: pd.DataFrame) -> pd.DataFrame:
    df = pd.read_excel(path)
    if "agrees_n" not in df.columns:
        return pd.DataFrame()
    df = df[df.agrees_n.notna() & (df.agrees_n >= 4)].copy()
    if df.empty:
        return df
    df["date"] = day
    df["list_id"] = f"{day}_{hhmm}"
    df["side"] = df["side"].astype(str).str.upper()
    df["line"] = df["line"].astype(float)
    df["player"] = df["player"].astype(str).str.strip()
    df["agrees_n"] = df["agrees_n"].astype(int)

    # Attach nhl_id / gameId from the D files (sheet does not store them).
    if d_index is not None and not d_index.empty:
        idx = d_index.copy()
        if "game" in idx.columns and "game" in df.columns:
            merged = df.merge(idx, on=["player", "line", "game"], how="left", suffixes=("", "_d"))
        else:
            merged = df.merge(idx, on=["player", "line"], how="left", suffixes=("", "_d"))
        miss = merged["nhl_id"].isna() if "nhl_id" in merged.columns else pd.Series(True, index=merged.index)
        if miss.any():
            fallback = df.merge(idx.drop(columns=[c for c in ("game",) if c in idx.columns]),
                                on=["player", "line"], how="left", suffixes=("", "_d"))
            for c in ("nhl_id", "gameId"):
                if c in fallback.columns:
                    merged.loc[miss, c] = fallback.loc[miss, c].values
        df = merged

    rows = []
    for _, r in df.iterrows():
        fprice, fstatus = fliff_for(F, r["list_id"], r["player"], r["side"], r["line"])
        price, src = price_side(r.get("dk_price"), fprice, fstatus)
        rows.append({
            "date": day,
            "list_id": r["list_id"],
            "appeared_on": r["list_id"],
            "game": str(r["game"]).strip(),
            "gameId": int(r["gameId"]) if pd.notna(r.get("gameId")) else np.nan,
            "nhl_id": int(r["nhl_id"]) if pd.notna(r.get("nhl_id")) else np.nan,
            "player": r["player"],
            "side": r["side"],
            "line": float(r["line"]),
            "agrees_n": int(r["agrees_n"]),
            "dk_price": parse_american(r.get("dk_price")),
            "fliff_price": fprice if pd.notna(fprice) else np.nan,
            "fliff_status": fstatus,
            "price": price if pd.notna(price) else np.nan,
            "price_source": src,
            "in_band": in_band(price),
        })
    return pd.DataFrame(rows)


def collect(dates: list[str]) -> tuple[pd.DataFrame, list[str], list[tuple[str, str, str]]]:
    passes, skipped = discover_passes(dates)
    chunks = []
    for day, hhmm, sheet in passes:
        if not sheet:
            # A D file with no sheet is not reconstructed here: agrees_n was
            # frozen on the sheet at list time, and re-scoring could drift.
            continue
        d_index = load_d_index(day)
        F = load_fliff(day)
        part = sides_from_sheet(sheet, day, hhmm, d_index, F)
        if part is not None and not part.empty:
            chunks.append(part)
    if not chunks:
        return pd.DataFrame(columns=COLS), skipped, passes
    all_sides = pd.concat(chunks, ignore_index=True)

    # Dedupe: earliest list keeps price + list_id; record every pass it appeared on.
    all_sides["_ord"] = all_sides["list_id"]
    all_sides = all_sides.sort_values(["date", "list_id"]).reset_index(drop=True)
    keys = all_sides.apply(key_of, axis=1)
    all_sides["_k"] = keys
    appeared = all_sides.groupby("_k", sort=False)["list_id"].agg(lambda s: ",".join(dict.fromkeys(s)))
    first = all_sides.drop_duplicates("_k", keep="first").copy()
    first["appeared_on"] = first["_k"].map(appeared)
    first = first.drop(columns=["_ord", "_k"])
    return first, skipped, passes


# ---- shots / game state ---------------------------------------------------

def get_json(url: str, retries: int = 3):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except (URLError, HTTPError, TimeoutError, json.JSONDecodeError) as e:
            last = e
            time.sleep(2 + i)
    raise RuntimeError(f"GET {url} failed: {last}")


def load_local_shots() -> tuple[dict, dict, set]:
    """shots[(nhl_id, gameId)] = actual; dates covered by a local source; gameIds seen."""
    shots = {}
    covered_dates = set()
    games = set()
    for f in glob.glob("graded/20*.csv"):
        base = os.path.basename(f)
        if not re.match(r"^20\d{6}\.csv$", base):
            continue
        g = pd.read_csv(f)
        if "actual" not in g.columns:
            continue
        covered_dates.add(base[:8])
        for _, r in g.iterrows():
            if pd.isna(r.get("nhl_id")) or pd.isna(r.get("gameId")):
                continue
            k = (int(r.nhl_id), int(r.gameId))
            games.add(int(r.gameId))
            if pd.notna(r.actual):
                shots[k] = int(r.actual)
    pkl = os.path.join("shadow", "s2026_live.pkl")
    if os.path.exists(pkl):
        logs = pd.read_pickle(pkl)
        for _, r in logs.iterrows():
            k = (int(r.playerId), int(r.gameId))
            games.add(int(r.gameId))
            if k not in shots and pd.notna(r.shots):
                shots[k] = int(r.shots)
            if pd.notna(r.get("gameDate")):
                gd = str(r.gameDate).replace("-", "")[:8]
                covered_dates.add(gd)
    return shots, covered_dates, games


def fetch_day_results(day: str) -> tuple[dict, dict]:
    """Live NHL pull (same family of endpoints as grade.py / three_records.py).

    Returns shots[(nhl_id, gameId)] and finished[gameId] = bool.
    In-progress games are marked not finished and their shots are ignored.
    """
    shots, finished = {}, {}
    try:
        score = get_json(f"https://api-web.nhle.com/v1/score/{iso(day)}")
    except Exception as e:
        print(f"warning: score API failed for {day}: {e}", file=sys.stderr)
        return shots, finished
    for g in score.get("games") or []:
        gid = int(g["id"])
        state = str(g.get("gameState") or "")
        finished[gid] = state in FINAL_STATES or state.startswith("FINAL")
        if not finished[gid]:
            continue
        try:
            box = get_json(f"https://api-web.nhle.com/v1/gamecenter/{gid}/boxscore")
        except Exception as e:
            print(f"warning: boxscore failed for {gid}: {e}", file=sys.stderr)
            continue
        # Confirm the box itself is final before accepting shots.
        bstate = str(box.get("gameState") or state)
        if not (bstate in FINAL_STATES or bstate.startswith("FINAL")):
            finished[gid] = False
            continue
        pbg = box.get("playerByGameStats") or {}
        for t in ("awayTeam", "homeTeam"):
            team = pbg.get(t) or {}
            for grp in ("forwards", "defense"):
                for p in team.get(grp) or []:
                    pid = p.get("playerId")
                    sog = p.get("sog")
                    if pid is not None and sog is not None:
                        shots[(int(pid), gid)] = int(sog)
    # Fill any holes from the stats summary endpoint grade.py uses, but only
    # for games already marked finished.
    try:
        data = get_json(
            "https://api.nhle.com/stats/rest/en/skater/summary?"
            "isAggregate=false&isGame=true&limit=-1&"
            f"cayenneExp=gameDate=\"{iso(day)}\"%20and%20gameTypeId=2"
        ).get("data") or []
        have = {gid for gid in finished if finished[gid]}
        for x in data:
            gid = int(x["gameId"])
            if gid not in have:
                continue
            k = (int(x["playerId"]), gid)
            if k not in shots and x.get("shots") is not None:
                shots[k] = int(x["shots"])
    except Exception as e:
        print(f"warning: stats API failed for {day}: {e}", file=sys.stderr)
    return shots, finished


def grade_rows(sides: pd.DataFrame) -> pd.DataFrame:
    if sides.empty:
        sides = sides.copy()
        for c in ("actual", "game_finished", "result", "units"):
            if c not in sides:
                sides[c] = pd.NA
        return sides

    local_shots, local_dates, local_games = load_local_shots()
    # Fetch any date that is not fully covered locally, plus today (games may
    # still be finishing). Finished flags always come from the live score API
    # for dates we fetch, so we do not mark an in-progress game as graded
    # from a partial box.
    need = sorted(set(sides["date"].astype(str)))
    live_shots, live_finished = {}, {}
    today = ymd(date.today())
    for d in need:
        if d < today and d in local_dates:
            # Still need finished flags? Historical days with a graded CSV or
            # a game log through that date are complete. Skip the live pull.
            continue
        s, f = fetch_day_results(d)
        live_shots.update(s)
        live_finished.update(f)

    # Historical dates already in graded/ or the live game log are treated
    # as finished (those files are written after the night's games end).
    hist_finished = {d for d in need if d < today and d in local_dates}

    out = sides.copy()
    actuals, finished_flag, results, units = [], [], [], []
    for _, r in out.iterrows():
        gid = int(r["gameId"]) if pd.notna(r.get("gameId")) else None
        nid = int(r["nhl_id"]) if pd.notna(r.get("nhl_id")) else None
        day = str(r["date"])

        is_fin = None
        if gid is not None and gid in live_finished:
            is_fin = bool(live_finished[gid])
        elif day in hist_finished and gid is not None and gid in local_games:
            is_fin = True
        elif day in hist_finished and nid is not None:
            # gameId missing but we have local shots for this date — still
            # require a concrete game match; leave pending if we cannot.
            # Game not in local shot files: leave pending, never void as DNP.
            is_fin = False
        else:
            is_fin = False

        sog = None
        if is_fin and nid is not None and gid is not None:
            if (nid, gid) in live_shots:
                sog = live_shots[(nid, gid)]
            elif (nid, gid) in local_shots:
                sog = local_shots[(nid, gid)]

        if not is_fin:
            actuals.append(np.nan)
            finished_flag.append(False)
            results.append("pending")
            units.append(np.nan)
            continue

        finished_flag.append(True)
        if sog is None:
            # Finished game, no box row for this skater → DNP void, same as grade.py.
            actuals.append(np.nan)
            results.append("void")
            units.append(np.nan)
            continue

        actuals.append(int(sog))
        line = float(r["line"])
        side = str(r["side"]).upper()
        if side == "OVER":
            if sog == line:
                results.append("void")
                units.append(np.nan)
                continue
            hit = sog > line
        elif side == "UNDER":
            if sog == line:
                results.append("void")
                units.append(np.nan)
                continue
            hit = sog < line
        else:
            results.append("void")
            units.append(np.nan)
            continue
        results.append("W" if hit else "L")
        if pd.isna(r.get("price")):
            units.append(np.nan)
        else:
            dec = am2dec(r["price"])
            units.append((dec - 1.0) if hit else -1.0)

    out["actual"] = actuals
    out["game_finished"] = finished_flag
    out["result"] = results
    out["units"] = units
    return out


# ---- idempotent write -----------------------------------------------------

def merge_existing(new: pd.DataFrame, path: str) -> pd.DataFrame:
    if new.empty:
        if os.path.exists(path):
            return pd.read_csv(path)
        return new
    new = new.copy()
    new["_k"] = new.apply(key_of, axis=1)
    if not os.path.exists(path):
        return new.drop(columns=["_k"])
    old = pd.read_csv(path)
    if old.empty:
        return new.drop(columns=["_k"])
    old["_k"] = old.apply(key_of, axis=1)
    # Keep a previously settled row (W/L/void) as-is. Refresh pending rows
    # (and any side not yet in the file) from this run.
    settled = old[old.result.isin(["W", "L", "void"])].copy()
    keep_keys = set(settled["_k"])
    add = new[~new["_k"].isin(keep_keys)].copy()
    # Preserve appeared_on / prices from the new collect for unsettled rows
    # (a later pass may add a list id to appeared_on).
    out = pd.concat([settled, add], ignore_index=True)
    # If a settled side gained a new appearance on a later re-run of collect,
    # update appeared_on only.
    appear = new.set_index("_k")["appeared_on"]
    out["appeared_on"] = out["_k"].map(lambda k: appear.get(k, np.nan)).fillna(out["appeared_on"])
    out = out.drop(columns=["_k"])
    # Drop accidental dupes if the on-disk file was edited by hand.
    out["_k"] = out.apply(key_of, axis=1)
    out = out.drop_duplicates("_k", keep="first").drop(columns=["_k"])
    return out


# ---- summary --------------------------------------------------------------

def _wl(df: pd.DataFrame) -> tuple[int, int, int, int]:
    w = int((df.result == "W").sum())
    l = int((df.result == "L").sum())
    v = int((df.result == "void").sum())
    p = int((df.result == "pending").sum())
    return w, l, v, p


def _units_block(df: pd.DataFrame) -> str:
    g = df[df.result.isin(["W", "L"])]
    priced = g[g.units.notna()]
    w, l, v, p = _wl(df)
    decided = w + l
    hit = (w / decided) if decided else float("nan")
    hit_s = f"{hit:.1%}" if decided else "n/a"
    if len(priced):
        u = priced.units.sum()
        be = 1.0 / priced["price"].map(am2dec).mean()
        u_s = f"{u:+.2f} u on {len(priced)} priced side{'s' if len(priced) != 1 else ''}"
        be_s = f"{be:.1%} break-even implied by those prices"
    else:
        u_s = "profit n/a (no posted prices)"
        be_s = "break-even n/a"
    unpriced = int(g.units.isna().sum())
    extra = f"; {unpriced} decided side{'s' if unpriced != 1 else ''} with profit n/a" if unpriced else ""
    return (
        f"{w}-{l}-{v} ({p} pending); hit rate {hit_s} on {decided} decided; "
        f"{u_s}; {be_s}{extra}"
    )


def print_summary(df: pd.DataFrame, skipped: list[str], n_collected: int) -> None:
    print("NHL SOG majority-list grader (4 or more of 7)")
    print(f"Unique sides collected: {n_collected}")
    if skipped:
        pretty = ", ".join(
            datetime.strptime(s, "%Y%m%d").strftime("%b %-d") for s in skipped
        )
        print(f"Skipped dates (no D files / no scored sheets): {pretty} ({', '.join(skipped)})")
    else:
        print("Skipped dates: none")
    if df.empty:
        print("No sides to grade.")
        return
    print()
    print("Overall:  " + _units_block(df))

    print("Price band (posted price worse than -150 is outside):")
    band = df["in_band"]
    print("  inside:   " + _units_block(df[band == True]))  # noqa: E712
    print("  outside:  " + _units_block(df[band == False]))  # noqa: E712
    unk = int(band.isna().sum()) if band.isna().any() else 0
    if unk:
        print(f"  band n/a: {unk} side(s) with no posted price")

    print("By evidence count (of 7):")
    for n in (4, 5, 6, 7):
        sub = df[df.agrees_n == n]
        print(f"  {n} of 7:  {_units_block(sub)}" if len(sub) else f"  {n} of 7:  no sides")

    w, l, v, p = _wl(df)
    decided = w + l
    pending = df[df.result == "pending"]
    if len(pending):
        games = ", ".join(sorted(pending.game.astype(str).unique()))
        print(f"Pending (game not final): {len(pending)} sides in {games}")

    print()
    print(f"Progress toward 100 graded sides: {decided} decided (W+L)"
          f"{'' if not v else f', {v} void'}{'' if not p else f', {p} pending'}.")
    if decided < 100:
        print(f"  {100 - decided} more decided sides needed before the 100-side bar.")
    else:
        print("  Bar of 100 decided sides has been reached.")


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    dates = dates_in_range(args)
    sides, skipped, passes = collect(dates)
    n_collected = len(sides)
    graded = grade_rows(sides)
    for c in COLS:
        if c not in graded.columns:
            graded[c] = pd.NA
    graded = graded[COLS]
    merged = merge_existing(graded, OUT)
    for c in COLS:
        if c not in merged.columns:
            merged[c] = pd.NA
    merged = merged[COLS].sort_values(["date", "list_id", "game", "player", "side", "line"])
    if "units" in merged.columns:
        merged["units"] = merged["units"].round(6)
    os.makedirs(HERE, exist_ok=True)
    merged.to_csv(OUT, index=False)
    print_summary(merged, skipped, n_collected)
    print(f"\nWrote {len(merged)} rows to {OUT}")
    # Pass list, for the run log.
    if passes:
        shown = ", ".join(f"{d}_{h}" + ("" if s else " (no sheet, skipped)") for d, h, s in passes)
        print(f"Passes considered: {shown}")


if __name__ == "__main__":
    main()
