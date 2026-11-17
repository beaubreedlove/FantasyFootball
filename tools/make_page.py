#!/usr/bin/env python3
"""Assemble the week-10 page from last week's template plus the new data."""
import json
import os
import re
import sys

import ff_core as F

HERE = os.path.dirname(os.path.abspath(__file__))
TPL = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
    "~/Projects/FantasyFootball/docs/s13/w9/index.html")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "page_w10.html")
SIMLABEL = sys.argv[3] if len(sys.argv) > 3 else "one million"

names, cur, base_tv, sched, rec, pts = F.load()
G = F.GAMES                      # 8
NW = len(F.REM)                  # 4

CF = json.load(open(os.path.join(HERE, "cf_w10.json")))
HELP = json.load(open(os.path.join(HERE, "help_w10.json")))
HODDS = json.load(open(os.path.join(HERE, "help_odds_w10.json")))
STAND = json.load(open(os.path.join(HERE, "S_w10.json")))
CORE = json.load(open(os.path.join(HERE, "prizes_core_w10.json")))
CUT = json.load(open(os.path.join(HERE, "cutoff_w10.json")))
BWP = json.load(open(os.path.join(HERE, "bwp_w10.json"))) if os.path.exists(
    os.path.join(HERE, "bwp_w10.json")) else None
REC = CORE["rec"]
ORDER = [r[0] for r in STAND]
rank = {t: i for i, t in enumerate(ORDER)}


def rngstr(v):
    if not v or v[0] is None:
        return "—"
    lo, hi = v
    return f"{lo} only" if lo == hi else f"{lo}–{hi}"


# ---------- ST: chips for clinched / eliminated ----------
ST = {t: {k: ("clinched" if v == "clinched" else
              "eliminated" if v == "eliminated" else "live")
          for k, v in CF[t]["status"].items()} for t in names}

# ---------- CF for the renderer ----------
OUTCF = {}
for t in ORDER:
    v = CF[t]
    seeds = {}
    for s in ("1", "2", "3", "6"):
        r = v["seeds"][s]
        if isinstance(r, dict) and r.get("kind") == "same":
            seeds[s] = r
        elif r == "clinched":
            seeds[s] = "clinched"
        elif r == "help":
            seeds[s] = "elim" if v["status"][s] == "eliminated" else "help"
        else:
            by = {}
            for c in r:
                by.setdefault(str(c["n"]), []).append(
                    {"f": c["f"], "k": c["k"], "pool": c["pool"], "rem": c["rem"]})
            seeds[s] = by
    OUTCF[t] = {"name": t, "rec": v["rec"],
                "rng": [rngstr(v["rng"][k]) for k in ("1", "2", "3", "6")],
                "odds": v["odds"], "oneins": v.get("oneins", {}), "seeds": seeds}

# ---------- H: elimination / help cards ----------
H = []
for t in ORDER:
    if t not in HELP:
        continue
    v = HELP[t]
    if v.get("dead"):
        H.append([t, v["rec"], "warn", "Eliminated from playoff contention.", [],
                  "No combination of remaining results can put them in the top six."])
        continue
    rows = HODDS[t]
    k, N = len(rows), v["N"]
    hdr = (f"Needs all {k} of these things to happen:" if N == k
           else f"Needs any {N} of these {k} things to happen:")
    items = []
    for u, l, w, _p, shown in rows:
        if l >= G:
            s = f"{u} loses all {G} <span class='pc'>{shown}</span>"
            if w:
                s += (f" <span class='mini'>one of those is your wk{w} game</span>")
        else:
            s = f"{u} loses ≥{l} of {G} <span class='pc'>{shown}</span>"
            if w and l - 1 > 0:
                s += f" <span class='mini'>you beat them in wk{w}, so {l-1} more</span>"
        items.append(s)
    note = ""
    if v["perm"]:
        note = (", ".join(v["perm"]) + " will finish above them regardless — "
                "nothing can change that, so they'd get in behind them.")
    H.append([t, v["rec"], "", hdr, items, note])

# ---------- P: the five prizes ----------
def lead(t):
    return f"{t} {REC[t]}"


