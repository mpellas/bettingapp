"""Post-scoring sidecar (2026-10-24, Tester3): per-line scope inputs so the prereg model_scope cutoff
(markets.universe_mask: >= 2 prior games; public projection >= 20 yds; QB must be projected starter; QB rushing out of scope) can be checked directly.
Reads data/track/<S>_wkWW.parquet + the pregame file each line was scored from (pred_file); writes
data/track/<S>_wkWW_scope.csv. Read-only w.r.t. scoring; track.py (prereg-pinned) untouched.
Usage: python scripts/add_scope_inputs.py 2026 7"""
import sys, pandas as pd
S, W = int(sys.argv[1]), int(sys.argv[2]); base = f'data/track/{S}_wk{W:02d}'
t = pd.read_parquet(f'{base}.parquet')
keys = ['player_id', 'market']; cols = ['public_proj', 'is_proj_starter', 'position']
P = []
for f in t.pred_file.dropna().unique():
    p = pd.read_parquet(f if f.endswith('.parquet') else f.rsplit('.', 1)[0] + '.parquet')
    P.append(p[keys + cols].drop_duplicates(keys).assign(pred_file=f))
P = pd.concat(P) if P else pd.DataFrame(columns=keys + cols + ['pred_file'])
m = t[['player_id', 'player_name', 'market', 'line_D', 'pred_file', 'in_scope', 'out_of_scope', 'void', 'status']].merge(P, on=keys + ['pred_file'], how='left')
def reason(r):
    if bool(r.void): return 'void (' + ('in scope' if r.in_scope else 'out of scope') + ')'
    if not r.out_of_scope: return 'in scope' if r.in_scope else 'not scored (void/pending)'
    if r.position == 'QB' and r.market == 'rush_yds': return 'QB rushing (always out of scope)'
    if r.position == 'QB' and r.market == 'pass_yds' and not r.is_proj_starter: return 'QB not projected starter'
    if r.n_prior_games < 2: return 'fewer than 2 prior games (universe rule p_n_prior >= 2)'
    if pd.notna(r.public_proj) and r.public_proj < 20: return 'public projection < 20 yds'
    return 'out of scope (other / projection missing)'
# prior-game count (universe_mask also needs p_n_prior >= 2; not stored in the pred file). Recomputed from nflverse
# weekly stats rows before this week (same season and earlier) as a check column; track.py's in_model_universe is authoritative.
st = pd.read_parquet('data/cache/raw/player_stats_%d.parquet' % S)
prior = st[st.week < W].groupby('player_id').size()
try:
    prev = pd.read_parquet('data/cache/raw/player_stats_%d.parquet' % (S - 1)).groupby('player_id').size()
    prior = prior.add(prev, fill_value=0)
except Exception: pass
m['n_prior_games'] = m.player_id.map(prior).fillna(0).astype(int)
m['scope_reason'] = m.apply(reason, axis=1)
m.to_csv(f'{base}_scope.csv', index=False)
print(f'{base}_scope.csv', len(m)); print(m.scope_reason.value_counts().to_string())
