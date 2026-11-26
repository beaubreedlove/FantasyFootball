#!/usr/bin/env python3
"""Late-swap optimiser: 1:00 game is locked, optimise the rest.

Players already playing cannot be changed, so their salary and slots come off
the top and only the later games are free. Beyond raw projection this scores
two things the plain knapsack ignores:

  correlation -- a QB with his own pass catchers rises and falls together, so a
  stack converts a good game script into a lineup-wide spike instead of one
  good score. A "bring-back" from the opposing side turns a shootout into
  points on both ends.

  usage -- projected rostership. In a tournament the payout depends on beating
  other entries, so a point scored by a player nobody owns is worth more than
  the same point from a popular one.
"""
import csv
import re
import sys

from ortools.sat.python import cp_model

CAP = 50_000
SLOTS = {"QB": 1, "RB": 2, "WR": 3, "TE": 1, "DST": 1}
FLEX = ("RB", "WR", "TE")
LOCK_TIME = "1:00PM"
SRC = sys.argv[1] if len(sys.argv) > 1 else "dfs/dk_thu_11-26_all.csv"
LOCKED = ["Jahmyr Gibbs", "Luther Burden III", "Rome Odunze",
          "Colston Loveland", "Detroit Lions"]

ROST = {"0-1%": 0.5, "1-5%": 3.0, "5-10%": 7.5, "10-20%": 15.0, "20-30%": 25.0,
        "30-40%": 35.0, "40-50%": 45.0}


def load():
    out = []
    for r in csv.DictReader(open(SRC)):
        try:
            pts = float(r["PROJ PTS."])
            sal = int(re.sub(r"[^\d]", "", r["SALARY"]))
        except (ValueError, KeyError):
            continue
        raw = r["PLAYER"].strip()
        if pts <= 0 or sal <= 0 or raw.endswith(" O") or raw.endswith(" I"):
            continue
        pos = r["POS RANK"].split()[0]
        if pos not in SLOTS:
            continue
        m = re.match(r"(.+?)\s+([A-Z]{2,3})\s+-\s+(QB|RB|WR|TE|DST)", raw)
        name = m.group(1).strip() if m else re.sub(r" [OIQ]$", "", raw)
        team = m.group(2) if m else "?"
        opp = r["OPPONENT"]
        at = re.search(r"(\d+:\d+[AP]M)", opp)
        vs = re.match(r"@?([A-Z]{2,3})", opp)
        out.append({"name": name, "team": team, "pos": pos, "pts": pts, "sal": sal,
                    "ceil": float(r["PROJ CEIL."] or 0), "rost": r["PROJ. ROST%"],
                    "own": ROST.get(r["PROJ. ROST%"], 3.0),
                    "time": at.group(1) if at else "?",
                    "opp": vs.group(1) if vs else "?"})
    return out


def build(players, locked_idx, extra=None):
    m = cp_model.CpModel()
    x = [m.NewBoolVar(p["name"]) for p in players]
    for i in locked_idx:
        m.Add(x[i] == 1)
    for i, p in enumerate(players):
        if i not in locked_idx and p["time"] == LOCK_TIME:
            m.Add(x[i] == 0)                      # already playing, can't add
    m.Add(sum(x) == 9)
    for pos, n in SLOTS.items():
        g = [x[i] for i, p in enumerate(players) if p["pos"] == pos]
        m.Add(sum(g) >= n)
        m.Add(sum(g) <= n + (1 if pos in FLEX else 0))
    m.Add(sum(x[i] * players[i]["sal"] for i in range(len(players))) <= CAP)
    if extra:
        extra(m, x)
    return m, x


def stack_rule(players, nback=0):
    """QB must bring >=1 of his own pass catchers, optionally a bring-back too."""
    def add(m, x):
        for i, q in enumerate(players):
            if q["pos"] != "QB":
                continue
            mates = [x[j] for j, p in enumerate(players)
                     if p["team"] == q["team"] and p["pos"] in ("WR", "TE")]
            m.Add(sum(mates) >= 1).OnlyEnforceIf(x[i])
            if nback:
                backs = [x[j] for j, p in enumerate(players)
                         if p["team"] == q["opp"] and p["pos"] in ("WR", "TE", "RB")]
                m.Add(sum(backs) >= nback).OnlyEnforceIf(x[i])
    return add


def run(players, locked_idx, label, objective, extra=None, floor=None):
    m, x = build(players, locked_idx, extra)
    if floor is not None:
        m.Add(sum(x[i] * int(round(players[i]["pts"] * 100))
                  for i in range(len(players))) >= int(round(floor * 100)))
    objective(m, x)
    s = cp_model.CpSolver()
    s.parameters.num_search_workers = 8
    s.parameters.max_time_in_seconds = 60
    if s.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f"\n{label}: infeasible")
        return None
    idx = [i for i in range(len(players)) if s.Value(x[i])]
    show(players, idx, locked_idx, label)
    return idx


def show(players, idx, locked_idx, label):
    picked = [players[i] for i in idx]
    order = {"QB": 0, "RB": 1, "WR": 2, "TE": 3, "DST": 4}
    picked.sort(key=lambda p: (order[p["pos"]], -p["pts"]))
    tp = sum(p["pts"] for p in picked)
    ts = sum(p["sal"] for p in picked)
    tc = sum(p["ceil"] for p in picked)
    to = sum(p["own"] for p in picked)
    print(f"\n{label}")
    print(f"   {tp:.1f} proj · {tc:.1f} ceiling · ${ts:,} used · ${CAP-ts:,} left "
          f"· ~{to:.0f}% summed ownership")
    for p in picked:
        lk = "LOCK" if players.index(p) in locked_idx else "    "
        print(f"   {lk} {p['pos']:<4}{(p['name']+' '+p['team'])[:26]:28s}"
              f"{p['pts']:>6.1f}{p['sal']:>8,}{p['rost']:>8s}  {p['time']}")


def main():
    players = load()
    locked_idx = []
    for nm in LOCKED:
        hit = [i for i, p in enumerate(players) if p["name"] == nm]
        if not hit:
            print(f"!! locked player not found: {nm}")
            continue
        locked_idx.append(hit[0])
    lsal = sum(players[i]["sal"] for i in locked_idx)
    print(f"locked {len(locked_idx)} from the {LOCK_TIME} game · ${lsal:,} committed "
          f"· ${CAP-lsal:,} for the remaining {9-len(locked_idx)} slots")
    later = [p for p in players if p["time"] != LOCK_TIME]
    print(f"{len(later)} players still available in the later games")

    maxpts = lambda m, x: m.Maximize(sum(x[i] * int(round(players[i]["pts"] * 100))
                                         for i in range(len(players))))
    maxceil = lambda m, x: m.Maximize(sum(x[i] * int(round(players[i]["ceil"] * 100))
                                          for i in range(len(players))))
    minown = lambda m, x: m.Minimize(sum(x[i] * int(round(players[i]["own"] * 10))
                                         for i in range(len(players))))

    base = run(players, locked_idx, "A · most projected points", maxpts)
    if base:
        top = sum(players[i]["pts"] for i in base)
        run(players, locked_idx, "B · QB stacked with his own receiver",
            maxpts, extra=stack_rule(players))
        run(players, locked_idx, "C · full game stack, QB + receiver + bring-back",
            maxpts, extra=stack_rule(players, nback=1))
        run(players, locked_idx, "D · highest ceiling", maxceil)
        run(players, locked_idx, f"E · lowest ownership within 6 pts of {top:.1f}",
            minown, floor=top - 6)


if __name__ == "__main__":
    main()
