"""NON-PREREG extra line for challenger/SHADOW_REPORT.md (added 2026-10-19, user-approved, post-hoc).
Re-scores the same rows as grade_shadow.py (locked, unchanged) but drops BOS@LA event 401892530 (early close:
DK pulled the board 16.7 min before puck drop). Appended as a clearly labeled extra section; the prereg scoring
above it is untouched. Run AFTER grade_shadow.py:  python3 challenger/grade_shadow.py && python3 challenger/shadow_extra.py"""
from common import *
import glob
EXCLUDE_EVENTS = {'401892530'}
h = open(os.path.join(HERE, 'CHALLENGER')).read().strip()
START = os.environ.get('SHADOW_START_TEST', '20261017')
rows = []
for f in sorted(glob.glob(os.path.join(HERE, 'shadow', f'*_D_{h}.csv'))):
    d = os.path.basename(f)[:8]
    if d < START or not os.path.exists(os.path.join(ROOT, 'graded', f'{d}.csv')): continue
    s = pd.read_csv(f); g = pd.read_csv(os.path.join(ROOT, 'graded', f'{d}.csv'))
    rows.append(g.merge(s[['nhl_id', 'gameId', 'line', 'p_chal_over']], on=['nhl_id', 'gameId', 'line'], how='left').assign(date=d))
RP = os.path.join(HERE, 'SHADOW_REPORT.md'); txt = open(RP).read().split('\n## NON-PREREG')[0].rstrip('\n')
L = ['', '## NON-PREREG extra line (post-hoc reporting choice, not part of the locked score): BOS@LA 401892530 excluded', '']
if rows:
    import game_starts as GS
    G, _ = GS.mark_pre_noon(pd.concat(rows, ignore_index=True))
    G = G[(G.status == 'OK') & G.actual.notna() & G.p_chal_over.notna()]
    nx = int(G.event.astype(str).isin(EXCLUDE_EVENTS).sum()); G = G[~G.event.astype(str).isin(EXCLUDE_EVENTS)]
    o = (G.actual > G.line).astype(int).values; gid = G.gameId.values
    def ll(p): p = np.clip(p, 1e-6, 1 - 1e-6); return -(o * np.log(p) + (1 - o) * np.log(1 - p))
    lg = lambda p: np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
    zc = lg(G.nv_over_C.values) - lg(G.nv_over.values)
    f = lambda t: f'{t[0]:+.4f} [{t[1]:+.4f}, {t[2]:+.4f}]'
    dll = boot_diff(ll(G.p_chal_over.values) - ll(G.p_model_over.values), gid)
    oc, och = G.p_chal_over.values > G.nv_over.values, G.p_model_over.values > G.nv_over.values
    dz = boot_diff(np.where(oc, zc, -zc) - np.where(och, zc, -zc), gid)
    L += [f'{nx} BOS@LA rows dropped; {len(G)} lines, {G.gameId.nunique()} games remain.', '',
          f'- Log-loss, challenger - champion: {f(dll)}',
          f'- Lean z-CLV, challenger - champion: {f(dz)}', '',
          'This line is for information only. The prereg verdict uses the locked numbers above.']
else: L.append('No graded shadow slates yet.')
open(RP, 'w').write(txt + '\n' + '\n'.join(L) + '\n'); print('\n'.join(L))
