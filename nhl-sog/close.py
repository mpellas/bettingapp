"""Per-line close (C) build, same definition as the NFL track.
For each line key (player espn_id, market, point), the close is its LATEST price among snapshots taken
0-30 min before puck drop (minutes_to_start in [0,30]). Snapshots outside that window (e.g. 35 min out) never count.
A line seen in D or any earlier snapshot but absent from every in-window snapshot is logged pulled_before_close;
it is never backfilled from an earlier snapshot.
Sources: captures/<date>/archive/<eid>_*_HHMMSS.json (every snapshot). Legacy days without an archive fall back to
the surviving <eid>_C.json / <eid>_D.json / <eid>_ADHOC.json files (only what survived; noted in output as legacy).
Writes captures/<date>/<eid>_CLOSE.json.  Usage: python3 close.py YYYYMMDD [eid]"""
import json,glob,os,sys
WIN=(0,30); MKTS={'sog_lines':'sog','saves_lines':'saves'}
def key(m,l): return (str(l.get('espn_id')),m,float(l['line']))
def snaps(d,eid):
    a=glob.glob(f'{d}/archive/{eid}_*.json'); legacy=not a
    fs=a or glob.glob(f'{d}/{eid}_*.json')
    out=[json.load(open(f)) for f in fs if not f.endswith('_CLOSE.json')]
    return sorted(out,key=lambda s:s['captured_utc']),legacy
def build(d,eid):
    S,legacy=snaps(d,eid)
    if not S: return None
    inw=[s for s in S if WIN[0]<=s['minutes_to_start']<=WIN[1]]
    first_in=min((s['captured_utc'] for s in inw),default=None)
    close,seen={},{}
    for s in S:
        for m,mk in MKTS.items():
            for l in s.get(m) or []:
                k=key(mk,l)
                if s in inw: close[k]=dict(l,market=mk,close_captured_utc=s['captured_utc'],close_minutes_to_start=s['minutes_to_start'])
                elif first_in is None or s['captured_utc']<first_in: seen.setdefault(k,dict(l,market=mk,last_seen_utc=s['captured_utc'],last_seen_minutes=s['minutes_to_start']))
                if k in seen and s not in inw: seen[k].update(last_seen_utc=s['captured_utc'],last_seen_minutes=s['minutes_to_start'])
    pulled=[dict(v,status='pulled_before_close') for k,v in seen.items() if k not in close] if inw else []
    r={'event':eid,'name':S[0].get('name'),'start_utc':S[0].get('start_utc'),'window_min':WIN,'legacy_no_archive':legacy,
       'n_snapshots':len(S),'n_in_window':len(inw),'status':'OK' if inw else 'NO_IN_WINDOW_SNAPSHOT',
       'closed':[dict(v,status='closed') for v in close.values()],'pulled_before_close':pulled}
    json.dump(r,open(f'{d}/{eid}_CLOSE.json','w'),indent=1); return r
def build_day(date,only=None):
    d=f'captures/{date}'; eids=sorted({os.path.basename(f).split('_')[0] for f in glob.glob(f'{d}/*_*.json')+glob.glob(f'{d}/archive/*.json')})
    return {e:build(d,e) for e in eids if not only or e==only}
if __name__=='__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    for e,r in build_day(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else None).items():
        if r: print(e,r['name'],r['status'],f"snaps={r['n_snapshots']} in_window={r['n_in_window']} closed={len(r['closed'])} pulled={len(r['pulled_before_close'])}"+(' LEGACY(no archive)' if r['legacy_no_archive'] else ''))