P = [["Most points — $100", lead(CORE["pts"][0][0]),
      [f"{t} — {v:.2f}" for t, v in CORE["pts"]],
      "No tiebreaker needed; every total is distinct."],
     ["Best worst week — $50", lead(CORE["bworst"][0][0]),
      [f"{t} — {v:.2f} (wk{w})" for t, v, w in CORE["bworst"]],
      "A floor, so it only moves down. Ties break on the second-worst week, then the third. "
      "<b>Week 10 changed this one.</b> Rock You Like a Burrowcane had led all season on "
      "111.08 from week 3, then posted 89.62 — the week's lowest score — and fell to fourth. "
      "Flush It Down inherits the lead."],
     ["Best week — $50", lead(CORE["bbest"][0][0]),
      [f"{t} — {v:.2f} (wk{w})" for t, v, w in CORE["bbest"]],
      "Ties break on the second-highest week, then the third."],
     ["Most best weeks — $50", lead(CORE["mbest"][0][0]),
      [f"{t} — {n} (wk {', '.join(map(str, ws))}) · {p:.2f} pts in those weeks"
       for t, n, ws, p in CORE["mbest"]],
      "Ties break on points scored in the weeks that earned the point. "
      "<b>It is now a tie.</b> The Nightman Re-Cometh took week 10 with 163.48 to reach "
      "three, level with Rock You Like a Burrowcane — so the tiebreak decides it, and "
      "Burrowcane leads 488.68 to 469.30."]]
if BWP:
    P.append(["Best worst player — $50", lead(BWP[0][0]),
              [f"{t} — {p:.2f} ({nm}, {sl}, wk{w})" for t, p, nm, sl, w in BWP],
              "Only weeks where you filled every roster spot count. "
              "Ties break on the second-worst player that week."])

# ---------- assemble ----------
src = open(TPL).read()


def swap(const, obj):
    global src
    line = f"const {const}=" + json.dumps(obj, ensure_ascii=True) + ";"
    new, n = re.subn(rf'^const {const}=.*?;$', lambda m: line, src, count=1, flags=re.M)
    assert n == 1, f"could not swap {const}"
    src = new


swap("ST", ST)
swap("S", STAND)
swap("CF", OUTCF)
swap("H", H)
swap("P", P)

# archive banner from the w9 snapshot must not carry over
src = re.sub(r'<div class="card warn" style="margin:0 0 1\.25rem">.*?</div>', "", src,
             count=1, flags=re.S)

REPL = [
    ("<title>Playoff Picture — Week 9 (archived)</title>",
     "<title>Playoff Picture — Week 10 Report</title>"),
    ("Through Week 9 · Five weeks remain", "Through Week 10 · Four weeks remain"),
    ("five weeks remain", "four weeks remain"),
    ("W10 is your week-10 matchup, M13 the week-13 median.",
     "W11 is your week-11 matchup, M13 the week-13 median."),
    ("You have ten games left, not five", "You have eight games left, not four"),
    ("assume they win all\n  five matchups <em>and</em> all five medians",
     "assume they win all\n  four matchups <em>and</em> all four medians"),
    ("weeks 10 through 14", "weeks 11 through 14"),
    ("the final win total out of 28", "the final win total out of 28"),
    ("I simulated one billion ways", f"I simulated {SIMLABEL} ways"),
    ("from the billion-season simulation", f"from the {SIMLABEL.replace('one ','')}-season simulation"),
    ('"win out — all 12"', '"win out — all 8"'),
    ("c.f.length===12?", "c.f.length===8?"),
    ("c.k===12?", "c.k===8?"),
    ('if(el.length) out+=`<span class="chip e">out of ${el.length>1?"seeds "+el.join(", "):"seed "+el[0]}</span>`;',
     'if(el.includes("6")) out+=`<span class="chip e">eliminated from playoff contention</span>`;\n   else if(el.length) out+=`<span class="chip e">out of ${el.length>1?"seeds "+el.join(", "):"seed "+el[0]}</span>`;'),
]
src = re.sub(r'Five weeks left —\s*\n\s*ten games apiece',
             'Four weeks left —\n  eight games apiece', src, count=1)

for a, b in REPL:
    if a in src:
        src = src.replace(a, b)
    else:
        print(f"  NOTE: template string not found, skipped: {a[:58]!r}")

# number of teams needing help, stated in the prose
nhelp = len([h for h in H if not h[2]])
src = re.sub(r'\b\d+ teams don[’\']t control their own destiny',
             f"{nhelp} teams don’t control their own destiny", src, count=1)



