/* AI TUTOR — engine
 * XP/levels · prereq-aware quest generator · SM-2 spaced repetition · boss battles · badges
 * No build step, no deps. State: localStorage + JSON export.
 */
(() => {
"use strict";

const C   = window.CURRICULUM  || {tracks:[], levels:[], badges:[], xp_table:{}};
const FC  = (window.FLASHCARDS || {}).flashcards || [];
const DR  = (window.DRILLS     || {}).drills     || [];
const PR  = (window.PROBLEMS   || {}).problems   || [];
const KEY = "ai-tutor-state-v2";

/* ---------------- state ---------------- */
const blank = () => ({
  xp: 0,
  modules: {},          // moduleId -> "doing" | "done"
  cards: {},            // cardId -> {ef, interval, due, reps, lapses}
  drills: {},           // drillId -> {seen:date}; absence = still due
  problems: {},         // problemId -> {solved:true, firstTry:bool, date}
  bosses: [],           // {round, score, max, date, weak:[]}
  badges: [],           // badge ids
  streak: {count:0, last:null},
  log: [],              // {t, what, xp}
});
let S = load();

function load(){
  try{
    const raw = localStorage.getItem(KEY);
    if(!raw) return blank();
    return Object.assign(blank(), JSON.parse(raw));
  }catch(e){ return blank(); }
}
function save(){ try{ localStorage.setItem(KEY, JSON.stringify(S)); }catch(e){} }

/* ---------------- helpers ---------------- */
const $  = (s, r=document) => r.querySelector(s);
const el = (t, cls, html) => { const n=document.createElement(t); if(cls)n.className=cls; if(html!=null)n.innerHTML=html; return n; };
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const today = () => new Date().toISOString().slice(0,10);
const allModules = () => C.tracks.flatMap(t => t.modules.map(m => ({...m, track:t})));

function award(xp, what){
  S.xp += xp;
  S.log.unshift({t:new Date().toISOString(), what, xp});
  S.log = S.log.slice(0,300);
  checkBadges();
  save(); renderHUD(); renderFoot();
}

function levelInfo(){
  const L = C.levels || [];
  let idx = 0;
  for(let i=0;i<L.length;i++) if(S.xp >= L[i].xp) idx = i;
  const cur = L[idx] || {xp:0,name:"—"};
  const next = L[idx+1] || null;
  const span = next ? next.xp - cur.xp : 1;
  const into = next ? S.xp - cur.xp : 1;
  return {level: idx+1, name: cur.name, next, pct: Math.min(100, Math.round(into/span*100))};
}

function trackProgress(t){
  const done = t.modules.filter(m => S.modules[m.id] === "done").length;
  return {done, total: t.modules.length, pct: t.modules.length ? done/t.modules.length*100 : 0};
}
/* A prereq counts as satisfied at 50%, not 100%. Requiring a full track would
   lock RAG behind all 15 agentic modules and make the weekend-3 schedule
   impossible. Enough foundation to start, not enough to skip it. */
const PREREQ_THRESHOLD = 50;
function trackDone(id){
  const t = C.tracks.find(x => x.id === id);
  return t ? trackProgress(t).pct >= PREREQ_THRESHOLD : true;
}
function unlocked(t){ return (t.prereqs||[]).every(trackDone); }
/* Sprint modules bypass track gating entirely — if it's in the 8-weekend set
   you need it now, regardless of how far along its track's prereqs are. */
function moduleAvailable(m){ return m.tags.includes("sprint") || unlocked(m.track); }
function lockReason(t){
  return (t.prereqs||[]).filter(id => !trackDone(id)).map(id => {
    const p = C.tracks.find(x => x.id === id);
    return p ? `${p.title} (${Math.round(trackProgress(p).pct)}%/${PREREQ_THRESHOLD}%)` : id;
  });
}

/* ---------------- SM-2 ---------------- */
function dueCards(){
  const d = today();
  return FC.filter(c => {
    const st = S.cards[c.id];
    return !st || st.due <= d;
  });
}
/* Intervals MUST be capped. Uncapped SM-2 grows as ef^reps, so ~15 straight
   "Easy" grades push the due date past year 200000, where toISOString() emits
   an expanded-year form ("+244857-07-01"). "+" is ASCII 43 and "2" is 50, so
   that string sorts BEFORE "2026-..." — meaning dueCards() would treat a
   perfectly-known card as due every single day, forever. A 365-day ceiling
   also matches the goal: see everything at least once a year. */
const MAX_INTERVAL_DAYS = 365;

function grade(cardId, q){          // q: 0 again · 3 hard · 4 good · 5 easy
  const st = S.cards[cardId] || {ef:2.5, interval:0, reps:0, lapses:0};
  if(q < 3){
    st.reps = 0; st.interval = 1; st.lapses++;
  }else{
    st.reps++;
    st.interval = st.reps === 1 ? 1
                : st.reps === 2 ? 6
                : Math.round(st.interval * st.ef);
    st.interval = Math.min(MAX_INTERVAL_DAYS, Math.max(1, st.interval));
    st.ef = Math.max(1.3, st.ef + (0.1 - (5-q)*(0.08 + (5-q)*0.02)));
  }
  const dt = new Date(); dt.setDate(dt.getDate() + st.interval);
  st.due = dt.toISOString().slice(0,10);
  S.cards[cardId] = st;
  award(C.xp_table.flashcard || 3, `card ${cardId} q=${q}`);
}

/* ---------------- streak ---------------- */
function touchStreak(){
  const now = new Date(), d = today();
  if(S.streak.last === d) return;
  const isWeekend = now.getDay() === 0 || now.getDay() === 6;
  if(!isWeekend){ S.streak.last = d; save(); return; }
  const prev = S.streak.last ? new Date(S.streak.last) : null;
  const gapDays = prev ? Math.round((now - prev)/864e5) : 99;
  S.streak.count = gapDays <= 9 ? S.streak.count + 1 : 1;   // allow one missed weekend day
  S.streak.last = d;
  save();
}

/* ---------------- badges ---------------- */
const BADGE_RULES = {
  "first-blood":    () => Object.values(S.modules).some(v => v === "done"),
  "pattern-complete": () => trackDone("T02"),
  "three-cloud":    () => ["C-AWS","C-AZ","C-GCP"].every(id => {
                          const t = C.tracks.find(x => x.id === id);
                          return t && t.modules.some(m => m.slug.includes("iam") && S.modules[m.id] === "done");
                        }),
  "boss-slayer":    () => S.bosses.filter(b => b.score/b.max >= 0.7).length >= 3,
  "full-loop":      () => S.bosses.some(b => b.round === "full-loop" && b.score/b.max >= 0.7),
  "streak-4":       () => S.streak.count >= 4,
  "streak-12":      () => S.streak.count >= 12,
  "monotonic":      () => PR.filter(p => (p.pattern||"").includes("monotonic") && S.problems[p.id]).length >= 10,
};
function checkBadges(){
  for(const [id, fn] of Object.entries(BADGE_RULES)){
    try{ if(!S.badges.includes(id) && fn()) S.badges.push(id); }catch(e){}
  }
}
function grantBadge(id){
  if(!S.badges.includes(id)){ S.badges.push(id); save(); toast(`Badge unlocked: ${id}`); render(); }
}

/* ---------------- quest generator ---------------- */
function nextQuest(){
  const mods = allModules();
  const avail = mods.filter(m => S.modules[m.id] !== "done" && moduleAvailable(m));
  /* Ranking is TIERED, not additive. The sprint tier must be strictly ordered by
     the roadmap's weekend sequence — an earlier additive version let the
     `critical` weight (-30) outrank sprint_order (range 0-25), which silently
     reshuffled the sprint and served weekend-5 attention before the weekend-1
     agent loop. Tiers make that class of bug impossible. */
  const rank = m => {
    if(m.tags.includes("sprint")) return -1e6 + (m.sprint_order || 0);
    let s = 0;
    if(m.track.phase === "A") s -= 100;
    if(m.tags.includes("critical")) s -= 30;
    if(S.modules[m.id] === "doing") s -= 60;
    s += m.track.id.charCodeAt(1) * 0.01 + m.order * 0.5;
    return s;
  };
  avail.sort((a,b) => rank(a) - rank(b));

  /* Budget is a ceiling, not a target: only take a module if it fits (or if
     nothing is picked yet). Checking `hours >= 9` after adding overshot to 12h. */
  const BUDGET = 9, SLACK = 0.5;
  const picked = [], seen = new Set();
  let hours = 0;
  for(const m of avail){
    if(hours >= BUDGET) break;
    if(picked.length && hours + m.hours > BUDGET + SLACK) continue;
    // sprint weekends deliberately stack 3-4 modules from one track (all of
    // weekend 2 is LangGraph) — don't let the diversity cap break the roadmap
    const cap = m.tags.includes("sprint") ? 4 : 2;
    if(picked.filter(p => p.track.id === m.track.id).length >= cap) continue;
    if(seen.has(m.id)) continue;
    seen.add(m.id); picked.push(m); hours += m.hours;
  }
  const bossDue = S.bosses.length < Math.floor(Object.values(S.modules).filter(v=>v==="done").length / 12);
  return {modules: picked, hours: Math.round(hours*10)/10, due: dueCards().length, bossDue};
}

/* ---------------- toast ---------------- */
let toastT;
function toast(msg){
  let n = $("#toast");
  if(!n){ n = el("div"); n.id="toast"; document.body.appendChild(n);
    Object.assign(n.style,{position:"fixed",bottom:"52px",left:"50%",transform:"translateX(-50%)",
      background:"var(--panel2)",border:"1px solid var(--acc)",color:"var(--acc)",padding:".5rem .9rem",
      borderRadius:"8px",fontSize:".78rem",zIndex:99,transition:"opacity .3s"}); }
  n.textContent = msg; n.style.opacity = "1";
  clearTimeout(toastT); toastT = setTimeout(() => n.style.opacity = "0", 2200);
}

/* ---------------- views ---------------- */
const V = {};

V.dash = () => {
  const q = nextQuest(), li = levelInfo();
  const wrap = el("div","grid g2");

  const quest = el("div","card hi");
  quest.innerHTML = `<div class="row"><h2>▸ THIS WEEKEND'S QUEST</h2>
    <span class="muted">${q.hours}h planned</span></div>
    <p class="muted" style="font-size:.75rem;margin:.2rem 0 .7rem">
      <span class="tag A">sprint</span> modules come first, in roadmap order — that sequence is
      the plan. <span class="tag crit">critical</span> marks what decides an interview.</p>`;
  if(!q.modules.length) quest.appendChild(el("div","empty","Nothing available — finish prerequisite tracks or add content."));
  q.modules.forEach(m => quest.appendChild(modRow(m)));
  if(q.due) quest.insertAdjacentHTML("beforeend",
    `<hr><div class="row"><span>🧠 <b>${q.due}</b> flashcards due</span>
     <button class="btn p" data-go="cards">Review now</button></div>`);
  if(q.bossDue) quest.insertAdjacentHTML("beforeend",
    `<hr><div class="row"><span>⚔️ <b>Boss battle unlocked</b></span>
     <button class="btn p" data-go="boss">Fight</button></div>`);
  wrap.appendChild(quest);

  const side = el("div","grid");
  side.appendChild(el("div","card",`
    <h2>◈ STATUS</h2>
    <div class="row"><span>Level ${li.level} — ${esc(li.name)}</span><span class="muted">${S.xp} XP</span></div>
    <div class="bar"><i style="width:${li.pct}%"></i></div>
    <small class="dimmer">${li.next ? `${li.next.xp - S.xp} XP to ${esc(li.next.name)}` : "Max level"}</small>
    <hr>
    <div class="row"><span>Modules</span><span>${Object.values(S.modules).filter(v=>v==="done").length} / ${C.totals?.modules ?? 0}</span></div>
    <div class="row"><span>Problems solved</span><span>${Object.keys(S.problems).length} / ${PR.length}</span></div>
    <div class="row"><span>Boss battles won</span><span>${S.bosses.filter(b=>b.score/b.max>=.7).length}</span></div>
    <div class="row"><span>Badges</span><span>${S.badges.length} / ${(C.badges||[]).length}</span></div>`));

  const sprintMods = allModules().filter(m => m.tags.includes("sprint"));
  const doneS = sprintMods.filter(m => S.modules[m.id] === "done");
  const hrsLeft = Math.round(sprintMods.filter(m => S.modules[m.id] !== "done")
                                       .reduce((a,m)=>a+m.hours,0));
  const phaseA = C.tracks.filter(t => t.phase === "A");
  const doneA = phaseA.reduce((a,t)=>a+trackProgress(t).done,0);
  const totA  = phaseA.reduce((a,t)=>a+t.modules.length,0);
  side.appendChild(el("div","card",`
    <h2>🔴 INTERVIEW SPRINT</h2>
    <small class="muted">The subset that decides loops. Everything else can wait.</small>
    <div class="bar"><i style="width:${sprintMods.length?doneS.length/sprintMods.length*100:0}%"></i></div>
    <small class="dimmer">${doneS.length} / ${sprintMods.length} modules · <b>${hrsLeft}h left</b>
      ≈ ${Math.ceil(hrsLeft/9)} weekends at 9h</small>
    <hr>
    <div class="row"><span class="muted">Phase A (core)</span><span class="muted">${doneA}/${totA}</span></div>
    <div class="row"><span class="muted">Everything</span><span class="muted">${
      Object.values(S.modules).filter(v=>v==="done").length}/${C.totals?.modules ?? 0} · ${C.totals?.hours ?? 0}h</span></div>`));

  const recent = el("div","card","<h2>◷ RECENT</h2>");
  if(!S.log.length) recent.appendChild(el("div","empty","No activity yet."));
  else recent.insertAdjacentHTML("beforeend","<table>" + S.log.slice(0,8).map(l =>
    `<tr><td class="muted">${l.t.slice(5,10)}</td><td>${esc(l.what)}</td><td style="color:var(--acc)">+${l.xp}</td></tr>`).join("") + "</table>");
  side.appendChild(recent);

  wrap.appendChild(side);
  return wrap;
};

function modRow(m){
  const st = S.modules[m.id] || "todo";
  const isBoss = m.track.id === "T15" || m.tags.includes("boss");
  const n = el("div","mod" + (moduleAvailable(m) ? "" : " locked"));
  n.innerHTML = `<span class="dot ${st==="done"?"done":st==="doing"?"doing":""}"></span>
    <span class="t"><b>${esc(m.title)}</b>
      <small class="dimmer">${m.track.icon} ${esc(m.track.title)} · ${m.hours}h
      ${m.tags.includes("sprint")?'<span class="tag A">sprint</span>':""}
      ${m.tags.includes("critical")?'<span class="tag crit">critical</span>':""}</small></span>`;
  /* Boss rounds are NOT completable as modules. Marking one "done" from here
     would award deepdive XP (10) instead of boss XP (200) and record no score,
     which silently corrupts the mock-score history the debrief relies on.
     Send the user to the Boss Battles tab instead. */
  if(isBoss){
    const b = el("button","btn sm p","fight →");
    b.onclick = () => { view = "boss"; render(); };
    n.appendChild(b);
    return n;
  }
  const b = el("button","btn sm", st==="done" ? "↺" : st==="doing" ? "✓ done" : "start");
  b.onclick = () => {
    if(st === "done"){ delete S.modules[m.id]; }
    else if(st === "doing"){ S.modules[m.id]="done"; touchStreak(); award(C.xp_table.deepdive||10, `module: ${m.title}`); }
    else { S.modules[m.id]="doing"; }
    save(); render();
  };
  n.appendChild(b);
  return n;
}

V.tracks = () => {
  const wrap = el("div","grid g2");
  ["A","B"].forEach(phase => {
    C.tracks.filter(t => t.phase === phase).forEach(t => {
      const p = trackProgress(t), lock = !unlocked(t);
      const c = el("div","card" + (lock ? " locked" : ""));
      c.innerHTML = `<div class="row">
          <h2>${t.icon} ${esc(t.title)}</h2>
          <span><span class="tag ${t.phase}">Phase ${t.phase}</span><span class="tag">${t.hours}h</span></span>
        </div>
        <div class="bar"><i style="width:${p.pct}%"></i></div>
        <small class="dimmer">${p.done}/${p.total} modules · <code>${esc(t.dir)}</code>
        ${lock ? ` · 🔒 needs ${esc(lockReason(t).join(", "))}` : ""}</small><hr>`;
      t.modules.forEach(m => c.appendChild(modRow({...m, track:t})));
      wrap.appendChild(c);
    });
  });
  return wrap;
};

V.cards = () => {
  const due = dueCards();
  const wrap = el("div");
  if(!FC.length) return el("div","empty",
    "No flashcards yet.<br><br>Run <code>/tutor-cheatsheet &lt;topic&gt;</code> in Claude — it writes the sheet and generates cards, then <code>python app/build_data.py</code>.");
  if(!due.length) return el("div","empty",`✓ All caught up. ${FC.length} cards in rotation.<br><small class="dimmer">Next due: ${
    (Object.values(S.cards).map(c=>c.due).sort()[0]) || "—"}</small>`);

  let i = 0, shown = false;
  const card = el("div","card fc");
  const bar  = el("div","card");
  const paint = () => {
    const c = due[i];
    if(!c){ wrap.innerHTML=""; wrap.appendChild(el("div","empty","✓ Session complete.")); return; }
    card.innerHTML = `<div class="q">${esc(c.q)}</div>` +
      (shown ? `<div class="a">${esc(c.a)}</div>` : `<div class="muted">— press Space / click Reveal —</div>`);
    const g = el("div","grades");
    if(!shown){
      const b = el("button","btn p","Reveal");
      b.onclick = () => { shown = true; paint(); };
      g.appendChild(b);
    }else{
      [["Again",0],["Hard",3],["Good",4],["Easy",5]].forEach(([label,q]) => {
        const b = el("button", q===0 ? "btn d" : q===4 ? "btn p" : "btn", label);
        b.onclick = () => { grade(due[i].id, q); i++; shown=false; paint(); };
        g.appendChild(b);
      });
    }
    card.appendChild(g);
    bar.innerHTML = `<div class="row"><span class="muted">${i+1} / ${due.length} due</span>
      <span class="muted">${esc(c.topic||"")}</span></div>
      <div class="bar"><i style="width:${i/due.length*100}%"></i></div>`;
  };
  const keys = e => { if(e.code === "Space"){ e.preventDefault(); if(!shown){ shown=true; paint(); } } };
  document.addEventListener("keydown", keys, {once:false});
  wrap._cleanup = () => document.removeEventListener("keydown", keys);
  wrap.appendChild(bar); wrap.appendChild(card); paint();
  return wrap;
};

/* ---------------- drills ---------------- */
/* 3,977 drills ship in the data bundle; before v0.4 they were loaded into
   every page and rendered nowhere. Due = not yet answered correctly ("knew
   it"). XP is awarded only on the first knew-it per drill id — re-entering
   the view never shows an already-cleared drill, so there is nothing to farm. */
V.drills = () => {
  const due = DR.filter(d => !S.drills[d.id]);
  const wrap = el("div");
  if(!DR.length) return el("div","empty",
    "No drills yet.<br><br>Run <code>/tutor-drill &lt;topic&gt;</code> in Claude — it writes drill fragments, then <code>python app/build_data.py</code> merges them.");
  if(!due.length) return el("div","empty",
    `✓ All ${DR.length} drills cleared.<br><small class="dimmer">Reset from Save/Load by importing state without <code>drills</code>.</small>`);

  let i = 0, revealed = false;
  const card = el("div","card fc");
  const bar  = el("div","card");
  const paint = () => {
    const d = due[i];
    if(!d){ wrap.innerHTML=""; wrap.appendChild(el("div","empty","✓ Session complete.")); return; }
    card.innerHTML = `<div class="q">${esc(d.q)}</div>
      <small class="dimmer">${esc(d.module||"")} · ${esc(d.difficulty||"")}</small>` +
      (revealed ? `<div class="a">${esc(d.a)}</div>`
                : `<div class="muted">— reveal when you've committed to an answer —</div>`);
    const g = el("div","grades");
    if(!revealed){
      const b = el("button","btn p","Reveal");
      b.onclick = () => { revealed = true; paint(); };
      g.appendChild(b);
    }else{
      /* XP guard: award only when this id was never cleared. The queue above
         already skips seen ids, but the guard makes double-award impossible
         even if state is edited between renders. */
      const ok = el("button","btn p","knew it");
      ok.onclick = () => {
        if(!S.drills[d.id]) award(C.xp_table.drill || 5, `drill: ${d.id}`);
        S.drills[d.id] = {seen: today()};
        save(); i++; revealed = false; paint();
      };
      const no = el("button","btn d","missed");
      no.onclick = () => { i++; revealed = false; paint(); };
      g.appendChild(ok); g.appendChild(no);
    }
    card.appendChild(g);
    bar.innerHTML = `<div class="row"><span class="muted">${i+1} / ${due.length} due</span>
      <span class="muted">${Object.keys(S.drills).length} / ${DR.length} cleared</span></div>
      <div class="bar"><i style="width:${(i)/due.length*100}%"></i></div>`;
  };
  wrap.appendChild(bar); wrap.appendChild(card); paint();
  return wrap;
};

V.problems = () => {
  const wrap = el("div");
  if(!PR.length) return el("div","empty",
    "No problem set loaded yet.<br><br>Problem fragments go in <code>app/data/problemsets/&lt;module-id&gt;.json</code>, then <code>python app/build_data.py</code> merges them.");
  const byPattern = {};
  PR.forEach(p => (byPattern[p.pattern] ||= []).push(p));
  Object.entries(byPattern).forEach(([pat, list]) => {
    const solved = list.filter(p => S.problems[p.id]).length;
    const c = el("div","card");
    c.innerHTML = `<div class="row"><h2>${esc(pat)}</h2><span class="muted">${solved}/${list.length}</span></div>
      <div class="bar"><i style="width:${solved/list.length*100}%"></i></div><hr>`;
    const tb = el("table");
    tb.innerHTML = "<tr><th>#</th><th>Problem</th><th>Diff</th><th></th></tr>";
    list.forEach(p => {
      const tr = el("tr");
      const done = !!S.problems[p.id];
      tr.innerHTML = `<td class="dimmer">${esc(p.id)}</td>
        <td>${p.url ? `<a href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.title)}</a>` : esc(p.title)}</td>
        <td class="muted">${esc(p.difficulty||"")}</td>`;
      const td = el("td");
      const b = el("button", done ? "btn sm p" : "btn sm", done ? "solved" : "mark");
      b.onclick = () => {
        if(done){ delete S.problems[p.id]; }
        else { S.problems[p.id] = {date: today()}; award(C.xp_table.problem||15, `problem: ${p.title}`); }
        save(); render();
      };
      td.appendChild(b); tr.appendChild(td); tb.appendChild(tr);
    });
    c.appendChild(tb); wrap.appendChild(c);
  });
  return wrap;
};

