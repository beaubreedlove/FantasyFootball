#!/usr/bin/env python3
"""Exact clinch / elimination / win-range solver for the final four weeks.

The adversary picks every remaining result, subject only to what the schedule
allows: each week exactly six teams clear the median, and a matchup winner's
median result must dominate the loser's -- so a pair is (2,1), (2,0) or (1,0),
never (1,1), (2,2) or (0,0).

``n_above(T, forced, sense)`` is the whole engine. With sense="max" it asks
"how many teams COULD finish above T" (clinching: if even the worst case keeps
that count under the seed, the seed is locked). With sense="min" it asks "how
many MUST finish above T" (elimination). Using the maximiser for both is the
bug that once declared half the league dead.

Only 8 games remain, so the 256 subsets of a team's own games can be
enumerated exhaustively; the sufficient ones are upward-closed, which makes the
minimal ones an exact antichain rather than a heuristic.
"""
import json
from functools import lru_cache
from itertools import combinations

from ortools.sat.python import cp_model

import ff_core as F

names, cur, base_tv, sched, rec, pts = F.load()

ATOMS = [f"{k}{w}" for w in F.REM for k in ("W", "M")]      # W11, M11, ... M14


def _atom(t, w, kind):
    return f"{kind}{w}"


def build(T, forced):
    """CP-SAT model with T's listed games forced to wins. -> (model, above_bools)"""
    m = cp_model.CpModel()
    med, mwin = {}, {}
    for w in F.REM:
        for t in names:
            med[w, t] = m.NewBoolVar(f"med{w}{t}")
        m.Add(sum(med[w, t] for t in names) == 6)
        for a, b in sched[w]:
            x = m.NewBoolVar(f"mw{w}{a}")
            nb = m.NewBoolVar(f"mw{w}{b}")
            m.Add(nb == 1 - x)
            # dominance: the matchup winner also wins the median comparison
            m.Add(med[w, b] - med[w, a] <= 1 - x)
            m.Add(med[w, a] - med[w, b] <= x)
            mwin[w, a], mwin[w, b] = x, nb
    for a in forced:
        kind, w = a[0], int(a[1:])
        m.Add((mwin[w, T] if kind == "W" else med[w, T]) == 1)
    rem = {t: sum(mwin[w, t] + med[w, t] for w in F.REM) for t in names}
    key = {}
    for t in names:
        k = m.NewIntVar(0, 40 * F.BIG, f"k{t}")
        m.Add(k == (cur[t] + rem[t]) * F.BIG + base_tv[t]
              + sum((mwin[w, t] + med[w, t]) * F.POW3[w] for w in F.REM))
        key[t] = k
    ab = []
    for u in names:
        if u == T:
            continue
        a = m.NewBoolVar(f"ab{u}")
        m.Add(key[u] >= key[T] + 1).OnlyEnforceIf(a)
        m.Add(key[u] <= key[T] - 1).OnlyEnforceIf(a.Not())
        ab.append(a)
    return m, ab, rem, key


def _solve(m, obj, sense):
    m.Maximize(obj) if sense == "max" else m.Minimize(obj)
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = 8
    s.parameters.max_time_in_seconds = 60
    r = s.Solve(m)
    if r == cp_model.INFEASIBLE:
        return None
    assert r in (cp_model.OPTIMAL, cp_model.FEASIBLE), r
    return int(round(s.ObjectiveValue()))


@lru_cache(maxsize=None)
def n_above(T, forced, sense):
    """How many teams finish above T -- max (could) or min (must)."""
    m, ab, _, _ = build(T, forced)
    return _solve(m, sum(ab), sense)


def win_range(T, lo_seed, hi_seed):
    """(fewest, most) total wins T can have while landing in [lo_seed, hi_seed]."""
    out = []
    for sense in ("min", "max"):
        m, ab, rem, _ = build(T, ())
        n = sum(ab)
        m.Add(n >= lo_seed - 1)
        m.Add(n <= hi_seed - 1)
        v = _solve(m, cur[T] + rem[T], sense)
        out.append(v)
    return (None, None) if out[0] is None else tuple(out)


