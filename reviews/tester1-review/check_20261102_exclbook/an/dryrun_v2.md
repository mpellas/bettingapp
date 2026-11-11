**NFL build v2 dry run** (raw/20261101T1709 only, offline, 0 Odds API credits, paper only)

Result: **NO BETS**. 0 of 869 sides pass all gates.
- **Goff U259.5 (DET):** the fair price across all 3 books at 259.5 is 50.2%, so EV at DK −113 is −5.4%. Only 1 sharp book (Pinnacle) is at that line, and the model gives the under 39.3%. Fail.
- **Aaron Jones U29.5 (MIN):** the fair price across 4 books gives EV −1.9%. Only 1 sharp book (Pinnacle) is at the line, and the model gives the under 20.8%. Fail.
- **Josh Palmer O8.5 PP (BUF):** "Joshua Palmer" now matches, and he's in the model universe. The books are at 9.5 (5 books, no sharp) and 10.5 (FanDuel and Pinnacle), and none is at 8.5. With no exact-line price, he fails.
- **Reggie Virgil U11.5 PP:** now tagged **ARI**. He fails because no book is at 11.5 and he's not in the model universe.
- **Ty Johnson O1.5 rush PP:** now tagged **BUF**. The fair price is 49.8%, there's no sharp book at 1.5, and he's not in the model universe. Fail.

**Sharp coverage** (342 priced lines with at least 2 books quoting both sides at the same exact line):
- 2+ sharp books (FanDuel and Pinnacle): **109 (31.9%)**
- Pinnacle only: **35 (10.2%)**
- FanDuel only: 41 (12.0%)
- No sharp book: 157 (45.9%)

Caveat: `find.py` defines only Pinnacle as sharp (`SHARP = {"pinnacle": 3}`). v2 adds FanDuel and Circa, but Circa isn't in this pull. Under the code's own list, no line can ever have 2 sharp books, so the gate would block everything. With FanDuel counted, about a third of lines are eligible.
