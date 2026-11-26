#!/usr/bin/env python3
"""Exact knapsack for a DraftKings NFL Classic lineup.

QB 1 · RB 2 · WR 3 · TE 1 · FLEX 1 (RB/WR/TE) · DST 1 = 9 players, $50,000 cap.

Solved with CP-SAT rather than a greedy value sort: greedy by points-per-dollar
is not optimal under a cap plus positional quotas, and the gap is routinely a
point or two. Successive solutions are produced by forbidding each previous
lineup exactly, so the runner-ups are genuinely the next best rather than
near-duplicates of the winner.
"""
import csv
import re
import sys

from ortools.sat.python import cp_model

CAP = 50_000
SLOTS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "DST": 1}
FLEX = ("RB", "WR", "TE")
N_LINEUPS = int(sys.argv[2]) if len(sys.argv) > 2 else 3
SRC = sys.argv[1] if len(sys.argv) > 1 else "dfs/dk_thu_11-26_all.csv"


def load():
    out = []
    for r in csv.DictReader(open(SRC)):
        try:
            pts = float(r["PROJ PTS."])
            sal = int(re.sub(r"[^\d]", "", r["SALARY"]))
        except (ValueError, KeyError):
            continue
        if pts <= 0 or sal <= 0:
            continue                     # inactive, injured, or no projection
        name = r["PLAYER"].strip()
        status = ("OUT" if name.endswith(" O") else "IR" if name.endswith(" I")
                  else "Q" if name.endswith(" Q") else "")
        if status in ("OUT", "IR"):
            continue
        pos = r["POS RANK"].split()[0]
        if pos not in ("QB", "RB", "WR", "TE", "DST"):
            continue
        out.append({"name": re.sub(r" [OIQ]$", "", name), "pos": pos, "pts": pts,
                    "sal": sal, "status": status,
                    "ceil": float(r["PROJ CEIL."] or 0), "rost": r["PROJ. ROST%"]})
    return out


def solve(players, banned):
    m = cp_model.CpModel()
    x = [m.NewBoolVar(p["name"]) for p in players]
    use = {pos: [x[i] for i, p in enumerate(players) if p["pos"] == pos]
           for pos in SLOTS}
    m.Add(sum(x) == sum(SLOTS.values()) + 1)                 # 9 including FLEX
    for pos, n in SLOTS.items():
        lo, hi = n, n + (1 if pos in FLEX else 0)            # FLEX adds one
        m.Add(sum(use[pos]) >= lo)
        m.Add(sum(use[pos]) <= hi)
    m.Add(sum(x[i] * players[i]["sal"] for i in range(len(players))) <= CAP)
    for prev in banned:                                      # forbid that exact nine
        m.Add(sum(x[i] for i in prev) <= 8)
    m.Maximize(sum(x[i] * int(round(players[i]["pts"] * 100))
                   for i in range(len(players))))
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = 8
    s.parameters.max_time_in_seconds = 60
    if s.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return [i for i in range(len(players)) if s.Value(x[i])]


def show(players, idx, label):
    picked = [players[i] for i in idx]
    order = {"QB": 0, "RB": 1, "WR": 2, "TE": 3, "DST": 4}
    picked.sort(key=lambda p: (order[p["pos"]], -p["pts"]))
    tp = sum(p["pts"] for p in picked)
    ts = sum(p["sal"] for p in picked)
    tc = sum(p["ceil"] for p in picked)
    print(f"\n{label}   {tp:.1f} projected · ${ts:,} used · ${CAP-ts:,} left "
          f"· {tc:.1f} ceiling")
    counts = {}
    for p in picked:
        counts[p["pos"]] = counts.get(p["pos"], 0) + 1
    for p in picked:
        flex = ""
        if p["pos"] in FLEX and counts[p["pos"]] > SLOTS[p["pos"]]:
            flex = ""                                        # marked below instead
        q = " (Q)" if p["status"] == "Q" else ""
        print(f"   {p['pos']:<4}{p['name'][:28]+q:32s}{p['pts']:>6.1f}"
              f"{p['sal']:>9,}{p['rost']:>9s}")
    over = [pos for pos in FLEX if counts.get(pos, 0) > SLOTS[pos]]
    if over:
        print(f"   (the extra {over[0]} fills the FLEX slot)")
    return tp


def main():
    players = load()
    print(f"{len(players)} eligible players (zero-projection, OUT and IR removed)")
    banned, best = [], None
    for n in range(N_LINEUPS):
        idx = solve(players, banned)
        if idx is None:
            break
        tp = show(players, idx, f"LINEUP {n+1}")
        best = best or tp
        banned.append(idx)
    print(f"\ncap ${CAP:,} · QB 1, RB 2, WR 3, TE 1, FLEX 1, DST 1")


if __name__ == "__main__":
    main()
