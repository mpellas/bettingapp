"""Head-to-head shadow scoring: frozen challenger vs frozen champion vs DK no-vig, on slates on/after START only.
Joins challenger/shadow/<date>_D_<hash>.csv with graded/<date>.csv (champion grading: actual, status, nv_over_C).
Rows: status OK (result and close known); games with puck drop before 12:00 PM PT are excluded_pre_noon (same as grade_report.py, from 20261017). Metrics with game-clustered 95% CIs (2000 draws):
  log-loss and Brier of P(over at the DK line); paired differences challenger - champion and challenger - market;
  lean-side z-CLV (logit no-vig C minus D, signed by the lean) for challenger and champion; lean hit vs implied.
Usage: python3 challenger/grade_shadow.py  -> challenger/SHADOW_REPORT.md"""
from common import *
import glob
h = open(os.path.join(HERE, 'CHALLENGER')).read().strip()
PR = json.load(open(os.path.join(HERE, 'models', f'model_{h}.json')))
START = os.environ.get('SHADOW_START_TEST', '20261017')  # env override for tests only
rows = []
for f in sorted(glob.glob(os.path.join(HERE, 'shadow', f'*_D_{h}.csv'))):
    d = os.path.basename(f)[:8]
    if d < START or not os.path.exists(os.path.join(ROOT, 'graded', f'{d}.csv')): continue
    s = pd.read_csv(f); g = pd.read_csv(os.path.join(ROOT, 'graded', f'{d}.csv'))
    j = g.merge(s[['nhl_id', 'gameId', 'line', 'p_chal_over', 'late', 'stale_inputs']], on=['nhl_id', 'gameId', 'line'], how='left').assign(date=d)
    rows.append(j)
L = ['# Challenger shadow track', '', f'Challenger `{h}` (features: {len(PR["features"])}, groups {PR["groups"]}, trees {PR["trees"]}, k {PR["k"]:.2f}, trained through {PR["trained_through"]}) vs champion `c3ab760178` vs DraftKings no-vig.', f'Scored slates: {START} onward (see challenger/PREREG_{h}.md).', '']
if not rows:
    L.append('No graded shadow slates yet.')
else:
    G = pd.concat(rows, ignore_index=True)
    import game_starts as GS
    G, noon_summary = GS.mark_pre_noon(G)  # excluded_pre_noon for puck drop before 12:00 PM PT (from EXCLUDE_FROM)
    n_excl = int((G.status == 'excluded_pre_noon').sum())
    n_all = len(G); G = G[(G.status == 'OK') & G.actual.notna()]
    miss = G.p_chal_over.isna().sum(); G = G[G.p_chal_over.notna()]
    o = (G.actual > G.line).astype(int).values; gid = G.gameId.values
    def ll(p): p = np.clip(p, 1e-6, 1 - 1e-6); return -(o * np.log(p) + (1 - o) * np.log(1 - p))
    lg = lambda p: np.log(np.clip(p, 1e-3, 1 - 1e-3) / (1 - np.clip(p, 1e-3, 1 - 1e-3)))
    zc = lg(G.nv_over_C.values) - lg(G.nv_over.values)
    f = lambda t: f'{t[0]:+.4f} [{t[1]:+.4f}, {t[2]:+.4f}]'
    noon_note = f'{n_excl} rows marked excluded_pre_noon (puck drop before 12:00 PM PT; same rule as grade_report.py).' if n_excl else f'Pre-noon PT exclusion active from {GS.EXCLUDE_FROM} (0 rows excluded in this window).'
    L += [f'Rows: {len(G)} OK lines with a challenger prediction ({G.gameId.nunique()} games, {G.date.nunique()} slates); '
          f'{miss} OK lines had no challenger prediction; {int(G.late.sum())} predictions were produced late (inputs cut at the prior day, so not leaky); '
          f'{int(G.stale_inputs.sum())} flagged stale inputs. {noon_note}', '',
          '| model | log-loss | Brier | log-loss minus market | lean z-CLV | lean hit vs implied |', '|---|---|---|---|---|---|']
    for name, col in (('DK no-vig', 'nv_over'), ('champion c3ab760178', 'p_model_over'), (f'challenger {h}', 'p_chal_over')):
        p = G[col].values; row = f'| {name} | {ll(p).mean():.4f} | {((p - o) ** 2).mean():.4f} |'
        if col == 'nv_over': row += ' – | – | – |'
        else:
            over = p > G.nv_over.values; hit = np.where(over, o, 1 - o); imp = np.where(over, G.nv_over, 1 - G.nv_over)
            row += f' {f(boot_diff(ll(p) - ll(G.nv_over.values), gid))} | {f(boot_diff(np.where(over, zc, -zc), gid))} | {hit.mean():.3f} vs {imp.mean():.3f} |'
        L.append(row)
    dll = boot_diff(ll(G.p_chal_over.values) - ll(G.p_model_over.values), gid)
    oc, och = G.p_chal_over.values > G.nv_over.values, G.p_model_over.values > G.nv_over.values
    dz = boot_diff(np.where(oc, zc, -zc) - np.where(och, zc, -zc), gid)
    L += ['', f'**Primary 1 (log-loss, challenger - champion):** {f(dll)} over {dll[4]} games. Pass needs the upper bound < 0.',
          f'**Primary 2 (lean z-CLV, challenger - champion):** {f(dz)}. Pass needs the lower bound > 0.',
          f'Window/decision rules: see the prereg. Fewer than {300} lines or {60} games = INCONCLUSIVE, report only.']
open(os.path.join(HERE, 'SHADOW_REPORT.md'), 'w').write('\n'.join(L) + '\n'); print('\n'.join(L))