def card_span(s, start):
    """[start, end) of the <div> that begins at `start`, matched properly.

    The old code looked for the next </div> after some inner tag, which walked
    straight out of the card and swallowed the whole clinching section."""
    depth, i = 0, start
    while True:
        o = s.find("<div", i)
        c = s.find("</div>", i)
        assert c != -1, "unbalanced div"
        if o != -1 and o < c:
            depth += 1
            i = o + 4
        else:
            depth -= 1
            i = c + 6
            if depth == 0:
                return start, i


# ---------- the two cards that are rewritten from scratch each week ----------
rows = "".join(
    f'<tr><td data-l="Line">{CUT[k]["label"]}</td>'
    f'<td class="n" data-l="Mean">{CUT[k]["mean"]:.3f}</td>'
    f'<td class="n" data-l="Median">{CUT[k]["median"]:g}</td>'
    f'<td class="n" data-l="Mode">{CUT[k]["mode"]:g}</td></tr>'
    for k in ("s1", "s2", "s3", "s6"))
i, j = card_span(src, src.index('<div class="card"><h3>Where the playoff line falls</h3>'))
src = src[:i] + (
    '<div class="card"><h3>Where each line falls</h3>'
    '<p>The midpoint between the seed above a line and the seed below it, across '
    f'{SIMLABEL} seasons. The playoff line averages the 6 seed and 7 seed; the others '
    'work the same way one seed up.</p>'
    '<div class="panel" style="padding:2px 10px"><table class="stack">'
    '<thead><tr><th>Line</th><th class="r">Mean</th><th class="r">Median</th>'
    '<th class="r">Mode</th></tr></thead><tbody>' + rows + '</tbody></table></div>'
    '<p class="lead">Practical read: 15 wins should get you into the playoffs, 14 is a '
    'coin flip, 13 probably is not enough. The 1 seed has been going for about 20.</p>'
    '</div>') + src[j:]

YAHOO = ["Rock You Like a Burrowcane", "Showtime", "Omarion my wayward son",
         "Flush It Down", "Flowers For Charlie", "The Nightman Re-Cometh", "XXI",
         "Jahmyrs For Fears", "Chasing Nabors", "You Give Love A Brad Name",
         "Swap's Team", "It's Allen The Hips"]
diff = [(t, ORDER.index(t) + 1, YAHOO.index(t) + 1)
        for t in ORDER if ORDER.index(t) != YAHOO.index(t)]
li = "".join(f"<li><b>{t}</b> — {o} here, {y} on Yahoo</li>" for t, o, y in diff)
i, j = card_span(src, src.index('<div class="card"><h3>This order is not Yahoo\'s order</h3>'))
src = src[:i] + (
    '<div class="card"><h3>This order is not Yahoo\'s order</h3>'
    '<p>Yahoo breaks ties on points. Our rule is most recent weekly records counting '
    f'backwards from week 14, so {len(diff)} teams sit differently here:</p>'
    f'<ul class="tight">{li}</ul>'
    '<p class="lead">The three-way tie at 13-7 is the big one: Flowers For Charlie went '
    '2-0 in week 10, Omarion my wayward son 1-1, Flush It Down 0-2 — that one week '
    'orders all three.</p></div>') + src[j:]


# ---------- clinching section: cards first, explanation underneath ----------
_i = src.index('<span class="eyebrow">Team by team</span>')
_sec_end = src.index("</section>", _i)
_head_end = src.index("</div>", src.index("<h2>", _i)) + len("</div>")
_panel = src.index('<div class="panel"', _head_end)
_panel_end = src.index("</div>", src.index('id="clin"', _panel)) + len("</div>")
_panel_end = src.index("</div>", _panel_end) + len("</div>")
_card = src[_panel:_panel_end]
_prose = src[_head_end:_panel]
assert 'id="clin"' in _card and "Notes on notation" in _prose
src = src[:_head_end] + "\n  " + _card + _prose.rstrip() + "\n" + src[_panel_end:]
assert src.index('id="clin"') < src.index("Notes on notation")


TPL_IDS = set(re.findall(r'id="([a-z]+)"', open(TPL).read()))
OUT_IDS = set(re.findall(r'id="([a-z]+)"', src))
missing = TPL_IDS - OUT_IDS
assert not missing, f"build dropped render targets: {sorted(missing)}"
for sec in ("stand", "clin", "help", "prizes"):
    assert f'id="{sec}"' in src, f"missing #{sec}"

open(OUT, "w").write(src)
print(f"wrote {OUT}  ({len(src):,} bytes)")
print(f"  standings rows {len(STAND)} · clinch cards {len(OUTCF)} · "
      f"help cards {len(H)} · prizes {len(P)}")
