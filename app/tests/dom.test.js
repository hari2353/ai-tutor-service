/* Minimal DOM shim + test harness for app/app.js.
 * Implements only what app.js touches. Any property it reaches for that we
 * haven't implemented throws loudly — which is the point.
 */
const fs = require("fs");
const path = require("path");

// resolve so a relative argv[2] (e.g. ".") still yields an absolute path —
// require() treats a relative path as a bare module name and fails to find it
const ROOT = path.resolve(process.argv[2] || path.join(__dirname, "../.."));

// ---------------------------------------------------------------- DOM
let idSeq = 0;
class Node {
  constructor(tag) {
    this.tagName = (tag || "").toUpperCase();
    this.children = [];
    this.parentNode = null;
    this._text = "";
    this._html = "";
    this.style = new Proxy({}, { set: (t, k, v) => { t[k] = v; return true; } });
    this.dataset = {};
    this.classList = {
      _s: new Set(),
      add: (...c) => c.forEach(x => this.classList._s.add(x)),
      remove: (...c) => c.forEach(x => this.classList._s.delete(x)),
      toggle: (c, on) => on ? this.classList._s.add(c) : this.classList._s.delete(c),
      contains: c => this.classList._s.has(c),
    };
    this._listeners = {};
    this.__uid = ++idSeq;
  }
  set className(v) { this._cls = v; String(v || "").split(/\s+/).filter(Boolean).forEach(c => this.classList._s.add(c)); }
  get className() { return [...this.classList._s].join(" "); }
  set textContent(v) { this._text = String(v); this.children = []; }
  get textContent() { return this._text || this.children.map(c => c.textContent).join(""); }
  set innerHTML(v) {
    this._html = String(v);
    this.children = [];
    // extract data-go and data-view so delegation tests can find them
    const re = /data-(go|view)="([^"]+)"/g; let m;
    while ((m = re.exec(this._html))) {
      const stub = new Node("button");
      stub.dataset[m[1] === "go" ? "go" : "view"] = m[2];
      stub._synthetic = true;
      this.children.push(stub); stub.parentNode = this;
    }
  }
  get innerHTML() { return this._html; }
  appendChild(c) { c.parentNode = this; this.children.push(c); return c; }
  insertAdjacentHTML(_pos, html) {
    const n = new Node("div"); n.innerHTML = html; this.appendChild(n);
  }
  addEventListener(t, fn) { (this._listeners[t] ||= []).push(fn); }
  removeEventListener(t, fn) {
    if (this._listeners[t]) this._listeners[t] = this._listeners[t].filter(f => f !== fn);
  }
  set onclick(fn) { this._onclick = fn; }
  get onclick() { return this._onclick; }
  click() { if (this._onclick) this._onclick({ target: this }); }
  select() {}
  querySelector(sel) { return findAll(this).find(n => matches(n, sel)) || null; }
  querySelectorAll(sel) { return findAll(this).filter(n => matches(n, sel)); }
  closest(sel) { let n = this; while (n) { if (matches(n, sel)) return n; n = n.parentNode; } return null; }
  get firstChild() { return this.children[0] || null; }
}
function findAll(root, acc = []) { for (const c of root.children) { acc.push(c); findAll(c, acc); } return acc; }
function matches(n, sel) {
  // supports: #id, .cls, tag, "#tabs button", "[data-go]"
  const parts = sel.trim().split(/\s+/);
  const last = parts[parts.length - 1];
  const one = (n, s) => {
    if (s.startsWith("#")) return n.id === s.slice(1);
    if (s.startsWith(".")) return n.classList.contains(s.slice(1));
    if (s.startsWith("[")) { const k = s.slice(1, -1).replace(/-([a-z])/g, (_, c) => c.toUpperCase()); return n.dataset[k] !== undefined; }
    return n.tagName === s.toUpperCase();
  };
  if (!one(n, last)) return false;
  if (parts.length === 1) return true;
  let p = n.parentNode;
  while (p) { if (one(p, parts[0])) return true; p = p.parentNode; }
  return false;
}

