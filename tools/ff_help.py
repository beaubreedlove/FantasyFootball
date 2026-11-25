#!/usr/bin/env python3
"""What a team that can't clinch still needs from everybody else.

Thresholds are asked of the solver rather than derived by hand. The hand
derivation had to reason about who wins a tie, and got it backwards: when the
subject wins out their last-three-weeks record is 2-0, 2-0, 2-0, which is the
best possible, so the subject wins every tie on equal wins. Encoding that as
an off-by-one produced a `None` threshold for one team and an inflated count
for others. Asking the model "can u still finish above T if u wins at most W?"
needs no tie reasoning at all.
"""
import json
from itertools import combinations

import ff_core as F
import ff_solve as S

G = F.GAMES
A = tuple(S.ATOMS)
names, cur, sched = S.names, S.cur, S.sched


def _above_possible(T, caps):
    """With T winning out and caps {rival: max wins}, can >=6 teams finish above T?"""
    m, ab, rem, _key = S.build(T, A)
    for u, w in caps.items():
        m.Add(rem[u] <= w)
    v = S._solve(m, sum(ab), "max")
    return None if v is None else v > 5


def _u_can_be_above(T, u, w):
    """With T winning out and u winning at most w, can u personally finish above T?"""
    m, ab, rem, key = S.build(T, A)
    m.Add(rem[u] <= w)
    b = m.NewBoolVar("x")
    m.Add(key[u] >= key[T] + 1).OnlyEnforceIf(b)
    m.Add(key[u] <= key[T] - 1).OnlyEnforceIf(b.Not())
    v = S._solve(m, b, "max")
    return bool(v) if v is not None else False


def threshold(T, u):
    """Largest number of wins u can take and still be guaranteed below T.

    -> (max_wins, losses_required) or None if u finishes above no matter what.
    """
    for w in range(G, -1, -1):
        if not _u_can_be_above(T, u, w):
            return w, G - w
    return None


def help_for(T):
    if not _above_possible(T, {}):
        return None                                   # controls own destiny
    plays = {}
    for wk in F.REM:
        for a, b in sched[wk]:
            if T in (a, b):
                plays[b if a == T else a] = wk
    cap, perm = [], []
    for u in names:
        if u == T:
            continue
        r = threshold(T, u)
        if r is None:
            perm.append(u)
            continue
        _w, loss = r
        if loss <= 0:
            continue                                  # already guaranteed below
        cap.append([u, loss, plays.get(u)])
    cap.sort(key=lambda x: x[1])

    def ok(group):
        caps = {u: G - l for u, l, _w in group}
        v = _above_possible(T, caps)
        return True if v is None else not v           # infeasible => vacuous

    N = None
    for k in range(0, len(cap) + 1):
        subs = list(combinations(cap, k))
        if subs and all(ok(g) for g in subs):
            N = k
            break
    if N is None and cap and ok(tuple(cap)):
        N = len(cap)
    return {"rec": f"{cur[T]}-{22-cur[T]}", "N": N, "perm": perm, "things": cap,
            "impossible": N is None}


def main():
    status = json.load(open("status_w10.json"))
    H = {}
    for T in sorted(names, key=lambda t: -cur[t]):
        if status[T]["6"] == "eliminated":
            H[T] = {"rec": f"{cur[T]}-{22-cur[T]}", "dead": True}
            print(f"  {T:28s} ELIMINATED")
            continue
        h = help_for(T)
        if not h:
            continue
        H[T] = h
        k = len(h["things"])
        lab = ("NO SET SUFFICES" if h["N"] is None else
               f"all {k}" if h["N"] == k else f"any {h['N']} of {k}")
        print(f"  {T:28s} {lab}" + (f"  (+{len(h['perm'])} permanent)" if h["perm"] else ""))
        for u, l, w in h["things"]:
            print(f"        {u} loses >={l} of {G}" + (f"  [plays you wk{w}]" if w else ""))
        for u in h["perm"]:
            print(f"        PERMANENT: {u}")
    json.dump(H, open("help_w10.json", "w"), indent=1)


if __name__ == "__main__":
    main()
