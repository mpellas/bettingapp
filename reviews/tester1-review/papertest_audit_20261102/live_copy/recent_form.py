"""Recent-form filter for the Fliff list (approved by yinzerduck 2026-10-16).

Recent expected shots = sog60_r10 * toi_r5 / 60. A side passes only if the Poisson
probability implied by that rate beats the no-vig probability for that side:
  over at line L : P(X > L) > nv_over
  under at line L: P(X < L) > 1 - nv_over
(Previously a side only needed the rate on the right side of the line.)
Thin edge: thin_edge_over/under = model or recent margin over no-vig < 1 point (needs p_model_over).
Does not touch the frozen model's probabilities.
Usage: python recent_form.py picks/20261016_D.csv [out.csv]
"""
import math, sys
import pandas as pd

def pois_cdf(k, mu):
    return sum(math.exp(-mu) * mu**i / math.factorial(i) for i in range(int(k) + 1)) if k >= 0 else 0.0

def recent_mu(r):
    return r.sog60_r10 * r.toi_r5 / 60.0

def p_recent(r, side):
    mu, L = recent_mu(r), float(r.line)
    if side == 'over':  # P(X > L)
        return 1 - pois_cdf(math.floor(L), mu)
    return pois_cdf(math.ceil(L) - 1, mu)  # P(X < L)

def nv(r, side):
    return r.nv_over if side == 'over' else 1 - r.nv_over

def recent_form_pass(r, side):
    return p_recent(r, side) > nv(r, side)

THIN = 0.01  # thin-edge rule (approved 2026-10-16): a side is Skipped if model or recent beats no-vig by < 1 point

def thin_edge(model_margin, recent_margin):
    """True if model P - no-vig P, or p_recent - no-vig P, is under 1 point (negative margins count)."""
    return model_margin < THIN or recent_margin < THIN

RECENT_WINDOWS = 'shot rate last 10 x TOI last 5'  # label shown on cards (2026-10-24); gate formula unchanged

def last5(df):
    """DISPLAY ONLY (2026-10-24, tester request): actual shots in the player's last 5 games before the slate date
    (data/s2026.pkl, gameDate < slate), so cards show the real count next to the model %. Not used by any status rule."""
    try:
        h = pd.read_pickle('data/s2026.pkl')
        slate = pd.to_datetime(df.captured_utc, utc=True).dt.tz_convert('America/Los_Angeles').dt.strftime('%Y-%m-%d')
        out = []
        for pid, d in zip(df.nhl_id, slate):
            g = h[(h.playerId == pid) & (h.gameDate < d)].sort_values('gameDate').tail(5)
            out.append(','.join(str(int(x)) for x in g.shots))
        return out
    except Exception as e:
        print('last5 skipped:', e); return [''] * len(df)

def annotate(df):
    df = df.copy()
    if 'nhl_id' in df and 'captured_utc' in df: df['last5_shots'] = last5(df)
    df['recent_windows'] = RECENT_WINDOWS
    df['recent_mu'] = df.apply(recent_mu, axis=1)
    for s in ('over', 'under'):
        df[f'p_recent_{s}'] = df.apply(lambda r: p_recent(r, s), axis=1)
        df[f'recent_pass_{s}'] = df.apply(lambda r: recent_form_pass(r, s), axis=1)
        if 'p_model_over' in df:
            pm = df.p_model_over if s == 'over' else 1 - df.p_model_over
            nvs = df.nv_over if s == 'over' else 1 - df.nv_over
            df[f'thin_edge_{s}'] = [thin_edge(a, b) for a, b in zip(pm - nvs, df[f'p_recent_{s}'] - nvs)]
    return df

if __name__ == '__main__':
    d = annotate(pd.read_csv(sys.argv[1]))
    if len(sys.argv) > 2: d.to_csv(sys.argv[2], index=False)
    print(d[['player','line','nv_over','recent_mu','p_recent_over','recent_pass_over','p_recent_under','recent_pass_under']].round(3).to_string())