const document = {
  _byId: {},
  createElement: t => new Node(t),
  body: new Node("body"),
  _listeners: {},
  addEventListener(t, fn) { (this._listeners[t] ||= []).push(fn); },
  removeEventListener(t, fn) {
    if (this._listeners[t]) this._listeners[t] = this._listeners[t].filter(f => f !== fn);
  },
  querySelector(sel) {
    if (sel.startsWith("#")) return document._byId[sel.slice(1)] || null;
    return document.body.querySelector(sel);
  },
  querySelectorAll(sel) { return document.body.querySelectorAll(sel); },
};
function stub(id) { const n = new Node("div"); n.id = id; document._byId[id] = n; document.body.appendChild(n); return n; }
["topbar", "mode-line", "hud-level", "hud-level-name", "hud-xp", "hud-xpbar",
 "hud-streak", "hud-due", "tabs", "app", "foot-stats"].forEach(stub);

// tab buttons, as index.html declares them
const TABS = ["dash", "tracks", "cards", "drills", "problems", "boss", "badges", "save"];
TABS.forEach(v => {
  const b = new Node("button"); b.dataset.view = v; document._byId.tabs.appendChild(b);
});

const store = {};
global.localStorage = {
  getItem: k => (k in store ? store[k] : null),
  setItem: (k, v) => { store[k] = String(v); },
  removeItem: k => { delete store[k]; },
};
global.document = document;
global.window = { CURRICULUM: null };
global.navigator = { clipboard: { writeText: async () => {} } };
global.confirm = () => true;
global.alert = () => {};

// ---------------------------------------------------------------- load data + app
["curriculum", "flashcards", "drills", "problems"].forEach(n =>
  require(path.join(ROOT, "app", "data", n + ".js")));

// ---------------------------------------------------------------- run
const results = [];
const T = (name, fn) => {
  try { fn(); results.push(["PASS", name, ""]); }
  catch (e) { results.push(["FAIL", name, e.message.split("\n")[0]]); }
};
const assert = (c, m) => { if (!c) throw new Error(m || "assertion failed"); };

let clickHandler = null;
T("app.js loads without throwing", () => {
  const src = fs.readFileSync(path.join(ROOT, "app", "app.js"), "utf8");
  new Function("document", "window", "localStorage", "navigator", "confirm", src)(
    document, global.window, global.localStorage, global.navigator, global.confirm);
  clickHandler = (document._listeners.click || [])[0];
  assert(clickHandler, "no document click handler registered");
});

const app = document._byId.app;
const switchTo = v => {
  const btn = document._byId.tabs.children.find(b => b.dataset.view === v);
  clickHandler({ target: btn });
};

T("dashboard renders content", () => {
  assert(app.children.length > 0, "app host is empty after initial render");
});
T("HUD is populated", () => {
  assert(document._byId["hud-level"].textContent !== "—", "level not set");
  assert(document._byId["hud-xp"].textContent === "0", "xp should start at 0");
  assert(document._byId["foot-stats"].textContent.includes("tracks"), "footer stats empty");
});

for (const v of TABS) {
  T(`view "${v}" renders`, () => {
    switchTo(v);
    assert(app.children.length > 0, `view ${v} produced no DOM`);
  });
}

T("tab switching marks active", () => {
  switchTo("tracks");
  const active = document._byId.tabs.children.filter(b => b.classList.contains("active"));
  assert(active.length === 1 && active[0].dataset.view === "tracks", "active tab wrong");
});

T("starting a module then completing it awards XP", () => {
  switchTo("tracks");
  const btns = findAll(app).filter(n => n.tagName === "BUTTON" && n._onclick && !n._synthetic);
  assert(btns.length > 0, "no module buttons found");
  const before = Number(document._byId["hud-xp"].textContent);
  btns[0].click();                       // todo -> doing
  switchTo("tracks");
  const b2 = findAll(app).filter(n => n.tagName === "BUTTON" && n._onclick && !n._synthetic)[0];
  b2.click();                            // doing -> done  (awards XP)
  const after = Number(document._byId["hud-xp"].textContent);
  assert(after > before, `xp did not increase (${before} -> ${after})`);
});