V.boss = () => {
  const rounds = (C.tracks.find(t => t.id === "T15")?.modules) || [];
  const wrap = el("div","grid g2");
  rounds.forEach(r => {
    const past = S.bosses.filter(b => b.round === r.slug);
    const best = past.length ? Math.max(...past.map(b => Math.round(b.score/b.max*100))) : null;
    const c = el("div","card" + (best >= 70 ? " hi" : ""));
    c.innerHTML = `<div class="row"><h2>${esc(r.title.replace(/^Boss: /,""))}</h2>
      <span class="muted">${best === null ? "unattempted" : best + "%"}</span></div>
      <small class="muted">Run in Claude:</small>
      <div><code>/tutor-mock ${esc(r.slug.replace("round-",""))}</code></div>
      <small class="dimmer">Attempts: ${past.length}${past.length ? " · last " + past[past.length-1].date : ""}</small>`;
    const f = el("div","row"); f.style.marginTop = ".6rem";
    const sc = el("input"); sc.type="number"; sc.placeholder="score"; sc.min=0; sc.max=100;
    Object.assign(sc.style,{width:"70px",background:"#080c11",color:"var(--fg)",
      border:"1px solid var(--line)",borderRadius:"6px",padding:".25rem .4rem",fontFamily:"var(--mono)"});
    const b = el("button","btn","log result");
    b.onclick = () => {
      const raw = parseInt(sc.value, 10);
      if(isNaN(raw)) return toast("Enter the score /100 from your mock transcript");
      /* the input's max=100 only constrains the spinner arrows, not typing —
         clamp so a 150 can't corrupt the score history /tutor-progress reads */
      const v = Math.max(0, Math.min(100, raw));
      S.bosses.push({round:r.slug, score:v, max:100, date:today(), weak:[]});
      touchStreak(); award(C.xp_table.boss || 200, `boss: ${r.title} (${v}%)`);
      save(); render();
    };
    f.appendChild(sc); f.appendChild(b); c.appendChild(f);
    wrap.appendChild(c);
  });
  return wrap;
};

