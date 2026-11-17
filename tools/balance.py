import sys
from html.parser import HTMLParser
VOID={'br','img','meta','link','input','hr','source','wbr','col'}
class P(HTMLParser):
    def __init__(s):
        super().__init__(convert_charrefs=True); s.st=[]; s.bad=[]
    def handle_starttag(s,t,a):
        if t in VOID: return
        if t=='p' and s.st and s.st[-1][0]=='p': s.st.pop()
        s.st.append((t,s.getpos()[0],dict(a).get('class','')))
    def handle_endtag(s,t):
        if t in VOID: return
        if not s.st: s.bad.append(('stray close',t,s.getpos()[0])); return
        if s.st[-1][0]!=t:
            for i in range(len(s.st)-1,-1,-1):
                if s.st[i][0]==t:
                    for j in range(len(s.st)-1,i,-1):
                        s.bad.append(('never closed',s.st[j][0],s.st[j][1]))
                    del s.st[i:]; return
            s.bad.append(('stray close',t,s.getpos()[0])); return
        s.st.pop()
ok=True
for f in sys.argv[1:]:
    p=P(); p.feed(open(f).read())
    probs=p.bad+[('open at EOF',t,ln) for t,ln,_ in p.st]
    if probs:
        ok=False; print(f"  {f}: UNBALANCED")
        for k,t,ln in probs: print(f"     line {ln}: {k} <{t}>")
    else: print(f"  {f}: balanced")
sys.exit(0 if ok else 1)