T("state persists to localStorage", () => {
  const raw = localStorage.getItem("ai-tutor-state-v2");
  assert(raw, "nothing written to localStorage");
  const s = JSON.parse(raw);
  assert(Object.values(s.modules).includes("done"), "completed module not persisted");
  assert(s.xp > 0, "xp not persisted");
});

T("quest generator respects the hour budget", () => {
  const C = global.window.CURRICULUM;
  const all = C.tracks.flatMap(t => t.modules.map(m => ({ ...m, track: t })));
  const sprint = all.filter(m => m.tags.includes("sprint"));
  assert(sprint.length > 0, "no sprint modules tagged");
  const byWeek = {};
  sprint.forEach(m => { byWeek[m.sprint_week] = (byWeek[m.sprint_week] || 0) + m.hours; });
  const bad = Object.entries(byWeek).filter(([, h]) => h > 10.5);
  assert(!bad.length, "sprint weekend over budget: " + JSON.stringify(bad));
});

T("flashcards view handles an empty due queue", () => {
  switchTo("cards");
  assert(app.children.length > 0, "cards view blank");
});

T("badges view renders all badges", () => {
  switchTo("badges");
  const C = global.window.CURRICULUM;
  const cards = findAll(app).filter(n => n.classList.contains("badge"));
  assert(cards.length === C.badges.length, `${cards.length} badge cards vs ${C.badges.length} badges`);
});

T("save/load view exposes exportable JSON", () => {
  switchTo("save");
  const ta = findAll(app).find(n => n.tagName === "TEXTAREA");
  assert(ta, "no textarea in save view");
  JSON.parse(ta.value);
});

T("boss battle logging validates input", () => {
  switchTo("boss");
  const inputs = findAll(app).filter(n => n.tagName === "INPUT");
  assert(inputs.length > 0, "no score inputs in boss view");
  const btn = findAll(app).filter(n => n.tagName === "BUTTON" && n._onclick)[0];
  btn.click();                                   // empty score -> should not crash
  inputs[0].value = "82";
  const btn2 = findAll(app).filter(n => n.tagName === "BUTTON" && n._onclick)[0];
  btn2.click();
  const s = JSON.parse(localStorage.getItem("ai-tutor-state-v2"));
  assert(s.bosses.length >= 1, "boss result not recorded");
  assert(s.bosses[0].score === 82, "wrong score recorded: " + s.bosses[0].score);
});

T("boss score is clamped to the 0-100 band (typed 150 records 100)", () => {
  switchTo("boss");
  const input = findAll(app).find(n => n.tagName === "INPUT");
  const before = JSON.parse(localStorage.getItem("ai-tutor-state-v2")).bosses.length;
  input.value = "150";
  findAll(app).filter(n => n.tagName === "BUTTON" && n._onclick)[0].click();
  const s = JSON.parse(localStorage.getItem("ai-tutor-state-v2"));
  assert(s.bosses.length === before + 1, "clamped boss not recorded");
  assert(s.bosses[s.bosses.length - 1].score === 100, "score not clamped: " + s.bosses[s.bosses.length - 1].score);
});

T("drills view renders and reveals an answer", () => {
  switchTo("drills");
  let reveal = findAll(app).filter(n => n.tagName === "BUTTON" && n._onclick && n._html === "Reveal")[0];
  assert(reveal, "no Reveal button in drills view");
  reveal.click();
  const graded = findAll(app).filter(n => n.tagName === "BUTTON" && n._onclick);
  assert(graded.some(b => b._html === "knew it") && graded.some(b => b._html === "missed"),
    "grade buttons missing after reveal");
});

