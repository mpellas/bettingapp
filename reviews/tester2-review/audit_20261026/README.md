# Tester2 Oct 26 section 3 audit + item 6
- three records: /workspace/nhl-sog/three_records.py (nightly grader; fresh NHL API shots, matched by nhl_id) + card_decisions.csv (skips from FINAL CALL cards; append new skips nightly).
  Run: cd /workspace/nhl-sog && .venv/bin/python three_records.py [YYYYMMDD ...]  -> graded/three_records_sides.csv, graded/three_records.md
- bets audit: audit_bets.py -> bets_audit.csv
- list_track backfill: list_track_backfill.md (note list_track still skips 20261017_post.txt and has no graded/20261025.csv; three_records.py covers both)
