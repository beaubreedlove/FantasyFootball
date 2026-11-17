# Playoff picture pipeline

The scratchpad these were written in is a tmp directory that gets cleared, which
once cost a full from-scratch rebuild mid-request. They live here now.

## Weekly run

```sh
python3 -m venv .venv && .venv/bin/pip install ortools numpy

# 1. scrape — one league page per week gives all six matchups
#    (see the scrape block in the session; writes ff_data.json)
#    ALWAYS reconcile: every team's season total must equal Yahoo's PF column
#    and every weekly median must equal Yahoo's published median.

# 2. simulate — million first for speed, billion in the background
.venv/bin/python ff_sim.py 1000000    sim_1e6.npz
nohup .venv/bin/python ff_sim.py 1000000000 sim_1e9.npz > sim.log 2>&1 &

# 3. status + solver data
.venv/bin/python ff_build.py sim_1e9.npz

# 4. players, for the "best worst player" prize only
./scrape_players.sh

# 5. page
.venv/bin/python make_page.py <last-week-archive.html> page.html "one billion"
```

## Things that have bitten us

- **Scrape the team or per-matchup view, not the first row of a repeated block.**
  A parser that only validates the first matchup on a page proves nothing; that
  bug put 10 of 12 records wrong and survived a spot check.
- **Yahoo applies stat corrections on Tuesday.** Re-pull before publishing; week
  10 moved a score by 1.00 overnight.
- **Elimination needs the minimiser.** `n_above(..., "min")` answers "how many
  MUST finish above me". Using the maximiser for both once declared half the
  league eliminated.
- **A cap that ties is not a cap.** To finish *below* someone you need one more
  loss than the figure that merely draws level, because the tiebreak goes to the
  adversary.
- **Validate the built HTML.** An unclosed `<b>` bolded a whole page and made the
  browser renest the sections, silently eating the layout. `tools/balance.py`
  style parsing is part of the publish step now.
- **Check `node --check` on the script block.** One syntax error blanks every
  rendered section.
