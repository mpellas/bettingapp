"""Freeze the challenger (does NOT touch models/CURRENT or the champion files).
Recipe (identical to evaluate.py's): trees by early stopping, training seasons <= 2024-25 -> validation 2025-26;
k fit out-of-sample on those 2025-26 predictions; final booster refit on ALL rows (n_prior >= 5) dated <= CUTOFF
with that tree count. Hash = sha256(model text)[:10] (same convention as freeze.py).
-> challenger/models/model_<hash>.txt + .json"""
from common import *
import hashlib, datetime as dt
CUTOFF = pd.Timestamp(sys.argv[1] if len(sys.argv) > 1 else '2026-10-16')
sel = json.load(open(os.path.join(HERE, 'selection.json'))); CH = sel['features']
df = build(); df = df[(df.n_prior >= 5) & (df.date <= CUTOFF)]
tr2, va = df[df.season <= 2024], df[df.season == 2025]
m2, it = fit(tr2, va, CH); k = fit_k(va.shots.values, m2.predict(va[CH]))
m, _ = fit(df, None, CH, it)
txt = m.model_to_string(); h = hashlib.sha256(txt.encode()).hexdigest()[:10]
os.makedirs(os.path.join(HERE, 'models'), exist_ok=True)
open(os.path.join(HERE, 'models', f'model_{h}.txt'), 'w').write(txt)
meta = dict(hash=h, k=k, k_source='out-of-sample, 2025-26 predictions of the <=2024-25 model', features=CH, trees=it,
            trained_through=str(df.date.max().date()), rows=len(df), params=P, groups=sel['groups_chosen'],
            frozen_at_pt=dt.datetime.now().astimezone().isoformat(timespec='seconds'),
            data_sha1={f: hashlib.sha1(open(os.path.join(ROOT, f), 'rb').read()).hexdigest() for f in
                       ['data/s2021.pkl', 'data/s2022.pkl', 'data/s2023.pkl', 'data/s2024.pkl', 'data/s2025.pkl', 'data/s2026.pkl', 'challenger/team_games.pkl']})
json.dump(meta, open(os.path.join(HERE, 'models', f'model_{h}.json'), 'w'), indent=1, default=float)
print(h, it, round(k, 3), len(df), meta['trained_through'])
