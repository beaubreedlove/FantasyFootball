#!/usr/bin/env python3
"""Generate every data block the page needs, from the solver + a sim file."""
import json
import sys
from itertools import combinations

import numpy as np

import ff_core as F
import ff_solve as S

A = S.ATOMS
names, cur, base_tv, sched, rec, pts = S.names, S.cur, S.base_tv, S.sched, S.rec, S.pts
SIM = sys.argv[1] if len(sys.argv) > 1 else "sim_w10_1e6.npz"


# ---------- odds formatting: keep digits until 3 significant figures ----------
def pct(c, n, possible):
    """c hits out of n, rendered to exactly three significant figures of
    whichever side is small -- so 99.95% keeps digits on the 0.05% tail -- with
    no trailing-zero padding beyond those three figures."""
    if not possible:
        return "0%"
    if c == 0:
        return f"none in {n:,}"
    p = 100.0 * c / n
    tail = 100.0 - p
    ref = min(p, tail) if 0.0 < tail else p
    if ref <= 0:
        return f"{p:g}%"
    import math
    dec = max(1, 2 - int(math.floor(math.log10(ref))))
    s = f"{p:.{dec}f}".rstrip("0").rstrip(".")
    if "." not in s:
        s += ".0"
    return s + "%"


def one_in(c, n):
    return None if c == 0 else f"1 in {round(n / c):,}"


# ---------- clinch: cheapest clean routes, then the uniform "any k" ----------
def any_k_ok(T, seed, k):
    return all(S.n_above(T, c, "max") <= seed - 1 for c in combinations(A, k))


def routes(T, seed):
    if S.n_above(T, (), "max") <= seed - 1:
        return "clinched"
    if S.n_above(T, tuple(A), "max") > seed - 1:
        return "help"
    kmin = next(k for k in range(0, 9) if any_k_ok(T, seed, k))
    mins = S.minimal_sufficient(T, seed)
    out = []
    for k in range(1, kmin):
        g = [m for m in mins if len(m) == k]
        if not g:
            continue
        cl = S.compress(g)
        if len(cl) <= 3:                 # only show cheaper routes if they stay readable
            out.extend(cl)
        else:
            out.append({"f": [], "k": k, "pool": None, "rem": 8, "n": k,
                        "partial": len(g)})
    out.append({"f": [], "k": kmin, "pool": None, "rem": 8, "n": kmin})
    out.sort(key=lambda d: d["n"])
    return out


# ---------- help: what the teams who can't clinch still need ----------
def help_for(T):
    """Assume T wins out; who must be held below them, and how many suffice."""
    tot = cur[T] + F.GAMES
    plays = {}
    for w in F.REM:
        for a, b in sched[w]:
            if T in (a, b):
                plays[b if a == T else a] = w
    raw = []
    for u in names:
        if u == T:
            continue
        ceil = cur[u] + (F.GAMES - 1 if u in plays else F.GAMES)
        if ceil < tot:
            continue                      # already below T's ceiling
        # strictly below T, not merely tied -- a tie goes to the adversary
        need = ceil - tot + 1
        raw.append((u, need, plays.get(u)))
    cap = sorted([(u, l, w) for u, l, w in raw if l <= F.GAMES], key=lambda x: x[1])
    perm = [u for u, l, _w in raw if l > F.GAMES]

    def ok(group):
        m, ab, rem, key = S.build(T, tuple(A))
        for u, l, _w in group:
            m.Add(rem[u] <= F.GAMES - l)
        v = S._solve(m, sum(ab), "max")
        # infeasible: that combination of losses cannot physically occur, so the
        # implication holds vacuously and must not block a smaller N
        return True if v is None else v <= 5

    if ok(()):
        return None                       # controls own destiny
    N = None
    for k in range(1, len(cap) + 1):
        subs = list(combinations(cap, k))
        if subs and all(ok(g) for g in subs):
            N = k
            break
    return {"rec": f"{cur[T]}-{20-cur[T]}", "N": N, "perm": perm,
            "things": [[u, l, w] for u, l, w in cap]}


def main():
    z = np.load(SIM, allow_pickle=True)
    snames = [str(x) for x in z["names"]]
    exact, n = z["exact"], int(z["n"])
    si = {t: i for i, t in enumerate(snames)}
    status = json.load(open("status_w10.json"))

    CF = {}
    for T in names:
        row = exact[si[T]]
        st = status[T]
        odds, oneins = [], {}
        for lab, idx in (("1", [0]), ("2", [1]), ("3", [2]), ("6", list(range(6)))):
            c = int(row[idx].sum())
            poss = st[lab] != "eliminated"
            odds.append(pct(c, n, poss))
            if poss and 0 < c:
                oneins[lab] = one_in(c, n)
        rng = {}
        for lab, (lo, hi) in (("1", (1, 1)), ("2", (2, 2)), ("3", (3, 3)), ("6", (1, 6))):
            rng[lab] = S.win_range(T, lo, hi)
        CF[T] = {"name": T, "rec": f"{cur[T]}-{20-cur[T]}", "odds": odds,
                 "oneins": oneins, "rng": rng, "status": st,
                 "seeds": {str(s): routes(T, s) for s in (1, 2, 3, 6)}}
        print(f"  {T:28s} " + " ".join(f"{o:>14s}" for o in odds), flush=True)

    # collapse identical route sets into "same as the N seed"
    for T, v in CF.items():
        for s in ("2", "3", "6"):
            for prior in ("1", "2", "3"):
                if prior >= s:
                    break
                if v["seeds"][s] == v["seeds"][prior] and not isinstance(v["seeds"][s], str):
                    v["seeds"][s] = {"kind": "same", "of": int(prior)}
                    break
    json.dump(CF, open("cf_w10.json", "w"), indent=1)

    H = {}
    for T in names:
        if status[T]["6"] == "eliminated":
            H[T] = {"rec": f"{cur[T]}-{20-cur[T]}", "dead": True}
            continue
        h = help_for(T)
        if h:
            H[T] = h
    json.dump(H, open("help_w10.json", "w"), indent=1)
    print("\nhelp needed:")
    for T, v in H.items():
        if v.get("dead"):
            print(f"  {T:28s} ELIMINATED")
        else:
            lab = "all" if v["N"] == len(v["things"]) else f"any {v['N']}"
            print(f"  {T:28s} {lab} of {len(v['things'])}"
                  + (f"  (+{len(v['perm'])} permanent)" if v["perm"] else ""))


if __name__ == "__main__":
    main()
