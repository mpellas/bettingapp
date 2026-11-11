#!/bin/bash
# Nightly paper-only shadow trackers. Usage: run_nightly.sh YYYYMMDD (PT slate date)
set -e; D=$1; N=/workspace/nhl-sog; E=/workspace/tester1-review/enh1_promo_under; C=/workspace/tester1-review/item4_overbias/challenger
P=$(ls $N/picks/${D}_D_[0-9][0-9][0-9][0-9]_GATE.csv 2>/dev/null | sed -E 's/.*_D_([0-9]{4})_GATE.csv/\1/')
for X in $E/nhl-sog_copy $C/src; do for p in $P; do cp -a $N/picks/${D}_D_${p}.csv $N/picks/${D}_D_${p}_GATE.csv $X/picks/; done; done
for p in $P; do (cd $E && python3 shadow_no_promo_under.py picks/${D}_D_$p.csv picks/${D}_D_${p}_GATE.csv $E/forward/slate_${D}_$p.csv);
  (cd $C && python3 shadow_shrink50.py slate src/picks/${D}_D_$p.csv src/picks/${D}_D_${p}_GATE.csv --out forward/slate_${D}_$p.csv); done
python3 $E/forward/tally_forward.py $D; python3 $C/forward/tally_forward.py $D; python3 $N/shadow/edge8_band/edge8_band.py $D
