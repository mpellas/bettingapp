"""ESPN public JSON endpoints (no key). Scoreboards, summaries, rosters."""
from __future__ import annotations

from datetime import datetime, timezone

from .net import get_json

SITE = "https://site.api.espn.com/apis/site/v2/sports/football/{lg}"
CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/{lg}"
LG = {"nfl": "nfl", "ncaaf": "college-football"}


def scoreboard(league: str, week: int | None = None, season: int | None = None,
               seasontype: int = 2, ttl: float = 900) -> dict:
    params = {"limit": 400}
    if league == "ncaaf":
        params["groups"] = 80  # FBS
    if week is not None:
        params.update({"week": week, "seasontype": seasontype})
        if season:
            params["year"] = season
    return get_json(SITE.format(lg=LG[league]) + "/scoreboard", params, ttl=ttl)


def summary(league: str, event_id: str, final: bool = False) -> dict:
    # Completed games never change -> cache forever; otherwise 20 min.
    return get_json(SITE.format(lg=LG[league]) + "/summary", {"event": event_id},
                    ttl=None if final else 1200)


def team_roster(league: str, team_id: str) -> dict | None:
    return get_json(SITE.format(lg=LG[league]) + f"/teams/{team_id}/roster", ttl=24 * 3600,
                    allow_404=True)


def parse_event(ev: dict) -> dict:
    """Flatten a scoreboard event into a game dict."""
    comp = ev["competitions"][0]
    home = next(c for c in comp["competitors"] if c["homeAway"] == "home")
    away = next(c for c in comp["competitors"] if c["homeAway"] == "away")
    odds = (comp.get("odds") or [{}])[0]
    venue = comp.get("venue") or {}
    st = ev["status"]["type"]

    def sc(c):
        try:
            return float(c.get("score"))
        except (TypeError, ValueError):
            return None

    g = {
        "event_id": ev["id"],
        "date_utc": ev["date"],
        "name": ev.get("shortName"),
        "state": st.get("state"),  # pre / in / post
        "completed": bool(st.get("completed")),
        "status_detail": st.get("shortDetail"),
        "neutral": bool(comp.get("neutralSite")),
        "home_id": home["team"]["id"], "home": home["team"].get("abbreviation"),
        "home_name": home["team"].get("displayName"),
        "away_id": away["team"]["id"], "away": away["team"].get("abbreviation"),
        "away_name": away["team"].get("displayName"),
        "home_score": sc(home), "away_score": sc(away),
        "venue": venue.get("fullName"), "indoor": venue.get("indoor"),
        "odds_details": odds.get("details"), "total": odds.get("overUnder"),
        "home_spread": odds.get("spread"),  # ESPN 'spread' is the home team's line
        "odds_provider": (odds.get("provider") or {}).get("name"),
    }
    # implied team totals
    if g["total"] is not None and g["home_spread"] is not None:
        try:
            t, s = float(g["total"]), float(g["home_spread"])
            g["home_implied"] = round((t - s) / 2, 1)
            g["away_implied"] = round((t + s) / 2, 1)
        except (TypeError, ValueError):
            pass
    return g


def current_slate(league: str) -> tuple[int, int, list[dict]]:
    """Return (season, week, games) for the slate that still has unplayed games.
    If every game in ESPN's 'current' week is final, roll to the next week."""
    sb = scoreboard(league)
    season = sb["season"]["year"]
    week = sb["week"]["number"]
    games = [parse_event(e) for e in sb.get("events", [])]
    if games and all(g["completed"] for g in games):
        nxt = scoreboard(league, week=week + 1, season=season)
        ng = [parse_event(e) for e in nxt.get("events", [])]
        if ng:
            week, games = week + 1, ng
    return season, week, games


def game_weather(league: str, event_id: str, indoor: bool | None) -> dict:
    """Forecast/observed weather from the ESPN summary (AccuWeather feed)."""
    out = {"weather": "Indoor" if indoor else "n/a", "temp_f": None, "gust_mph": None, "precip_pct": None}
    if indoor:
        return out
    try:
        s = summary(league, event_id)
    except Exception:  # noqa: BLE001
        out["weather"] = "fetch failed"
        return out
    w = (s.get("gameInfo") or {}).get("weather")
    if w:
        out.update(temp_f=w.get("temperature"), gust_mph=w.get("gust"), precip_pct=w.get("precipitation"))
        parts = [f"{w.get('temperature')}F"]
        if w.get("gust") is not None:
            parts.append(f"gusts {w.get('gust')} mph")
        if w.get("precipitation") is not None:
            parts.append(f"precip {w.get('precipitation')}%")
        out["weather"] = ", ".join(parts)
    return out


def game_injuries(league: str, event_id: str) -> dict[str, dict]:
    """ESPN game-day injury list keyed by ESPN athlete id (NFL has it; college usually empty)."""
    res = {}
    try:
        s = summary(league, event_id)
    except Exception:  # noqa: BLE001
        return res
    for t in s.get("injuries") or []:
        for inj in t.get("injuries", []):
            a = inj.get("athlete") or {}
            d = inj.get("details") or {}
            res[str(a.get("id"))] = {
                "status": inj.get("status"),
                "detail": " ".join(x for x in [d.get("type"), d.get("detail")] if x and x != "Not Specified"),
                "name": a.get("displayName"),
            }
    return res


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