V.badges = () => {
  const wrap = el("div","grid g3");
  (C.badges||[]).forEach(b => {
    const on = S.badges.includes(b.id);
    const c = el("div","badge" + (on ? " on" : ""));
    c.innerHTML = `<div class="i">${b.icon}</div><b>${esc(b.name)}</b><small>${esc(b.desc)}</small>`;
    if(!on){ const g = el("button","btn sm","claim"); g.style.marginTop=".5rem";
      g.onclick = () => grantBadge(b.id); c.appendChild(g); }
    wrap.appendChild(c);
  });
  return wrap;
};

V.save = () => {
  const wrap = el("div","grid");
  const c = el("div","card");
  c.innerHTML = `<h2>◆ EXPORT / IMPORT</h2>
    <small class="muted">Paste into <code>progress/progress.json</code> to version it, or to move browsers.
    <code>/tutor-progress</code> reads that file.</small>`;
  const ta = el("textarea"); ta.value = JSON.stringify(S, null, 2);
  const row = el("div","row"); row.style.marginTop=".6rem";
  const cp = el("button","btn p","Copy JSON");
  cp.onclick = async () => { try{ await navigator.clipboard.writeText(ta.value); toast("Copied"); }
                             catch(e){ ta.select(); toast("Select-all done — press Ctrl+C"); } };
  const im = el("button","btn","Import from box");
  im.onclick = () => { try{ S = Object.assign(blank(), JSON.parse(ta.value)); save(); render(); toast("Imported"); }
                       catch(e){ toast("Invalid JSON"); } };
  const rs = el("button","btn d","Reset everything");
  rs.onclick = () => { if(confirm("Wipe all progress?")){ S = blank(); save(); render(); } };
  row.appendChild(cp); row.appendChild(im); row.appendChild(rs);
  c.appendChild(ta); c.appendChild(row);
  wrap.appendChild(c);
  return wrap;
};

