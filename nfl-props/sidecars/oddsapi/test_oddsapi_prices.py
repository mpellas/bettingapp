"""Odds API price parse + merge onto ESPN lines (no network)."""
import nflprops.oddsapi as oa


SAMPLE = {
    "id": "abc",
    "bookmakers": [
        {"key": "fanduel", "markets": [
            {"key": "player_rush_yds", "outcomes": [
                {"name": "Over", "description": "Chuba Hubbard", "price": -110, "point": 66.5},
                {"name": "Under", "description": "Chuba Hubbard", "price": -110, "point": 66.5},
            ]},
        ]},
        {"key": "draftkings", "markets": [
            {"key": "player_rush_yds", "outcomes": [
                {"name": "Over", "description": "Chuba Hubbard", "price": -115, "point": 66.5},
                {"name": "Under", "description": "Chuba Hubbard", "price": -105, "point": 66.5},
            ]},
            {"key": "player_pass_yds", "outcomes": [
                {"name": "Over", "description": "Baker Mayfield", "price": -120, "point": 245.5},
                {"name": "Under", "description": "Baker Mayfield", "price": 100, "point": 245.5},
            ]},
        ]},
    ],
}


def test_parse_and_prefer_draftkings():
    rows = oa.parse_prices(SAMPLE)
    idx = oa.index_prices(rows)
    hub = idx[(oa.norm_name("Chuba Hubbard"), "rush_yds")]
    assert hub[0]["book"] == "draftkings" and hub[0]["over_price"] == -115


def test_merge_onto_espn_by_player_market():
    espn = [
        {"espn_id": "1", "market": "rush_yds", "line": 66.5, "over_price": None, "under_price": None},
        {"espn_id": "2", "market": "pass_yds", "line": 245.5, "over_price": None, "under_price": None},
        {"espn_id": "3", "market": "rec_yds", "line": 40.5, "over_price": None, "under_price": None},  # no price
    ]
    names = {"1": oa.norm_name("Chuba Hubbard"), "2": oa.norm_name("Baker Mayfield"), "3": oa.norm_name("Someone Else")}
    out, n = oa.merge_prices_onto_espn(espn, oa.index_prices(oa.parse_prices(SAMPLE)), names)
    assert n == 2
    assert out[0]["over_price"] == -115 and out[0]["under_price"] == -105 and out[0]["price_book"] == "draftkings"
    assert out[1]["over_price"] == -120
    assert out[2]["over_price"] is None


def test_match_event_by_teams_and_kick():
    import datetime as dt
    events = [
        {"id": "x", "home_team": "Carolina Panthers", "away_team": "Detroit Lions",
         "commence_time": "2026-10-04T17:20:00Z"},
        {"id": "y", "home_team": "New Orleans Saints", "away_team": "Atlanta Falcons",
         "commence_time": "2026-10-06T00:15:00Z"},
    ]
    kick = dt.datetime.fromisoformat("2026-10-04T17:20:00+00:00")
    m = oa.match_event("Carolina Panthers", "Detroit Lions", kick, events)
    assert m["id"] == "x"


def test_norm_name():
    assert oa.norm_name("A.J. Brown") == oa.norm_name("AJ Brown")
    assert oa.norm_name("Kenneth Walker III") == "kenneth walker"
