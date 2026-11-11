# DailyFaceoff lineup audit — Sun Nov 1 2026 (Tester1)
All times PT. Read-only on /workspace/nhl-sog (files read by full path; nothing run there).

## Q1: Is the lineup pull refreshing?
Yes. The fetch is working. The stale times come from DFO's own `updatedAt` stamp.
- Code: `capture.py` (line 57) and `shop_gate.py` (line 18) both call `requests.get` on `dailyfaceoff.com/teams/{slug}/line-combinations` on every run. Each one parses `__NEXT_DATA__ ... combinations.updatedAt`. Neither has a cache layer. `dfo_updated` in the GATE files is the site's stamp, not our fetch time.
- Evidence that the fetch is live: in the same runs, the other teams' stamps were from this morning. EDM was 6:25 AM, OTT 6:26 AM, WPG 6:28 AM.
- Stored stamps per team in the picks/20261101_D_*_GATE.csv files:
  | Run | Team | DFO updatedAt | Age at run |
  |---|---|---|---|
  | 0908 | MIN / WSH | Oct 31 7:57 AM | ~25 h |
  | 0908 | CAR (WPG@CAR, never listed: pre-noon rule) | Oct 30 6:57 AM | ~50 h |
  | 0933 | PHI | Oct 31 9:05 AM | ~24.5 h |
  | 0933 | UTA | Oct 30 6:54 AM | ~51 h |
  | 1137 | NYR | Oct 31 9:22 AM | ~26 h |
  | 1334 | ANA | Oct 31 10:00 AM | ~27.5 h |
- Live check (curl of the public pages at 4:15 PM): NYR updated 2:38 PM today, UTA 12:40 PM, PHI 12:37 PM, ANA **still Oct 31 10:00 AM**.
- Conclusion: DFO updates many teams only about 20–60 minutes before puck drop, after the morning skate or warmups. Our passes run about 3.5 h out, so the 12-hour rule mostly measures DFO's timing, not news. ANA had not been updated even 45 minutes before puck drop. Possible fixes: a re-pull 30–45 minutes before the game, a looser rule for unchanged lineups, or a second source (team or beat reporter).

## Q2: Sides the 12-hour rule blocked or would have blocked (Fliff-check sides only; the DK list was empty in every run)
| Run | Player | Side | Game | Lineup age | Other blocker | Result |
|---|---|---|---|---|---|---|
| 0933 | Trevor Zegras | O1.5 | UTA@PHI | 24.5/51 h | no Fliff market | 1 SOG, LOSS |
| 0933 | Porter Martone | O1.5 | UTA@PHI | same | no Fliff market | 2, WIN |
| 0933 | Vincent Trocheck | O1.5 | UTA@PHI | same | no Fliff market | 2, WIN |
| 0933 | Dylan Guenther | U2.5 | UTA@PHI | same | no Fliff market; line moved 16.9 pts against | 4, LOSS |
| 0933 | Travis Sanheim | O1.5 | UTA@PHI | same | no Fliff; only 2/7 agree | 2, WIN |
| 1137 | Pavel Dorofeyev | U2.5 | EDM@NYR | NYR 26 h | Fliff +105 and DK +110, both worse than shop-at +125 | game LIVE at 4:15 PM (0 SOG so far), not graded |
| 1334 | Jackson LaCombe | U1.5 | OTT@ANA | ANA 27.5 h | Fliff not posted; DK -150 worse than -128 | not started (5:00 PM), not graded |
| 1334 | Beckett Sennecke | U2.5 | OTT@ANA | same | Fliff not posted; DK -110 worse than +105 | not started, not graded |
- 0908 (MIN@WSH): lineups were 25 h old, but no side cleared the 5-point floor, so the rule blocked nothing in practice.
- Podkolzin U1.5 (EDM, fresh lineup) was not blocked by the rule. It failed on price only.
- **Total: 8 sides. Every one of them was also blocked by something else** (no Fliff market, or price worse than shop-at). Removing the 12-hour rule would not have produced a single bet today.
- Graded so far: UTA@PHI, 3-2 on paper (Sanheim also failed agreement). The NYR and ANA sides should be graded after tonight's games.
- Oddity to confirm: Trocheck is listed under Utah at Philadelphia (game 2026020229). The box score has him in that game, so the data is consistent. If that's wrong, it's a roster or name-mapping issue, not a lineup one.