/* ---------------- render ---------------- */
let view = "dash", current = null;
function render(){
  if(current && current._cleanup) current._cleanup();
  const host = $("#app"); host.innerHTML = "";
  current = (V[view] || V.dash)();
  host.appendChild(current);
  document.querySelectorAll("#tabs button").forEach(b =>
    b.classList.toggle("active", b.dataset.view === view));
  renderHUD(); renderFoot();
}
function renderHUD(){
  const li = levelInfo();
  $("#hud-level").textContent = li.level;
  $("#hud-level-name").textContent = li.name;
  $("#hud-xp").textContent = S.xp;
  $("#hud-xpbar").style.width = li.pct + "%";
  $("#hud-streak").textContent = S.streak.count;
  $("#hud-due").textContent = dueCards().length;
}
function renderFoot(){
  const t = C.totals || {};
  $("#foot-stats").textContent =
    `${t.tracks||0} tracks · ${t.modules||0} modules · ${t.hours||0}h curriculum · v${C.version||"?"}`;
}

document.addEventListener("click", e => {
  const tab = e.target.closest("#tabs button");
  if(tab){ view = tab.dataset.view; render(); return; }
  const go = e.target.closest("[data-go]");
  if(go){ view = go.dataset.go; render(); }
});

touchStreak();
checkBadges();
render();
})();
