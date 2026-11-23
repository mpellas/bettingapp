#!/bin/bash
# Score one week, then apply the INTERIM single-week label. Use this instead of calling nflprops.track week directly.
# Usage: scripts/track_week.sh --season 2026 --week 7
cd "$(dirname "$0")/.." || exit 1
.venv/bin/python -m nflprops.track week "$@" || exit $?
S=2026; W=""; while [ $# -gt 0 ]; do case "$1" in --season) S=$2; shift;; --week) W=$2; shift;; esac; shift; done
.venv/bin/python scripts/label_interim.py "data/track/${S}_wk$(printf %02d "$W").summary.json"
.venv/bin/python scripts/add_scope_inputs.py "$S" "$W"
_rc=$?  # keep the original exit status
# EXTRA MARKETS (added 2026-11-15, data-only; spread ATS added 2026-11-22): raw O/U-at-line grading of other free DK-via-ESPN props (receptions, carries,
# QB/defense/kicker totals) plus game point spread ATS (both sides, line and price, plus close) into sidecars/extra_markets/graded/nfl_*.csv. Separate files; never affects the outputs above.
timeout 600 .venv/bin/python sidecars/extra_markets/grade_extra_nfl.py --season "$S" --week "$W" 2>&1 | tail -n 1 || true
exit $_rc
