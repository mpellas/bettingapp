# Yinzer section-4 cross-check (Oct 26), paper only, no locked files touched
Script: gates_rerun.py (own code; uses repo game_starts.py for puck times only) -> gates_yinzer.csv, run_output.txt
74 posted NHL sides / 24 passes with sides (26 incl. empty 20261025_1306, _1601). Per day 26/4/9/18/11/6.
Window 150-210: 74/74 pass (minute diffs vs Tester3 up to 5 min = filename HHMM vs capture time; no gate change)
5-pt floor (20261020_1513 on): all pass. Recent form (sog60_r10*toi_r5/60 Poisson > no-vig): 74/74. Role veto: none on posted side.
Shop-at (95/5 blend, own formula): 74/74 match posted. Model pts: 74/74 match posted.
Noon PT: 4 violations confirmed (20261017_post.txt, NJD@WSH 10:00 AM PT: Strome U1.5, Meier O2.5, Chychrun U2.5, Gritsyuk O1.5). Aho O2.5 on same list is not pre-noon.
Agree<=2 as printed: Pastrnak 1017_1520, Sennecke 1019_1247, Kapanen 1020_1508, Hayton 1024_1512, Coronato 1024_1609 (5); Dunn 1024_1609 becomes 2 once the 22.3-pt huge move is not counted -> 6, matches Tester3.
Rule dates: 2-of-7 skip is not in code or git log; first written in NOTES.md line 174 (Oct 25 16:01 DeBrusk). Huge-move rule: no code, no NOTES entry, no threshold anywhere.
Huge-move threshold: same outcome for any cutoff from ~4 up to 22.3 pts (Dunn 22.3 is the binding case); Tester3's '4-22' OK.
TOI vote: not independently recomputed (needs season-to-date TOI); Tester3's 13 toi_vote vs sheet mismatches are all pre-d6cb300 passes.
Split 61/7/6 reproduced in count only; final-call texts for Oct 17-20 and Oct 24 are not on disk (markers only), so tester-skip membership not verifiable from files.
NFL: see report below.
NFL ESPN grades (site.api.espn.com summary): Horton wk5 SF@SEA 401872992 no stat line, not on injury list -> DNP/void; Mumpfield wk5 BUF@LAR 401872994 no stat line -> DNP/void; Skattebo wk6 NO@NYG 401873000 no stat line, listed Questionable -> DNP/void. track.py: all three no_stat, 0 units -> matches.
