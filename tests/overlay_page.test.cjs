const { JSDOM } = require("jsdom"); const fs = require("fs");
let fails = 0; const ok = (c, m) => { console.log((c ? "PASS " : "FAIL ") + m); if (!c) fails++; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function make(file, cfg) {
  const state = { latest: 5, events: [] };
  const dom = new JSDOM(fs.readFileSync(file, "utf8"), { runScripts: "dangerously", pretendToBeVisual: true, beforeParse(w) {
    w.__POLL = 30; w.audioCalls = 0; w.AudioContext = function () { w.audioCalls++; throw new Error("no audio in test"); };
    w.fetch = (url) => { const after = Number(new URL(url, "http://x").searchParams.get("after"));
      const evs = after < 0 ? [] : state.events.filter((e) => e.id > after);
      return Promise.resolve({ json: () => Promise.resolve({ events: evs, latest: state.latest, cfg }) }); };
  } });
  return { dom, push(e) { e.id = ++state.latest; state.events.push(e); } };
}
(async () => {
  // ---- alerts ----
  let t = make(require("path").join(__dirname, "out", "alert.html"), { seconds: 0.3, showMessage: true, sound: false, colors: { a1: "#aa0000", a2: "#00aa00", a3: "#0000aa" } });
  const doc = t.dom.window.document, seen = [];
  new t.dom.window.MutationObserver((ms) => ms.forEach((m) => m.addedNodes.forEach((n) => { if (n.classList && n.classList.contains("alert")) seen.push(n.textContent); }))).observe(doc.getElementById("alertbox"), { childList: true });
  await sleep(150);
  ok(doc.querySelector(".alert") === null, "old alerts are not replayed when the page loads");
  t.push({ platform: "tip", name: "Rahul", amount: "₹100", message: "Great stream bhai" });
  t.push({ platform: "youtube", name: "<b>Evil</b>", amount: "₹50", message: '<img src=x onerror="window.hacked=1"> नमस्ते' });
  await sleep(250);
  ok(seen.length === 1 && seen[0].includes("Rahul") && seen[0].includes("₹100") && seen[0].includes("Great stream bhai") && seen[0].includes("Payment"), "first alert shows source, name, amount and message");
  ok(doc.querySelectorAll(".alert").length === 1, "second alert waits its turn (one on screen at a time)");
  ok(doc.documentElement.style.getPropertyValue("--a1") === "#aa0000", "theme colours from the app are applied");
  for (let i = 0; i < 80 && seen.length < 2; i++) await sleep(100);
  ok(seen.length === 2 && seen[1].includes("<b>Evil</b>") && seen[1].includes("नमस्ते"), "second alert appears after the first (HTML shown as plain text, Hindi works)");
  ok(doc.querySelector("img") === null && !t.dom.window.hacked, "no injected HTML or scripts can run");
  for (let i = 0; i < 100 && doc.querySelectorAll(".alert").length > 0; i++) await sleep(100);
  ok(doc.querySelectorAll(".alert").length === 0, "alerts remove themselves");
  ok(t.dom.window.audioCalls === 0, "no sound when sound is off");
  t.dom.window.close();
  // ---- message hidden / sound on ----
  t = make(require("path").join(__dirname, "out", "alert.html"), { seconds: 0.3, showMessage: false, sound: true, colors: {} });
  const d2 = t.dom.window.document; await sleep(120); t.push({ platform: "tip", name: "Sam", amount: "$5", message: "secret text" }); await sleep(250);
  ok(d2.querySelector(".alert") && !d2.querySelector(".msg") && t.dom.window.audioCalls === 1, "message hidden when turned off; chime attempted when sound is on");
  t.dom.window.close();
  // ---- chat ----
  t = make(require("path").join(__dirname, "out", "chat.html"), { chatSeconds: 0.4, maxLines: 8, colors: {} });
  const d3 = t.dom.window.document; await sleep(120);
  for (let i = 0; i < 10; i++) t.push({ platform: i % 2 ? "twitch" : "youtube", name: "u" + i, text: "msg " + i });
  await sleep(250);
  const lines = d3.querySelectorAll("#chatbox .m");
  ok(lines.length === 8 && lines[7].textContent.includes("msg 9") && !d3.getElementById("chatbox").textContent.includes("msg 0"), "chat keeps only the newest 8 lines");
  ok(lines[7].querySelector(".tag").textContent === "TWITCH" && lines[6].querySelector(".tag").textContent === "YOUTUBE", "platform tags shown");
  await sleep(1400); ok(d3.querySelectorAll("#chatbox .m").length === 0, "chat lines fade away after the set time");
  t.dom.window.close();
  console.log(fails ? fails + " FAILED" : "ALL PASSED"); process.exit(fails ? 1 : 0);
})();
