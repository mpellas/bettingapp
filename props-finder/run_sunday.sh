#!/bin/bash
# One command: Odds API pull (find.py, saves raw JSON) + full analysis.
# Usage: ./run_sunday.sh HOURS MAX_CREDITS [--counts]      e.g. ./run_sunday.sh 5 76 --counts
#   --counts adds player_receptions, player_pass_completions, player_rush_attempts (6 credits/event instead of 3)
#   Credit floor is fixed at 250: find.py never lets the remaining balance drop below it.
set -e; cd "$(dirname "$0")"; PY=/workspace/nfl-props/.venv/bin/python
H="${1:-5}"; C="${2:-40}"; shift 2 || true; EXTRA="$*"
"$PY" find.py --sport nfl --hours "$H" --max-credits "$C" --floor 250 $EXTRA
"$PY" analyze.py --raw latest $EXTRA
