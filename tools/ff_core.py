#!/usr/bin/env python3
"""Shared state for the week-10 playoff picture.

Tiebreak is encoded as a base-3 integer with week 14 most significant, so a
plain integer compare reproduces the league rule "most recent weekly records,
counting backwards from week 14". Weeks 1-10 are fixed and contribute
``base_tv``; weeks 11-14 are the free variables.

key = total_wins * BIG + tv, with BIG = 3**15 chosen so tv can never carry
into the win field (max tv = sum_{w=1..14} 2*3^w = 3**15 - 3).
"""
import json
import os

REM = [11, 12, 13, 14]          # weeks still to play
PLAYED = range(1, 11)
GAMES = 2 * len(REM)            # 8 games left per team
BIG = 3 ** 15
POW3 = {w: 3 ** w for w in range(1, 15)}

_HERE = os.path.dirname(os.path.abspath(__file__))


def load():
    d = json.load(open(os.path.join(_HERE, "ff_data.json")))
    names = sorted(d["rec"])                       # canonical team order
    rec = {t: {int(w): r for w, r in d["rec"][t].items()} for t in names}
    cur = {t: sum(rec[t].values()) for t in names}
    base_tv = {t: sum(rec[t][w] * POW3[w] for w in PLAYED) for t in names}
    sched = {int(w): [tuple(p) for p in v] for w, v in d["pairs"].items()}
    pts = d["PF"]
    assert sum(cur.values()) == 2 * 6 * len(PLAYED), "win total must be 12/week"
    for w in REM:
        flat = [t for p in sched[w] for t in p]
        assert sorted(flat) == names, f"week {w} schedule is not a perfect matching"
    return names, cur, base_tv, sched, rec, pts


def seed_order(names, wins, tv):
    """-> list of teams best-first under the league rule."""
    return sorted(names, key=lambda t: -(wins[t] * BIG + tv[t]))


if __name__ == "__main__":
    names, cur, base_tv, sched, rec, pts = load()
    order = seed_order(names, cur, base_tv)
    print(f"{'':3s}{'team':28s}{'rec':>7s}  {'wk10':>5s}  {'pts':>8s}")
    for i, t in enumerate(order, 1):
        wk = rec[t][10]
        print(f"{i:2d}. {t:28s}{cur[t]:>3d}-{20-cur[t]:<3d}  {wk}-{2-wk}  {pts[t]:8.2f}")
