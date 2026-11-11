"""Grid-tune on 2024 only (MAE vs closing spread, both teams>=4 games); 2025/2026 stay out-of-sample."""
import itertools, numpy as np
from backtest import run
from model import P
res = []
for hl, rd, cap, hfa in itertools.product([45, 90, 180], [1, 3, 6], [21, 35], [2.0, 3.0]):
    p = dict(P, HALF_LIFE_DAYS=hl, RIDGE=rd, MOV_CAP=cap, HFA=hfa)
    rows = [r for r in run([2024], p) if r['min_games'] >= 4]
    m = np.mean([abs(r['model_spread'] - r['close_spread']) for r in rows])
    res.append((m, hl, rd, cap, hfa)); print(f'{m:.3f} hl={hl} ridge={rd} cap={cap} hfa={hfa}', flush=True)
print('BEST', min(res))