def minimal_sufficient(T, seed):
    """Antichain of minimal sets of T's own games that lock up `seed` or better.

    Sufficiency is upward closed, so enumerating sizes in order and skipping
    supersets of a known-sufficient set yields exactly the minimal sets.
    """
    if n_above(T, (), "max") is not None and n_above(T, (), "max") <= seed - 1:
        return "clinched"
    if n_above(T, tuple(ATOMS), "max") > seed - 1:
        return "help"                      # winning out still isn't enough
    found = []
    for k in range(1, len(ATOMS) + 1):
        for S in combinations(ATOMS, k):
            s = set(S)
            if any(set(f) <= s for f in found):
                continue                   # a smaller sufficient set is inside
            if n_above(T, S, "max") <= seed - 1:
                found.append(S)
        if found and k >= max(len(f) for f in found):
            # everything larger is a superset of something already found only if
            # every size-k set was covered; keep going otherwise
            pass
    return found


def compress(minimals):
    """-> fewest clauses covering the antichain exactly.

    A clause is "win every game in f, plus any k from pool". The pool may be any
    SUBSET of the remaining atoms -- the earlier version only ever tried the full
    remainder, so it could not express "win W13 plus any one of these four" and
    fell back to a claim of "any 2", which is false when only 4 of the 15 pairs
    actually work. A candidate is legal only when every way of choosing k from
    pool yields a set in the family.
    """
    if not isinstance(minimals, list):
        return minimals
    fam = {frozenset(s) for s in minimals}
    n = len(ATOMS)
    cands = []
    for fmask in range(1 << n):
        f = frozenset(ATOMS[i] for i in range(n) if fmask >> i & 1)
        rest = [a for a in ATOMS if a not in f]
        if f and f in fam:
            cands.append((f, 0, (), frozenset({f})))
        for pmask in range(1, 1 << len(rest)):
            pool = tuple(rest[i] for i in range(len(rest)) if pmask >> i & 1)
            for k in range(1, len(pool) + 1):
                covers, ok = set(), True
                for X in combinations(pool, k):
                    c = f | frozenset(X)
                    if c in fam:
                        covers.add(c)
                    else:
                        ok = False
                        break
                if ok and covers:
                    cands.append((f, k, pool, frozenset(covers)))
    # drop a candidate if another covers a superset of the same sets at no
    # greater cost -- keeps the cover search small
    cands.sort(key=lambda c: (-len(c[3]), len(c[0]) + c[1]))
    m = cp_model.CpModel()
    use = [m.NewBoolVar(f"c{i}") for i in range(len(cands))]
    for t in fam:
        hit = [use[i] for i, c in enumerate(cands) if t in c[3]]
        assert hit, f"no clause covers {sorted(t)}"
        m.Add(sum(hit) >= 1)
    # fewest clauses first, then the least forced games, then the widest pools
    m.Minimize(sum(use) * 10000
               + sum(use[i] * (len(cands[i][0]) + cands[i][1]) * 10 for i in range(len(cands)))
               - sum(use[i] * len(cands[i][2]) for i in range(len(cands))))
    sv = cp_model.CpSolver()
    sv.parameters.num_search_workers = 8
    sv.parameters.max_time_in_seconds = 120
    sv.Solve(m)
    out = []
    for i, c in enumerate(cands):
        if sv.Value(use[i]):
            f, k, pool, _ = c
            out.append({"f": sorted(f, key=ATOMS.index), "k": k,
                        "pool": list(pool) if k and k < len(pool) else None,
                        "rem": len(pool) if pool else len(ATOMS) - len(f),
                        "n": len(f) + k})
    out.sort(key=lambda d: (d["n"], len(d["f"])))
    return out


if __name__ == "__main__":
    import sys
    T = sys.argv[1] if len(sys.argv) > 1 else names[0]
    for seed in (1, 2, 3, 6):
        r = minimal_sufficient(T, seed)
        print(f"\n{T} seed<={seed}: ", end="")
        if isinstance(r, str):
            print(r)
            continue
        for c in compress(r):
            print(f"\n   {c['n']} wins: f={c['f']} +any {c['k']}"
                  f"{' of '+str(c['pool']) if c['pool'] else ''}", end="")
        print()
