import json,glob,collections
def p(a): a=float(a); return -a/(-a+100) if a<0 else 100/(a+100)
st=collections.Counter(); ex=[]
for f in glob.glob('in/captures/2026*/*.json'):
    try: d=json.load(open(f))
    except: continue
    if not isinstance(d,dict) or 'raw' not in d: continue
    ms={}
    for r in d['raw']:
        if r['type']=='Shots on Goal Milestones': ms.setdefault(r['espn_id'],{})[r['target']]=r['american']
    for L in d.get('sog_lines',[]):
        if L['side_method']!='order_fallback': st['ms_conf']+=1; continue
        m=ms.get(L['espn_id'],{}).get(L['line']+0.5)
        if m is None: st['fb_no_ms']+=1; continue
        do,du=abs(p(m)-p(L['over'])),abs(p(m)-p(L['under']))
        k='fb_both_equal' if L['over']==L['under']==m else ('fb_closer_over' if do<du else 'fb_closer_under' if du<do else 'fb_tie')
        st[k]+=1
        if len(ex)<8 and k=='fb_closer_under': ex.append((f,L['player'],L['line'],L['over'],L['under'],m))
print(st); [print(e) for e in ex]
