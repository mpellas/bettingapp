#!/bin/bash
# Score one week, then apply the INTERIM single-week label. Use this instead of calling nflprops.track week directly.
# Usage: scripts/track_week.sh --season 2026 --week 7
cd "$(dirname "$0")/.." || exit 1
.venv/bin/python -m nflprops.track week "$@" || exit $?
S=2026; W=""; while [ $# -gt 0 ]; do case "$1" in --season) S=$2; shift;; --week) W=$2; shift;; esac; shift; done
.venv/bin/python scripts/label_interim.py "data/track/${S}_wk$(printf %02d "$W").summary.json"
.venv/bin/python scripts/add_scope_inputs.py "$S" "$W"
