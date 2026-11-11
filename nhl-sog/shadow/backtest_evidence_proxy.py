"""PROXY backtest of evidence agreement on 2025-26 (no market lines exist for that season in our data).
Champion recipe and challenger features trained on seasons < 2025 (trees by early stopping on 2024-25 from a <2024 model,
same as challenger/evaluate.py). Synthetic line L = floor(mu_champ) + 0.5; side = champion's lean at L; reference
probability = champion P(side). Four market-free signals (bands as in evidence.py):
  chal   : challenger P(side) - champion P(side)  (+/-0.5 pt)
  shrunk : NB(shr_mu, k_champ) P(side) - champion P(side) (+/-0.5 pt)
  toi    : toi_r5 - toi_r30 (+/-0.5 min; live uses season mean, proxy uses r30)
  opp    : opponent shots allowed to the player's slot / league (+/-3%)
Question: does hit - P_champ(side) rise with the number of agreeing signals? This is calibration of the champion's lean
conditional on agreement, NOT profit vs a market price."""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'challenger'))
from common import *
CH = json.load(open(os.path.join(ROOT, 'challenger', 'selection.json')))['features']
DF = build(); df = DF[DF.n_prior >= 5]; S = 2025
def recipe(feats):
    tr_all = df[df.season < S]; tr2 = tr_all[tr_all.season < S - 1]; va = tr_all[tr_all.season == S - 1]
    m2, it = fit(tr2, va, feats); m, _ = fit(tr_all, None, feats, it)
    return m, fit_k(tr_all.shots.values, m.predict(tr_all[feats])), fit_k(va.shots.values, m2.predict(va[feats]))
mc, kc, _ = recipe(CHAMP); mx, _, kx = recipe(CH)
te = df[df.season == S].copy(); te['mu_c'] = mc.predict(te[CHAMP]); te['mu_x'] = mx.predict(te[CH])
te['L'] = np.floor(te.mu_c) + 0.5
pc = p_over(te.L.values, te.mu_c.values, kc); px = p_over(te.L.values, te.mu_x.values, kx)
ps = p_over(te.L.values, te.shr_mu.fillna(te.mu_c).values, kc)
ov = pc >= 0.5; sgn = np.where(ov, 1, -1)
side = lambda p: np.where(ov, p, 1 - p)
te['p_side'] = side(pc); te['hit'] = np.where(ov, te.shots > te.L, te.shots < te.L).astype(int)
def band(v, b): return np.where(v > b, 1, np.where(v < -b, -1, 0))
te['s_chal'] = band(side(px) - side(pc), 0.005); te['s_shr'] = band(side(ps) - side(pc), 0.005)
te['s_toi'] = sgn * band((te.toi_r5 - te.toi_r30).fillna(0).values, 0.5)
te['s_opp'] = sgn * band((te.opp_slot_ratio_r20.fillna(1) - 1).values, 0.03)
sc = ['s_chal', 's_shr', 's_toi', 's_opp']; te = te.copy(); te['agree'] = (te[sc] == 1).sum(1); te['against'] = (te[sc] == -1).sum(1)
te['res'] = te.hit - te.p_side
print(f'2025-26 proxy: {len(te)} player-games, {te.gameId.nunique()} games; k champ {kc:.2f}, k chal {kx:.2f}; overs {ov.mean():.0%}')
print('| agreeing signals (of 4) | n | games | hit | champion P(side) | hit - P (pts) |'); print('|---|---|---|---|---|---|')
for a in range(5):
    s = te[te.agree == a]
    if len(s) < 50: print(f'| {a} | {len(s)} | | too few |'); continue
    r = boot_diff(s.res.values, s.gameId.values)
    print(f'| {a} | {len(s)} | {s.gameId.nunique()} | {s.hit.mean():.3f} | {s.p_side.mean():.3f} | {r[0]*100:+.2f} [{r[1]*100:+.2f}, {r[2]*100:+.2f}] |')
for lab, s in [('agree >= 3', te[te.agree >= 3]), ('agree <= 2', te[te.agree <= 2]), ('net (agree - against) >= 2', te[te.agree - te.against >= 2]), ('net <= -1', te[te.agree - te.against <= -1])]:
    r = boot_diff(s.res.values, s.gameId.values)
    print(f'| {lab} | {len(s)} | {s.gameId.nunique()} | {s.hit.mean():.3f} | {s.p_side.mean():.3f} | {r[0]*100:+.2f} [{r[1]*100:+.2f}, {r[2]*100:+.2f}] |')
print('\nper signal: hit - P when + / 0 / -')
for c in sc:
    out = []
    for v in (1, 0, -1):
        s = te[te[c] == v]; r = boot_diff(s.res.values, s.gameId.values) if len(s) > 50 else (np.nan,) * 3
        out.append(f'{"+0-"[1 - v]} n={len(s)} {r[0]*100:+.2f} [{r[1]*100:+.2f}, {r[2]*100:+.2f}]')
    print(f'  {c:7s}', ' | '.join(out))
te[['gameId', 'playerId', 'L', 'p_side', 'hit', 'agree', 'against'] + sc].to_csv(os.path.join(ROOT, 'shadow', 'backtest_evidence_proxy_rows.csv'), index=False)
