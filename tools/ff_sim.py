#!/usr/bin/env python3
"""Monte Carlo over the remaining four weeks.

Each week is drawn as a uniformly random ordering of all twelve teams -- equal
weight, nobody rated above anybody else. The top six in that ordering take the
median point; the matchup point goes to whichever of the pair ranks higher.
That construction automatically respects the dominance rule (a matchup winner
can never finish below its opponent on the median), so every sampled week is a
schedule-legal outcome.

Saves the full 12x12 seed matrix plus the cutoff distributions.

    ff_sim.py N [outfile]
"""
import json
import sys

import numpy as np

import ff_core as F


def run(n, out, seed=20261117, batch=250_000):
    names, cur, base_tv, sched, _rec, _pts = F.load()
    pos = {t: i for i, t in enumerate(names)}
    nt, nw = len(names), len(F.REM)
    pair_idx = np.array([[[pos[a], pos[b]] for a, b in sched[w]] for w in F.REM])
    w3 = np.array([F.POW3[w] for w in F.REM], dtype=np.int64)
    base = np.array([cur[t] * F.BIG + base_tv[t] for t in names], dtype=np.int64)

    rng = np.random.default_rng(seed)
    exact = np.zeros((nt, nt), dtype=np.int64)      # team x seed
    cut = {k: np.zeros(2 * 28 + 1, dtype=np.int64) for k in ("s1", "s2", "s3", "s6")}
    winhist = np.zeros((nt, 29), dtype=np.int64)
    done = 0
    while done < n:
        b = min(batch, n - done)
        done += b
        key = np.repeat(base[None, :], b, axis=0)
        for wi in range(nw):
            r = rng.random((b, nt))
            rank = np.argsort(np.argsort(-r, axis=1), axis=1)   # 0 = best
            above = (rank < 6).astype(np.int64)
            a, bb = pair_idx[wi, :, 0], pair_idx[wi, :, 1]
            pt = np.zeros((b, nt), dtype=np.int64)
            awin = rank[:, a] < rank[:, bb]
            np.put_along_axis(pt, np.broadcast_to(a, (b, 6)), awin.astype(np.int64), 1)
            np.put_along_axis(pt, np.broadcast_to(bb, (b, 6)), (~awin).astype(np.int64), 1)
            got = pt + above                        # this week's record, 0/1/2
            key += got * F.BIG + got * w3[wi]       # wins field, then tiebreak field
        wins = key // F.BIG
        ks = np.sort(key, axis=1)                   # ascending: index 11 is the 1 seed
        for k, (hi, lo) in (("s1", (11, 10)), ("s2", (10, 9)),
                            ("s3", (9, 8)), ("s6", (6, 5))):
            v = (ks[:, hi] // F.BIG) + (ks[:, lo] // F.BIG)     # 2x the midpoint
            cut[k] += np.bincount(v, minlength=2 * 28 + 1)
        seeds = np.argsort(np.argsort(-key, axis=1), axis=1)
        for i in range(nt):
            exact[i] += np.bincount(seeds[:, i], minlength=nt)
            winhist[i] += np.bincount(wins[:, i], minlength=29)
        print(f"  {done:,}/{n:,}", flush=True)
    np.savez(out, names=np.array(names), exact=exact, winhist=winhist,
             n=np.int64(n), **{f"cut_{k}": v for k, v in cut.items()})
    return names, exact, cut, n


def report(names, exact, cut, n):
    print(f"\nseed distribution over {n:,} seasons")
    order = sorted(range(len(names)), key=lambda i: -exact[i].dot(np.arange(len(names), 0, -1)))
    for i in order:
        row = exact[i]
        mk = lambda c: "0%" if c == 0 else f"{100*c/n:.3f}%"
        print(f"  {names[i]:28s} 1:{mk(row[0]):>9s} 2:{mk(row[1]):>9s} "
              f"3:{mk(row[2]):>9s} top6:{mk(row[:6].sum()):>9s}")
    print("\nplayoff-cutoff style midpoints (wins):")
    for k, lab in (("s1", "1 seed line"), ("s2", "2 seed line"),
                   ("s3", "3 seed line"), ("s6", "playoff line")):
        h = cut[k]
        tot = h.sum()
        vals = np.nonzero(h)[0]
        mean = (vals * h[vals]).sum() / tot / 2
        cdf = np.cumsum(h)
        med = np.searchsorted(cdf, tot / 2) / 2
        mode = int(np.argmax(h)) / 2
        print(f"  {lab:14s} mean {mean:6.3f}   median {med:5.1f}   mode {mode:5.1f}")


if __name__ == "__main__":
    n = int(float(sys.argv[1]))
    out = sys.argv[2] if len(sys.argv) > 2 else f"sim_{n}.npz"
    names, exact, cut, n = run(n, out)
    report(names, exact, cut, n)
