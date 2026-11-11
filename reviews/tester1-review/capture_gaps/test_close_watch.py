"""Simulated missing closing snapshot: close_watch must flag it and the retry wrapper must survive transient errors."""
import json, os, tempfile, datetime as dt, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import close_watch as cw
NOW = dt.datetime(2026, 10, 26, 5, 0, tzinfo=dt.timezone.utc)
def snap(d, eid, tag, mins, start='2026-10-26T02:00Z'):
    os.makedirs(f'{d}/archive', exist_ok=True)
    json.dump({'event': eid, 'name': f'G{eid}', 'start_utc': start, 'minutes_to_start': mins, 'tag': tag, 'sog_lines': [{'line': 2.5}]},
              open(f'{d}/archive/{eid}_{tag}_{abs(int(mins*100)):06d}.json', 'w'))
def test_flags_missing_close():
    with tempfile.TemporaryDirectory() as root:
        d = f'{root}/captures/20261025'
        snap(d, 'A', 'D', 180); snap(d, 'A', 'C', 12)          # good game: close in window
        snap(d, 'B', 'D', 175)                                  # simulated gap: D only, no C
        snap(d, 'C', 'D', 170); snap(d, 'C', 'C', 35)           # C taken but outside 0-30 window
        snap(d, 'F', 'D', 180, start='2026-10-26T09:00Z')       # future game: not judged yet
        sched = lambda date: {e: ('G' + e, '2026-10-26T02:00Z') for e in 'ABC'} | {'F': ('GF', '2026-10-26T09:00Z'),
                                 'E': ('GE', '2026-10-26T01:00Z')}  # E: on ESPN schedule, no files at all (outage)
        R = {r['event']: r['status'] for r in cw.check(root, ['20261025'], sched, NOW)}
        assert R == {'A': 'OK', 'B': 'NO_IN_WINDOW_SNAPSHOT', 'C': 'NO_IN_WINDOW_SNAPSHOT', 'E': 'NO_FILES'}, R
        assert {r['event'] for r in cw.check(root, ['20261025'], None, NOW)} == {'A', 'B', 'C'}  # offline: disk games only
        out = f'{root}/alerts'; rows = cw.check(root, ['20261025'], sched, NOW)
        new = cw.alert(rows, out); assert len(new) == 3 and all(m.startswith('!!! CLOSE SNAPSHOT MISSING') for m in new)
        assert cw.alert(rows, out) == []                        # deduped: alert posts once per game
def test_retry_survives_transient(monkeypatch=None):
    import requests
    calls = {'n': 0}; real = requests.get
    class Ok:
        def raise_for_status(self): pass
        def json(self): return {'events': []}
    def flaky(*a, **k):
        calls['n'] += 1
        if calls['n'] < 3: raise requests.ConnectionError('simulated drop')
        return Ok()
    requests.get = flaky
    try: assert cw.get_json('x', _sleep=lambda s: None) == {'events': []} and calls['n'] == 3
    finally: requests.get = real
    requests.get = lambda *a, **k: (_ for _ in ()).throw(requests.Timeout('down'))
    try:
        try: cw.get_json('x', tries=3, _sleep=lambda s: None); raise AssertionError('should raise after retries')
        except requests.Timeout: pass
    finally: requests.get = real
if __name__ == '__main__':
    test_flags_missing_close(); test_retry_survives_transient(); print('2 tests passed')
