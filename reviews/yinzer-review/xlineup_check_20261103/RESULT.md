# X line-rush would-skips vs NHL.com, Nov 3 2026 (paper only)

Source: NHL stats API timeonice (EV/PP/total TOI) + shiftcharts (top same-position linemates by shared ice time) + gamecenter boxscore (SOG). 'Actual' = EV-TOI rank among team F (÷3) or D (÷2). All 24 dressed.

| Pass | Player (team) | DFO | X | Actual (EV rank / total rank) | EV TOI | PP TOI | Top linemates | Class | DK line / SOG |
|---|---|---|---|---|---|---|---|---|---|
| 1239 | Charle-Edouard D'Astous (Tampa Bay Lightning) | d3 | extra | d2 (4/2) | 13:51 | 4:21 | Carlson | DFO right (X had him as extra D; he played pair 2 + 4:21 PP) | 1.5 / 2 |
| 1239 | Blake Coleman (Minnesota Wild) | f2 | f3 | f3 (8/6) | 11:25 | 1:26 | McCarron/Brink | X right | 1.5 / 1 |
| 1239 | Michael McCarron (Minnesota Wild) | f2 | f3 | f3 (9/9) | 11:24 | 0:00 | Coleman/Brink | X right | 1.5 / 1 |
| 1239 | Owen Tippett (Philadelphia Flyers) | f2 | f3 | f3 (7/10) | 11:51 | 0:29 | Foerster/Knuble | X right (swap) | 2.5 / 2 |
| 1239 | Tyson Foerster (Philadelphia Flyers) | f2 | f3 | f2 (4/5) | 14:28 | 0:49 | Tippett/Barkey | DFO right (swap) | 1.5 / 3 |
| 1239 | Matvei Michkov (Philadelphia Flyers) | f3 | f2 | f2 (5/4) | 12:05 | 4:15 | Martone/Cates | X right (swap) | 1.5 / 4 |
| 1239 | Porter Martone (Philadelphia Flyers) | f3 | f2 | f4 (11/8) | 9:42 | 3:28 | Michkov/Cates | unclear (EV rank 11 but on Michkov line) | 1.5 / 1 |
| 1239 | Maxim Shabanov (Minnesota Wild) | f3 | f2 | f2 (5/4) | 13:09 | 4:58 | Yurov/Trenin | X right | 1.5 / 1 |
| 1239 | Tom Wilson (Washington Capitals) | f1 | f2 | f3 (7/3) | 13:48 | 2:50 | Dubois/Protas | unclear (EV rank 7, total rank 3) | 1.5 / 1 |
| 1239 | Alex Tuch (Washington Capitals) | f2 | f1 | f1 (3/1) | 14:30 | 1:39 | Strome/Kyrou | X right (swap) | 2.5 / 2 |
| 1239 | Dylan Strome (Washington Capitals) | f2 | f1 | f1 (2/2) | 14:56 | 2:52 | Kyrou/Tuch | X right (swap) | 1.5 / 3 |
| 1239 | Jordan Kyrou (Washington Capitals) | f2 | f1 | f2 (6/6) | 14:13 | 2:50 | Strome/Tuch | DFO right (swap) | 1.5 / 1 |
| 1239 | Aliaksei Protas (Washington Capitals) | f1 | f2 | f2 (5/7) | 14:22 | 0:00 | Dubois/Wilson | X right (swap) | 1.5 / 0 |
| 1239 | Nazem Kadri (Colorado Avalanche) | f2 | f3 | f3 (7/6) | 11:44 | 3:05 | Landeskog/Roy | X right (swap) | 2.5 / 1 |
| 1239 | Brock Nelson (Colorado Avalanche) | f3 | f2 | f2 (6/4) | 12:03 | 0:53 | Schwartz/Hughes | X right (swap) | 1.5 / 0 |
| 1307 | Timo Meier (New Jersey Devils) | f1 | f2 | f1 (2/2) | 17:38 | 2:54 | Evangelista/Hischier | DFO right (swap) | 2.5 / 2 |
| 1307 | Nico Hischier (New Jersey Devils) | f1 | f2 | f2 (6/4) | 13:49 | 2:42 | Meier/Evangelista | X right (swap) | 2.5 / 0 |
| 1307 | Jesper Bratt (New Jersey Devils) | f2 | f1 | f2 (4/3) | 15:07 | 4:13 | Hughes/Gritsyuk | DFO right (swap) | 1.5 / 4 |
| 1307 | Jack Hughes (New Jersey Devils) | f2 | f1 | f1 (1/1) | 20:58 | 4:19 | Bratt/Gritsyuk | X right (swap) | 3.5 / 5 |
| 1307 | Luke Evangelista (New Jersey Devils) | f1 | f2 | f1 (3/5) | 15:32 | 2:18 | Meier/Hischier | DFO right (swap) | 1.5 / 2 |
| 1307 | Arseny Gritsyuk (New Jersey Devils) | f2 | f1 | f2 (5/6) | 14:37 | 1:57 | Hughes/Bratt | DFO right (swap) | 2.5 / 1 |
| 1335 | Ross Colton (Nashville Predators) | f3 | f4 | f3 (7/8) | 13:24 | 0:56 | Edstrom/Drury | DFO right | 1.5 / 1 |
| 1436 | Linus Karlsson (Vancouver Canucks) | f3 | f2 | f3 (8/8) | 12:00 | 2:50 | O'Connor/Quillan | DFO right | 1.5 / 1 |
| 1436 | Jonathan Lekkerimaki (Vancouver Canucks) | f2 | f3 | f3 (7/6) | 12:18 | 3:29 | Ohgren/Rossi | X right (swap) | 1.5 / 2 |

