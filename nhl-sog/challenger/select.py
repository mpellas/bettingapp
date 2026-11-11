"""Stage A: feature-group selection on PAST seasons only. Train 2021-22..2023-24, validate 2024-25.
Greedy forward over cfeatures.GROUPS starting from the champion's feature list; a group is accepted only if the
validation NB log-likelihood gain is > 0 with a game-clustered bootstrap 95% lower bound > 0.
Then the dispersion test: one k vs k per position (D/F), k fit out-of-sample on the validation half split by game.
Writes challenger/selection.json."""
from common import *
df = build(); df = df[df.n_prior >= 5]
tr, va = df[df.season <= 2023], df[df.season == 2024]
y = va.shots.values
def score(feats):
    m, it = fit(tr, va, feats); mu = m.predict(va[feats])
    # k fit on even-numbered validation games, scored everywhere (k barely moves; avoids in-sample k on training rows)
    ev = (va.gameId % 2 == 0).values; k = fit_k(y[ev], mu[ev])
    return nb_ll(y, mu, k), it, k
base_ll, base_it, base_k = score(CHAMP)
log = [dict(step='baseline (champion features)', n_feats=len(CHAMP), val_ll=float(base_ll.mean()), trees=base_it, k=base_k)]
print(log[-1], flush=True)
chosen, cur_ll, cur = [], base_ll, list(CHAMP)
remaining = list(C.GROUPS)
while remaining:
    trials = {}
    for gname in remaining:
        ll, it, k = score(cur + C.GROUPS[gname])
        m, lo, hi, n, ng = boot_diff(ll - cur_ll, va.gameId.values)
        trials[gname] = dict(gain=m, lo=lo, hi=hi, trees=it, k=k, ll=ll)
        print(f'  try +{gname}: gain {m:+.5f} [{lo:+.5f}, {hi:+.5f}] trees {it}', flush=True)
    best = max(trials, key=lambda g: trials[g]['gain']); t = trials[best]
    log.append(dict(step=f'round {len(chosen)+1}', tried={g: {kk: v for kk, v in tt.items() if kk != 'll'} for g, tt in trials.items()}, best=best))
    if t['lo'] <= 0: log[-1]['decision'] = f'stop: best group {best} lower bound {t["lo"]:+.5f} <= 0'; print(log[-1]['decision']); break
    chosen.append(best); cur += C.GROUPS[best]; cur_ll = t['ll']; remaining.remove(best)
    log[-1]['decision'] = f'accept {best}'; print('accept', best, flush=True)
# dispersion: per-position k
m, it = fit(tr, va, cur); mu = m.predict(va[cur]); ev = (va.gameId % 2 == 0).values; od = ~ev
k1 = fit_k(y[ev], mu[ev]); k2 = fit_k(y[ev], mu[ev], va.D.values[ev])
d = nb_ll(y[od], mu[od], karr(k2, va.D.values[od])) - nb_ll(y[od], mu[od], k1)
dm, dlo, dhi, n, ng = boot_diff(d, va.gameId.values[od])
disp = dict(k_single=k1, k_by_D=k2, gain_odd_games=dm, ci=[dlo, dhi], accept=bool(dlo > 0))
poisson_gain = boot_diff(nb_ll(y[od], mu[od], k1) - stats.poisson.logpmf(y[od], mu[od]), va.gameId.values[od])
json.dump(dict(groups_chosen=chosen, features=cur, trees_inner=it, dispersion=disp,
               nb_vs_poisson_gain=poisson_gain[:3], log=log), open(os.path.join(HERE, 'selection.json'), 'w'), indent=1, default=float)
print('chosen', chosen, 'dispersion', disp, 'NB vs Poisson', poisson_gain[:3])
