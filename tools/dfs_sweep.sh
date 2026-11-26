#!/bin/bash
# Enumerate every player on the current DFS slate.
#
# The table renders at most ~25 rows at a time, so no single view shows the
# whole pool. Each position tab is its own 25, and sorting a column both ways
# surfaces the bottom of a long list as well as the top. The union over
# (position x sort column x direction) is what actually covers the slate;
# players are deduped on name.
S=fantasypros
OUT=dfs/sweep
mkdir -p "$OUT"
GRAB='(function(){var ts=document.querySelectorAll("table");var t=null;
 ts.forEach(function(x){var h=x.querySelector("thead");
   if(h&&/PLAYER/.test(h.innerText)&&/SALARY/.test(h.innerText))t=x});
 if(!t)return "[]";
 return JSON.stringify(Array.prototype.map.call(t.querySelectorAll("tbody tr"),
   function(tr){return Array.prototype.map.call(tr.cells,function(c){
     return (c.innerText||"").trim().replace(/\s+/g," ")})}))})()'

for POS in All QB RB WR TE FLEX DST; do
  playwright-cli -s=$S eval "(function(){var e=Array.prototype.slice.call(document.querySelectorAll('a.panel-specific-nav__link')).filter(function(x){return (x.innerText||'').trim()==='$POS'})[0];if(e)e.click();return !!e})()" >/dev/null 2>&1
  sleep 2
  for COL in 9 11 12 13 4; do
    for PASS in 1 2; do
      playwright-cli -s=$S eval "(function(){var ts=document.querySelectorAll('table');var t=null;ts.forEach(function(x){var h=x.querySelector('thead');if(h&&/PLAYER/.test(h.innerText)&&/SALARY/.test(h.innerText))t=x});if(!t)return 0;var th=t.querySelectorAll('thead th')[$COL];if(!th)return 0;(th.querySelector('a,button')||th).click();return 1})()" >/dev/null 2>&1
      sleep 2
      playwright-cli -s=$S eval "$GRAB" 2>&1 | grep '^"' > "$OUT/${POS}_c${COL}_p${PASS}.json"
      printf "%-5s col%-3s pass%s  %s bytes\n" "$POS" "$COL" "$PASS" "$(wc -c <"$OUT/${POS}_c${COL}_p${PASS}.json" | tr -d ' ')"
    done
  done
done
echo SWEEPDONE