Counts: {'DFO right': 9, 'X right': 13, 'unclear': 2}. No posted or Fliff-check side on any of these 24 players, so no bet outcome was affected; DK line/SOG shown for reference only.

## Findings
- No would-skip was a scratch or a real lineup change. All 24 dressed in roles close to both sources. Every one would have been a **false skip**.
- About 20 of the 24 are the same trio given a different number (1↔2 or 2↔3). Shift linemates confirm the trios stayed together: NJD Meier-Hischier-Evangelista and Hughes-Bratt-Gritsyuk, WSH Strome-Kyrou-Tuch and Dubois-Wilson-Protas, PHI Tippett-Foerster and Michkov-Martone, MIN Coleman-McCarron-Brink. Within one trio, the TOI rank often lands in two different line buckets, so line numbering is noise at the 1-3 level.
- X's only material error was D'Astous (TBL), whom it listed as extra D. He played pair 2 with 4:21 of PP. That was a would-skip on a playing PP1 defenseman.
- Recommendation: X adds nothing as a gate. Keep it logging only. If it stays, compare player sets (trio/pair membership plus dressed/scratched) instead of line numbers, and only skip on a scratch or a move to/from line 4 / pair 3.

## Task B: capture-loop stall (Nov 3-4)
- The loop ran at 20:03:59 and 23:35:49 PT, where it set NEXT_SLEEP 600 with the next puck drop 1014 min away. The next run was 07:02:57 PT.
- The supervisor checks every 30 s and alerts when the heartbeat is more than 480 s stale. It logged nothing between 13:59 on Nov 3 and 07:02:55 on Nov 4. At 07:02:55 it reported the heartbeat 26,628 s stale, so the last touch was about 23:39 PT. Between 20:04 and 23:35 the heartbeat also went 3.5 h without a run and the supervisor raised no alert.
- The box did not reboot (uptime since Nov 2 09:49). If the worker had hung, the supervisor would have caught it within 8 min. Both processes were silent, so the likely cause is that the whole box was paused or suspended while no agent was active. The supervisor has no hours-of-operation logic, and the loop never sleeps longer than 600 s. Earlier stale alerts (Nov 3 at 08:59, 10:01 and 13:59; Nov 4 at 07:59) fit the same pattern of short pauses.
- Risk for tonight's 7:00 PM PT games (SJ@LA, CGY@SEA): low to moderate. Closes land around 6:30-7:00 PM. The nhl-fliff-second-pull routine wakes the box every 10 min until 7:50 PM, but after a pause the first capture can come up to about 4.5 min late. Nov 3 still captured closes 1.5-4 min before puck drop.
- Minimal fix (no code change): a routine at about 6:15, 6:35 and 6:50 PM PT on slate days that runs `ops/ensure_capture.sh` and checks for `CLOSE_*` files. Optionally the supervisor could log an "ALERT box resumed after Ns" line when its own 30 s sleep takes more than 120 s, so pauses become visible.
