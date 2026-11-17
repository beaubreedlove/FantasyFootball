#!/bin/bash
# Per-team, per-week STARTER points for the "best worst player" prize.
# Roster rows carry 30 cells: [0]=slot, [1]=player, [5]=fantasy points.
# Bench (BN) and injured (IR) slots are excluded by the extractor.
cd "$(dirname "$0")"
S=ffprize
playwright-cli -s=$S close >/dev/null 2>&1
playwright-cli -s=$S open --browser=chromium "https://football.fantasysports.yahoo.com/f1/765761" >/dev/null 2>&1
mkdir -p players
JS='JSON.stringify(Array.prototype.slice.call(document.querySelectorAll("table tbody tr")).filter(function(tr){return tr.cells.length>=7&&tr.cells[0]&&/^(QB|RB|WR|TE|W\/R\/T|K|DEF|BN|IR)$/.test(tr.cells[0].innerText.trim())}).map(function(tr){return [tr.cells[0].innerText.trim(),(tr.cells[1].innerText||"").split("\n")[0],tr.cells[5]?tr.cells[5].innerText.trim():""]}))'
for t in 1 2 3 4 5 6 7 8 9 10 11 12; do
  for w in 1 2 3 4 5 6 7 8 9 10; do
    f="players/t${t}_w${w}.json"
    [ -s "$f" ] && [ "$(head -c 4 "$f")" != '"[]"' ] && continue
    playwright-cli -s=$S goto "https://football.fantasysports.yahoo.com/f1/765761/${t}?week=${w}" >/dev/null 2>&1
    playwright-cli -s=$S eval "$JS" 2>&1 | grep '^"' > "$f"
    echo "t$t w$w $(wc -c <"$f" | tr -d ' ')"
  done
done
playwright-cli -s=$S close >/dev/null 2>&1
echo DONE