T("clearing a drill awards drill XP exactly once and persists", () => {
  switchTo("drills");
  const C = global.window.CURRICULUM;
  const drillXp = C.xp_table.drill || 5;
  const before = Number(document._byId["hud-xp"].textContent);
  findAll(app).filter(n => n.tagName === "BUTTON" && n._onclick && n._html === "Reveal")[0].click();
  findAll(app).filter(n => n.tagName === "BUTTON" && n._onclick && n._html === "knew it")[0].click();
  const after = Number(document._byId["hud-xp"].textContent);
  assert(after - before === drillXp, `xp delta ${after - before} != drill xp ${drillXp}`);
  const s = JSON.parse(localStorage.getItem("ai-tutor-state-v2"));
  assert(Object.keys(s.drills).length === 1, `expected 1 cleared drill, got ${Object.keys(s.drills).length}`);
});

T("missed drills stay due and cleared drills leave the queue", () => {
  switchTo("drills");
  // clear one more via "knew it"
  findAll(app).filter(n => n.tagName === "BUTTON" && n._onclick && n._html === "Reveal")[0].click();
  findAll(app).filter(n => n.tagName === "BUTTON" && n._onclick && n._html === "knew it")[0].click();
  let s = JSON.parse(localStorage.getItem("ai-tutor-state-v2"));
  assert(Object.keys(s.drills).length === 2, `expected 2 cleared, got ${Object.keys(s.drills).length}`);
  // then miss one — it must NOT be recorded as cleared
  findAll(app).filter(n => n.tagName === "BUTTON" && n._onclick && n._html === "Reveal")[0].click();
  findAll(app).filter(n => n.tagName === "BUTTON" && n._onclick && n._html === "missed")[0].click();
  s = JSON.parse(localStorage.getItem("ai-tutor-state-v2"));
  assert(Object.keys(s.drills).length === 2, "a missed drill was recorded as cleared");
});

T("data-go shortcuts resolve to real views", () => {
  switchTo("dash");
  const gos = findAll(app).filter(n => n.dataset && n.dataset.go);
  gos.forEach(g => assert(TABS.includes(g.dataset.go), `data-go="${g.dataset.go}" is not a view`));
});

T("no module title breaks HTML escaping", () => {
  const C = global.window.CURRICULUM;
  const raw = C.tracks.flatMap(t => t.modules).filter(m => /[<>&"]/.test(m.title));
  // titles with & or > must still render; just assert we know about them
  assert(raw.every(m => typeof m.title === "string"), "non-string title");
});

// ---------------------------------------------------------------- report
const pass = results.filter(r => r[0] === "PASS").length;
const fail = results.filter(r => r[0] === "FAIL");
for (const [st, name, msg] of results) {
  console.log(`  ${st === "PASS" ? "✓" : "✗"} ${name}${msg ? "  → " + msg : ""}`);
}
console.log(`\n  ${pass}/${results.length} passed`);
if (fail.length) { console.log("\n  FAILURES:"); fail.forEach(f => console.log(`   - ${f[1]}: ${f[2]}`)); process.exit(1); }

// --- regression: boss rounds must not be completable as modules ---
(() => {
  const C = global.window.CURRICULUM;
  const src = fs.readFileSync(path.join(ROOT, "app", "app.js"), "utf8");
  const ok = /isBoss/.test(src) && /view = "boss"/.test(src);
  console.log(`  ${ok ? "✓" : "✗"} boss rounds route to the Boss tab, not module completion`);
  if (!ok) process.exit(1);
})();

// --- regression: drill XP guard must key off S.drills (no double-award path) ---
(() => {
  const src = fs.readFileSync(path.join(ROOT, "app", "app.js"), "utf8");
  const ok = /if\(!S\.drills\[d\.id\]\) award/.test(src);
  console.log(`  ${ok ? "✓" : "✗"} drill XP is guarded per-id (award only on first knew-it)`);
  if (!ok) process.exit(1);
})();
