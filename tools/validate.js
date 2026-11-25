// Render-check a built page the way a browser actually would.
//
// The previous stub returned a live object for ANY id, so a page that had lost
// its #clin div still "rendered" fine here while throwing in a real browser and
// blanking every section after it. Now getElementById only resolves ids that
// genuinely appear in the HTML, and returns null otherwise.
const fs = require("fs");
const path = require("path");
const file = process.argv[2];
const html = fs.readFileSync(file, "utf8");

const ids = new Set([...html.matchAll(/id="([A-Za-z0-9_-]+)"/g)].map(m => m[1]));
const store = {};
const el = () => ({
  classList: { toggle() {}, add() {}, remove() {} },
  dataset: {}, style: {}, setAttribute() {}, appendChild() {}, remove() {},
  addEventListener() {}, querySelector: () => null, querySelectorAll: () => [],
  closest: () => el(), appendChild() {}, contains: () => false,
  set textContent(v) {}, set className(v) {}, set value(v) {}, get value() { return ""; },
});
global.localStorage = { getItem: () => null, setItem() {} };
global.location = { search: "", href: "https://example.invalid/" };
global.history = { replaceState() {} };
global.document = {
  createElement: el,
  querySelectorAll: () => [],
  querySelector: () => null,
  getElementById(id) {
    if (!ids.has(id)) return null;          // exactly what a browser does
    // NB: Object.assign would copy the accessor's VALUE, not the accessor,
    // silently dropping the setter and making every section look empty.
    const node = el();
    Object.defineProperty(node, "innerHTML", {
      set(v) { store[id] = v; },
      get() { return store[id] || ""; },
      configurable: true,
    });
    return node;
  },
};

const js = html.split("<script>")[1].split("</script>")[0];
const tmp = path.resolve(file + ".extracted.js");
fs.writeFileSync(tmp, js);
try {
  require(tmp);
} catch (e) {
  console.log("  *** SCRIPT THREW: " + e.message);
  process.exit(1);
} finally {
  fs.unlinkSync(tmp);
}

let bad = 0;
for (const k of ["stand", "clin", "help", "prizes"]) {
  const present = ids.has(k);
  const filled = (store[k] || "").length;
  if (!present || !filled) bad++;
  console.log(
    `  #${k.padEnd(7)} ${present ? "in DOM" : "MISSING FROM DOM"}  ` +
    (filled ? `rendered ${filled} chars` : "*** RENDERED NOTHING ***"));
}
const all = Object.values(store).join("");
const checks = {
  "any-N-of-N": (all.match(/any (\d+) of these \1\b/g) || []).length,
  "any 0 of": (all.match(/any 0\b/g) || []).length,
  "sci notation": (all.match(/\de-\d/g) || []).length,
  "trailing-zero odds": (all.match(/\d\.\d*?0{4,}%/g) || []).length,
  // a clinched team legitimately shows 100%; what must never appear is a
  // *condition* that is certain, so only the elimination section is checked
  "100% conditions": ((store.help || "").match(/>100(\.\d+)?%</g) || []).length,
  "padded 100.0%": (all.match(/>100\.0+%</g) || []).length,
};
for (const [k, v] of Object.entries(checks)) {
  if (v) bad++;
  console.log(`  ${k.padEnd(20)} ${v}`);
}
console.log(`  bold tags            ${(all.match(/<b[ >]/g) || []).length}`);
process.exit(bad ? 1 : 0);
