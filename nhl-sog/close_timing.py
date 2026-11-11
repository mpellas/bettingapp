"""Game-level close timing / 'early close' tag (added 2026-10-17, room request after BOS@LA 401892530).
Read-only over captures/<date>/archive (via close.snaps); never rewrites captures, CLOSE.json or graded CSVs, and does
not change close.py / grade.py (both are hash-pinned in challenger/PREREG_3386583f18.md).
For each game, m = minutes before puck drop of the LAST snapshot in the 0-30 min close window that has any line:
  early_close  m > EARLY_MIN and a LATER in-window snapshot came back with 0 lines: the book pulled the board early.
               The per-line close close.py picked is then really a ~m-minute-early price. grade_report.py keeps these
               rows OUT of every CLV / closing-line number and reports them on their own; win/loss still graded.
  capture_gap  m > EARLY_MIN and NO later snapshot at all (our capture stopped, e.g. box paused). Info only: still in
               CLV, listed on its own line in the report so it can be judged separately.
  legacy_unknown  day without archive/ (Oct 11-15): only the surviving main file is known, so timing can't be judged. Info only.
  on_time      m <= EARLY_MIN.   no_lines: no in-window snapshot with lines (grade.py already VOIDs those rows).
Usage: python3 close_timing.py [YYYYMMDD ...]   (capture dirs, UTC dates; default all) -> prints + graded/close_timing.csv"""
import glob, os, sys, csv
import close
EARLY_MIN = 5   # minutes; C cadence near puck drop is ~4 min, so a healthy last snapshot is 0-5 min out
def timing(d, eid):
    S, legacy = close.snaps(d, eid)
    if not S: return None
    inw = [s for s in S if close.WIN[0] <= s['minutes_to_start'] <= close.WIN[1]]
    has = [s for s in inw if any(s.get(m) for m in close.MKTS)]
    r = {'capture_dir': os.path.basename(d), 'event': str(eid), 'name': S[0].get('name'), 'start_utc': S[0].get('start_utc'),
         'legacy_no_archive': legacy, 'n_in_window': len(inw), 'n_in_window_with_lines': len(has)}
    if not has: return dict(r, close_timing='no_lines', last_lines_min=None, early_close=False, early_close_min=None)
    last = max(has, key=lambda s: s['captured_utc']); m = round(float(last['minutes_to_start']), 1)
    later = [s for s in inw if s['captured_utc'] > last['captured_utc']]
    t = 'on_time' if m <= EARLY_MIN else ('legacy_unknown' if legacy else 'early_close' if later else 'capture_gap')  # legacy: only the last main file survived
    return dict(r, close_timing=t, last_lines_min=m, last_lines_utc=last['captured_utc'], n_empty_after=len(later),
                early_close=t == 'early_close', early_close_min=m if t == 'early_close' else None)
def all_games(dates=None):
    out = {}
    for d in sorted(glob.glob('captures/2*/')):
        d = d.rstrip('/')
        if dates and os.path.basename(d) not in dates: continue
        for e in sorted({os.path.basename(f).split('_')[0] for f in glob.glob(f'{d}/*_*.json') + glob.glob(f'{d}/archive/*.json')}):
            if not e.isdigit(): continue
            r = timing(d, e)
            if r: out[e] = r
    return out
if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    T = all_games(set(sys.argv[1:]) or None)
    cols = ['capture_dir', 'event', 'name', 'start_utc', 'close_timing', 'last_lines_min', 'early_close', 'early_close_min', 'n_in_window', 'n_in_window_with_lines', 'n_empty_after', 'legacy_no_archive']
    if not sys.argv[1:]:
        with open('graded/close_timing.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, cols, extrasaction='ignore'); w.writeheader(); [w.writerow(r) for r in T.values()]
    for r in T.values():
        if r['close_timing'] != 'on_time': print(r['capture_dir'], r['event'], r['name'], r['close_timing'], r['last_lines_min'], 'LEGACY' if r['legacy_no_archive'] else '')
