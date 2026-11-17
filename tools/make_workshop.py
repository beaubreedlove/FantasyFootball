#!/usr/bin/env python3
"""Workshop build: team picker drives the page. Live page is untouched.

Per spec: drop the "where each line falls" card, put a picker at the top,
highlight the chosen team in the standings and in the prize boards, and show
only that team in the clinching and elimination sections.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "page_w10.html")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "workshop_w10.html")

src = open(SRC).read()
STAND = json.load(open(os.path.join(HERE, "S_w10.json")))
TEAMS = [r[0] for r in STAND]


def card_span(s, start):
    depth, i = 0, start
    while True:
        o, c = s.find("<div", i), s.find("</div>", i)
        assert c != -1
        if o != -1 and o < c:
            depth += 1
            i = o + 4
        else:
            depth -= 1
            i = c + 6
            if depth == 0:
                return start, i


# ---- 1. drop the cutoff card ----
i = src.index('<div class="card"><h3>Where each line falls</h3>')
a, b = card_span(src, i)
src = src[:a] + src[b:]
assert "Where each line falls" not in src

# ---- 1b. drop the "not Yahoo's order" card ----
i = src.index('<div class="card"><h3>This order is not Yahoo\'s order</h3>')
a, b = card_span(src, i)
src = src[:a] + src[b:]
assert "not Yahoo" not in src

# ---- 2. the picker, directly under the header ----
picker = """  <div class="picker">
    <label for="teamsel">Team</label>
    <select id="teamsel"><option value="" disabled selected>Select your team\u2026</option></select>
  </div>
</header>"""
assert "</header>" in src
src = src.replace("</header>", picker, 1)

css = """  .picker{display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-top:18px;}
  .picker label{font-size:11px; letter-spacing:.09em; text-transform:uppercase;
                color:var(--muted); font-weight:600;}
  .picker select{font:inherit; font-size:15px; padding:9px 12px; border-radius:9px;
                 border:1px solid var(--line); background:var(--surface);
                 color:var(--ink); max-width:100%;}
  .picker select:focus-visible{outline:2px solid var(--accent); outline-offset:2px;}
  .is-hidden{display:none !important;}
  /* "this is you" needs to read as neither the teal accent nor the rust warn,
     since warn already means eliminated on this page */
  :root{--you:#16A34A;}
  @media (prefers-color-scheme:dark){ :root{--you:#4ADE80;} }
  :root[data-theme="dark"]{--you:#4ADE80;}
  :root[data-theme="light"]{--you:#16A34A;}
  #stand tbody tr{cursor:pointer;}
  #stand tbody tr.sel{outline:2.5px solid var(--you); outline-offset:-2px;
                      border-radius:10px;}
  #stand tbody tr.sel td.team{color:var(--you);}
  #prizes ol.rank li.sel{font-weight:600; color:var(--ink);}
  #prizes ol.rank li.sel::marker{font-weight:600; color:var(--you);}
  .prompt{font-size:14px; color:var(--muted); font-style:italic; padding:2px 0 0;}
"""
anchor = "  .mini{"
assert anchor in src
src = src.replace(anchor, css + anchor, 1)

# ---- 3. data-team hooks on the rendered rows ----
subs = [
    ('`<tr data-team="${r[0]}" class="${i===6?\'cut\':\'\'}">',
     '`<tr data-team="${r[0]}" class="${i===6?\'cut\':\'\'}">'),
    ('`<tr class="${i===6?\'cut\':\'\'}"><td class="team" data-l="Team">${r[0]}',
     '`<tr data-team="${r[0]}" class="${i===6?\'cut\':\'\'}"><td class="team" data-l="Team">${r[0]}'),
    ('return `<div class="row"><h3>${v.name}',
     'return `<div class="row" data-team="${v.name}"><h3>${v.name}'),
    ('`<div class="card ${c}"><h3>${n}',
     '`<div class="card ${c}" data-team="${n}"><h3>${n}'),
    ('<ol class="rank">${items.map(i=>`<li>${i}</li>`).join("")}</ol>',
     '<ol class="rank">${items.map(i=>`<li data-team="${TEAMNAME(i)}">${i}</li>`).join("")}</ol>'),
]
for old, new in subs:
    if old in src and old != new:
        src = src.replace(old, new, 1)

if "function TEAMNAME" not in src:
    m = 'document.getElementById("stand").innerHTML=S.map((r,i)=>'
    assert m in src
    src = src.replace(m, (
        "const TEAMS_LONGEST=S.map(r=>r[0]).slice().sort((a,b)=>b.length-a.length);\n"
        "function TEAMNAME(s){for(const t of TEAMS_LONGEST){if(s.indexOf(t)===0)return t;}"
        "return \"\";}\n") + m, 1)

# ---- 4. the filter ----
filt = """
(function(){
  const sel=document.getElementById("teamsel");
  if(!sel) return;
  const names=S.map(r=>r[0]);
  for(const n of names.slice().sort((a,b)=>a.localeCompare(b))){
    const o=document.createElement("option"); o.value=n; o.textContent=n;
    sel.appendChild(o);
  }
  const sectionOf=id=>{
    const e=document.getElementById(id);
    return e?e.closest("section"):null;
  };
  const SEC={clin:sectionOf("clin"), help:sectionOf("help"), prizes:sectionOf("prizes")};
  function apply(team){
    document.querySelectorAll("#stand tbody tr").forEach(tr=>
      tr.classList.toggle("sel", !!team && tr.dataset.team===team));
    document.querySelectorAll("#prizes ol.rank li").forEach(li=>
      li.classList.toggle("sel", !!team && li.dataset.team===team));
    ["#clin .row","#help .card"].forEach(q=>
      document.querySelectorAll(q).forEach(el=>
        el.classList.toggle("is-hidden", !!team && el.dataset.team!==team)));
    // nothing chosen yet: standings only
    for(const k of ["clin","help","prizes"])
      if(SEC[k]) SEC[k].classList.toggle("is-hidden", !team);
    // a team with no elimination card gets no elimination section at all
    if(team && SEC.help){
      const any=document.querySelector("#help .card:not(.is-hidden)");
      SEC.help.classList.toggle("is-hidden", !any);
    }
  }
  let init="";
  try{ init=new URLSearchParams(location.search).get("team")
            || localStorage.getItem("ffteam") || ""; }catch(e){}
  if(names.indexOf(init)<0) init="";
  if(init) sel.value=init;
  apply(init);
  function choose(t){
    sel.value=t;
    try{ localStorage.setItem("ffteam",t); }catch(e){}
    try{
      const u=new URL(location.href);
      u.searchParams.set("team",t);
      history.replaceState(null,"",u);
    }catch(e){}
    apply(t);
  }
  sel.addEventListener("change",()=>choose(sel.value));
  document.querySelectorAll("#stand tbody tr").forEach(tr=>{
    tr.addEventListener("click",()=>{ if(tr.dataset.team) choose(tr.dataset.team); });
  });
})();
</script>"""
cut = src.rfind("</script>")
tail = src[cut + len("</script>"):]          # </body></html> must survive
src = src[:cut] + filt + tail

src = src.replace("<title>Playoff Picture — Week 10 Report</title>",
                  "<title>Playoff Picture — Week 10 (workshop)</title>", 1)

for sec in ("stand", "clin", "help", "prizes"):
    assert f'id="{sec}"' in src, f"lost #{sec}"
assert 'id="teamsel"' in src
open(OUT, "w").write(src)
print(f"wrote {OUT} ({len(src):,} bytes) · {len(TEAMS)} teams in the picker")
