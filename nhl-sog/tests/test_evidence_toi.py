"""TOI evidence vote (2026-10-20): last 5 vs THIS SEASON only; vote needs >= 1.0 min gap and >= 5 season games;
last 30 (mixes last season early on) is display only. Lee Oct 19: last 5 14.02 vs season 13.31 (+0.7) -> no vote."""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pandas as pd
import evidence, shrink
L = shrink.gamelogs(); st = evidence.season_toi(8475314, '2026-10-19', L)
assert abs(st - 13.311) < 0.01, st
base = dict(nv_over=0.5, p_model_over=0.55, opp_slot_ratio=1.0)
r = dict(base, fresh_toi_r5=14.02, toi_r30=15.4778)
s, why = evidence.score_side(r, 'over', s_toi=st); assert s['toi'] == 0, s
assert '+0.7' in why['toi'] and 'last 30 incl. last season 15.5' in why['toi'], why['toi']
# Oct 20 Fliff unders: last-30 says big drop, season says < 1.0 except LaCombe (-2.0)
for name, t5, season, t30, want in [('DeAngelo', 15.5, 16.3, 19.4, 0), ('LaCombe', 23.8, 25.8, 24.2, 1),
                                    ('Protas', 16.1, 16.2, 17.4, 0), ('Rielly', 18.5, 19.4, 19.8, 0), ('Marchenko', 17.7, 18.6, 19.3, 0)]:
    s, w = evidence.score_side(dict(base, fresh_toi_r5=t5, toi_r30=t30), 'under', s_toi=season)
    assert s['toi'] == want, (name, s['toi'], w['toi'])
    s, _ = evidence.score_side(dict(base, fresh_toi_r5=t5, toi_r30=t30), 'over', s_toi=season); assert s['toi'] == -want
# exactly 1.0 below counts
assert evidence.score_side(dict(base, fresh_toi_r5=15.0), 'under', s_toi=16.0)[0]['toi'] == 1
# fewer than 5 season games -> nan baseline -> no vote (no last-30 fallback)
g = pd.DataFrame(dict(playerId=[1]*34, gameDate=['2026-03-01']*30 + ['2026-10-0%d' % i for i in range(1, 5)],
                      timeOnIcePerGame=[1500]*30 + [900]*4))
assert np.isnan(evidence.season_toi(1, '2026-10-20', g))
s, w = evidence.score_side(dict(base, fresh_toi_r5=15.0, toi_r30=25.0), 'under', s_toi=evidence.season_toi(1, '2026-10-20', g))
assert s['toi'] == 0 and 'n/a' in w['toi'], w
print('ok:', why['toi'])
