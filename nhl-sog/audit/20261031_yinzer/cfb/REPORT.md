# CFB enhancement audit (Oct 31, 2026) — paper only, no Odds API credits (saved oddsapi_*.json/captures), no model changes
Inputs: /workspace/cfb/leans/*.csv (11 passes, 482 scored rows; levels for Oct 17 rebuilt from ESPN captures with price_check.py's rule). Finals: ESPN summary API (espn/*.json), all 93 games final, 0 ungraded.
Metric: edge_pts = Fliff price vs DK no-vig fair (price shop, both sides of every line scored). Short = gap_req (P4 3, G5/FCS 5) - edge.
## Grades (unique sides, last pass): 160-160, -23.11u at Fliff, -14.55u at DK (per-pass rows 241-241, -34.57u).
- Every edge was negative: max -0.95 (P4), -1.72 (G5), -2.81 (FCS); median -3.9. Closest to qualifying: one P4 side 3.95 short (won, +0.80u).
- Gap buckets 0-1/1-2/2-3: empty. 3-5: 1 side (1-0). Everything else 5+ short. See cfb_audit_output.txt for 1-pt buckets per level.
- Thresholds 2/4 or 1/3: still 0 qualifiers (record 0-0). Even 0/0 would qualify nothing: Fliff never beat DK fair on any CFB side.
- Better-priced side of each pair: 86-74, +0.24u Fliff, +5.79u DK (weak signal, small sample).
## Coverage: ESPN slate vs priced games: Oct 17 P4 26/27, G5 22/22, FCS 3/58; Oct 24 P4 23/25, G5 19/19, FCS 0/53. Feed: 18-59 events/pass with both DK+Fliff. FCS essentially absent from the odds feed; G5 not thin.
Files: cfb_all_scored_sides.csv, cfb_unique_sides_lastpass.csv, coverage_scored.csv, coverage_feed.csv, cfb_audit.py, cfb_audit_output.txt
