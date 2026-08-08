/* Focused tests on the SM-2 scheduler and streak logic extracted from app.js.
 * These are pure functions over state, so we test them directly against the
 * real source rather than through the DOM.
 */
const fs = require("fs");
const path = require("path");
const ROOT = path.resolve(process.argv[2] || path.join(__dirname, "../.."));
const src = fs.readFileSync(ROOT + "/app/app.js", "utf8");

// lift the SM-2 body out of app.js so we test the shipped algorithm, not a copy
const m = src.match(/function grade\(cardId, q\)\s*\{([\s\S]*?)\n\}/);
if (!m) { console.log("  ✗ could not locate grade() in app.js"); process.exit(1); }
const body = m[1];

const results = [];
const T = (n, f) => { try { f(); results.push(["✓", n, ""]); } catch (e) { results.push(["✗", n, e.message]); } };
const assert = (c, msg) => { if (!c) throw new Error(msg); };
// derive expected dates from the real clock — never hardcode, or the suite
// becomes a time bomb that fails at the next date rollover
const plusDays = (n) => { const d = new Date(); d.setDate(d.getDate() + n);
                          return d.toISOString().slice(0, 10); };

// pull the cap constant out of app.js too, so the test uses the shipped value
const capMatch = src.match(/const MAX_INTERVAL_DAYS\s*=\s*(\d+)/);
if (!capMatch) { console.log("  ✗ MAX_INTERVAL_DAYS not found in app.js — interval cap missing!"); process.exit(1); }
const CAP = Number(capMatch[1]);

function makeGrader() {
  const S = { cards: {}, xp: 0, log: [] };
  const C = { xp_table: { flashcard: 3 } };
  const award = (xp) => { S.xp += xp; };
  const today = () => new Date().toISOString().slice(0, 10);
  const grade = new Function("S", "C", "award", "today", "MAX_INTERVAL_DAYS", "cardId", "q", body)
    .bind(null, S, C, award, today, CAP);
  return { S, grade };
}

T("first 'Good' schedules 1 day out", () => {
  const { S, grade } = makeGrader();
  grade("c1", 4);
  assert(S.cards.c1.interval === 1, "interval should be 1, got " + S.cards.c1.interval);
  assert(S.cards.c1.reps === 1, "reps should be 1");
  assert(S.cards.c1.due === plusDays(1), "due should be tomorrow, got " + S.cards.c1.due);
});

T("second 'Good' schedules 6 days out", () => {
  const { S, grade } = makeGrader();
  grade("c1", 4); grade("c1", 4);
  assert(S.cards.c1.interval === 6, "interval should be 6, got " + S.cards.c1.interval);
  assert(S.cards.c1.due === plusDays(6), "due should be +6d, got " + S.cards.c1.due);
});

T("third+ review multiplies by ease factor", () => {
  const { S, grade } = makeGrader();
  grade("c1", 4); grade("c1", 4); grade("c1", 4);
  assert(S.cards.c1.interval > 6, "interval should grow past 6, got " + S.cards.c1.interval);
  assert(S.cards.c1.reps === 3, "reps should be 3");
});

T("'Again' resets reps and interval, counts a lapse", () => {
  const { S, grade } = makeGrader();
  grade("c1", 4); grade("c1", 4); grade("c1", 4);
  const beforeEf = S.cards.c1.ef;
  grade("c1", 0);
  assert(S.cards.c1.reps === 0, "reps should reset to 0, got " + S.cards.c1.reps);
  assert(S.cards.c1.interval === 1, "interval should reset to 1, got " + S.cards.c1.interval);
  assert(S.cards.c1.lapses === 1, "lapse not counted");
  assert(S.cards.c1.ef === beforeEf, "ef must not change on a lapse (SM-2 behaviour)");
});

T("ease factor rises on Easy, falls on Hard", () => {
  const a = makeGrader(); a.grade("c1", 5); a.grade("c1", 5);
  const b = makeGrader(); b.grade("c1", 3); b.grade("c1", 3);
  assert(a.S.cards.c1.ef > 2.5, "Easy should raise ef, got " + a.S.cards.c1.ef);
  assert(b.S.cards.c1.ef < 2.5, "Hard should lower ef, got " + b.S.cards.c1.ef);
});

T("ease factor floors at 1.3", () => {
  const { S, grade } = makeGrader();
  for (let i = 0; i < 40; i++) grade("c1", 3);
  assert(S.cards.c1.ef >= 1.3, "ef fell below floor: " + S.cards.c1.ef);
  assert(S.cards.c1.ef <= 1.31, "ef should be pinned at the 1.3 floor, got " + S.cards.c1.ef);
});

T("intervals stay capped and dates well-formed over 40 easy reviews", () => {
  const { S, grade } = makeGrader();
  for (let i = 0; i < 40; i++) grade("c1", 5);
  assert(Number.isFinite(S.cards.c1.interval), "interval went non-finite");
  assert(S.cards.c1.interval <= 365, "interval exceeded the 365d cap: " + S.cards.c1.interval);
  assert(/^\d{4}-\d{2}-\d{2}$/.test(S.cards.c1.due), "due date malformed: " + S.cards.c1.due);
});

T("a well-known card does NOT sort as due today (the regression)", () => {
  const { S, grade } = makeGrader();
  for (let i = 0; i < 30; i++) grade("c1", 5);
  // dueCards() compares date strings: st.due <= today
  assert(!(S.cards.c1.due <= plusDays(0)),
    "mastered card reads as due today — due=" + S.cards.c1.due);
});

T("XP is awarded per review", () => {
  const { S, grade } = makeGrader();
  grade("c1", 4); grade("c2", 4);
  assert(S.xp === 6, "expected 6 XP for 2 reviews, got " + S.xp);
});

// ---- streak logic -------------------------------------------------------
const sm = src.match(/function touchStreak\(\)\s*\{([\s\S]*?)\n\}/);
T("streak function exists and is weekend-aware", () => {
  assert(sm, "touchStreak not found");
  assert(/getDay\(\)\s*===\s*0\s*\|\|.*getDay\(\)\s*===\s*6/.test(sm[1]),
    "streak does not check for weekend days");
  assert(/gapDays\s*<=\s*9/.test(sm[1]), "no grace window for a missed weekend");
});

for (const [st, n, msg] of results) console.log(`  ${st} ${n}${msg ? "  → " + msg : ""}`);
const fails = results.filter(r => r[0] === "✗");
console.log(`\n  ${results.length - fails.length}/${results.length} passed`);
if (fails.length) process.exit(1);
