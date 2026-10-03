// Offline test of the worker with a fake KV and a fake Discord. Run: node test.mjs
import worker from "./src/index.js";

const store = new Map();
const KV = { async get(k) { return store.has(k) ? store.get(k) : null; }, async put(k, v) { store.set(k, v); }, async delete(k) { store.delete(k); } };
const env = { KV, DISCORD_CLIENT_ID: "CID", DISCORD_CLIENT_SECRET: "SEC", DISCORD_BOT_TOKEN: "BOT" };
const puts = [];
let memberOk = true, roleStatus = 204;
let invitesNow = [], membersNow = [], invitesStatus = 200, membersStatus = 200, memberCalls = 0;
const putsFull = [];

globalThis.fetch = async (url, init = {}) => {
  const u = new URL(url), p = u.pathname.replace("/api/v10", ""), m = init.method || "GET";
  const j = (o, s = 200) => new Response(JSON.stringify(o), { status: s });
  if (p === "/oauth2/token") {
    const body = new URLSearchParams(init.body);
    if (body.get("client_secret") === "BAD") return j({ error: "invalid_client" }, 401);
    return body.get("redirect_uri").includes("/setup/") ? j({ access_token: "AT", guild: { id: "G1", name: "Test Server" } }) : j({ access_token: "AT2" });
  }
  if (p === "/users/@me") return j({ id: "U1", username: "rahul", global_name: "Rahul" });
  if (p === "/guilds/G1/members/U1" && m === "GET") return memberOk ? j({ user: { id: "U1" } }) : j({}, 404);
  if (p === "/guilds/G1/roles") return j([{ id: "1", name: "@everyone", position: 0 }, { id: "100001", name: "Verified", position: 3 }, { id: "100002", name: "Regular", position: 2 }, { id: "100003", name: "Supporter", position: 4 }, { id: "9", name: "BotRole", managed: true, position: 5 }]);
  if (m === "PUT" && /^\/guilds\/G1\/members\/\w+\/roles\/\w+$/.test(p)) { const [, , , , u, , r] = p.split("/"); puts.push(r); putsFull.push(u + ":" + r); return new Response(null, { status: roleStatus }); }
  if (p === "/guilds/G1/invites") return invitesStatus === 200 ? j(invitesNow) : j({}, invitesStatus);
  if (p === "/guilds/G1/members") { memberCalls++; return membersStatus === 200 ? j(membersNow) : j({}, membersStatus); }
  return j({}, 404);
};

let fails = 0;
const ok = (c, msg) => { console.log((c ? "PASS " : "FAIL ") + msg); if (!c) fails++; };
const call = (path, opts) => worker.fetch(new Request("https://cv.example" + path, opts), env);
const stateFrom = (res) => new URL(res.headers.get("location")).searchParams.get("state");

// 1. bot setup
let r = await call("/setup");
ok(r.status === 302 && r.headers.get("location").includes("permissions=268435488"), "setup redirects to Discord with Manage Roles");
r = await call("/setup/callback?code=abc&state=" + stateFrom(r));
let html = await r.text();
const token = html.match(/<code>([a-z0-9]{40})<\/code>/)?.[1];
ok(r.status === 200 && token, "setup callback shows a server key");
r = await call("/setup/callback?code=abc&state=bogus"); ok(r.status === 400, "bad state rejected");

// 2. auth + config + roles
const H = { Authorization: "Bearer " + token, "content-type": "application/json" };
r = await call("/api/config", { headers: { Authorization: "Bearer nope" } }); ok(r.status === 401, "wrong key -> 401");
r = await call("/api/roles", { headers: H }); const roles = (await r.json()).roles;
ok(roles.length === 3 && roles[0].name === "Supporter", "roles listed (no @everyone / bot roles), highest first");
r = await call("/api/config", { method: "PUT", headers: H, body: JSON.stringify({ verifiedRole: "100001", regularRole: "100002", supporterRole: "100003", regularMsgs: 3 }) });
ok((await r.json()).ok, "config saved");
r = await call("/api/config", { method: "PUT", headers: H, body: JSON.stringify({ verifiedRole: "evil" }) }); ok(r.status === 400, "bad role id rejected");

// 3. viewer link flow
r = await call("/link/G1"); ok(r.status === 302, "link page redirects to Discord login");
const lstate = stateFrom(r);
memberOk = false;
let rr = await call("/link/callback?code=x&state=" + lstate); ok(rr.status === 403, "not in server -> asked to join first");
memberOk = true;
r = await call("/link/G1"); r = await call("/link/callback?code=x&state=" + stateFrom(r));
html = await r.text(); const code = html.match(/!link ([A-Z0-9]{4}-[A-Z0-9]{4})/)?.[1];
ok(code, "viewer gets a code: " + code);

// 4. app claims the code from chat
r = await call("/api/claim", { method: "POST", headers: H, body: JSON.stringify({ code: "ZZZZ-ZZZZ", platform: "youtube", uid: "UC1" }) }); ok(r.status === 404, "unknown code rejected");
r = await call("/api/claim", { method: "POST", headers: H, body: JSON.stringify({ code, platform: "youtube", uid: "UC1" }) });
let res = await r.json(); ok(res.ok && res.roleGranted && res.discordName === "Rahul", "claim links the account and grants Verified");
ok(puts.includes("100001"), "Discord got Verified role request");
r = await call("/api/claim", { method: "POST", headers: H, body: JSON.stringify({ code, platform: "youtube", uid: "UC2" }) }); ok(r.status === 404, "code is single-use");
r = await call("/api/links", { headers: H }); ok((await r.json()).keys[0] === "youtube:UC1", "links list returned to the app");

// 5. app reports a threshold -> role is granted (counting happens in the app, so the cloud writes almost nothing)
const grant = (role, uid = "UC1", platform = "youtube") => call("/api/grant", { method: "POST", headers: H, body: JSON.stringify({ platform, uid, role }) });
puts.length = 0; roleStatus = 204;
r = await grant("regular"); res = await r.json(); ok(res.ok && puts.includes("100002"), "regular role granted through /api/grant");
r = await grant("supporter"); res = await r.json(); ok(res.ok && puts.includes("100003"), "supporter role granted through /api/grant");
r = await grant("regular", "nobody"); ok(r.status === 404, "unlinked viewer cannot be granted a role");
r = await grant("admin"); ok(r.status === 400, "unknown role name rejected");

// 6. failure reporting (bot role too low)
roleStatus = 403;
r = await grant("regular"); res = await r.json(); ok(!res.ok && res.status === 403, "403 from Discord is reported to the app");
roleStatus = 204;

// 7. the failures that used to show Cloudflare's "Error 1101"
const badEnv = { ...env, DISCORD_CLIENT_SECRET: "BAD" };
let st = await worker.fetch(new Request("https://cv.example/setup"), badEnv); const bst = stateFrom(st);
r = await worker.fetch(new Request("https://cv.example/setup/callback?code=x&state=" + bst), badEnv);
html = await r.text(); ok(r.status === 400 && html.includes("invalid_client") && html.includes("Client Secret"), "wrong secret -> readable page, not error 1101");
r = await worker.fetch(new Request("https://cv.example/setup"), { KV });
html = await r.text(); ok(r.status === 500 && html.includes("DISCORD_CLIENT_ID"), "missing secrets -> page that names them");
r = await worker.fetch(new Request("https://cv.example/health"), { KV, DISCORD_CLIENT_ID: "12345678901234567890", DISCORD_CLIENT_SECRET: "x", DISCORD_BOT_TOKEN: "" });
const h = await r.json(); ok(h.DISCORD_CLIENT_ID.looks_right && !h.DISCORD_CLIENT_SECRET.looks_right && !h.DISCORD_BOT_TOKEN.set, "/health reports which settings are missing or look wrong");
const broken = { ...env, KV: { async get() { return null; }, async put() { throw new Error("storage down"); }, async delete() {} } };
r = await worker.fetch(new Request("https://cv.example/setup"), broken); ok(r.status === 500 && (await r.text()).includes("storage down"), "unexpected crash -> readable page");


// 8. payments: Razorpay webhook -> D1 queue -> app
class FakeDB {
  constructor() { this.rows = []; this.seq = 0; }
  prepare(sql) {
    const self = this;
    return { args: [], bind(...a) { this.args = a; return this; },
      async run() {
        if (sql.startsWith("INSERT OR IGNORE")) {
          const [guild, pay_id, ts, name, message, amount, currency, display] = this.args;
          if (!self.rows.some((x) => x.guild === guild && x.pay_id === pay_id)) self.rows.push({ seq: ++self.seq, guild, pay_id, ts, name, message, amount, currency, display });
        }
        if (sql.startsWith("DELETE")) self.rows = self.rows.filter((x) => x.ts >= this.args[0]);
        return {};
      },
      async first() { const m = self.rows.filter((x) => x.guild === this.args[0]).reduce((a, x) => Math.max(a, x.seq), 0); return { m }; },
      async all() { return { results: self.rows.filter((x) => x.guild === this.args[0] && x.seq > this.args[1]).slice(0, 20) }; } };
  }
}
env.DB = new FakeDB();
const { createHmac } = await import("node:crypto");
const SECRET = "whsec_test_123";
r = await call("/api/config", { method: "PUT", headers: H, body: JSON.stringify({ verifiedRole: "100001", regularRole: "100002", supporterRole: "100003", regularMsgs: 3, razorpaySecret: SECRET }) });
let cfgRes = await r.json();
ok(cfgRes.ok && cfgRes.config.hasRazorpaySecret && cfgRes.config.hookUrl.includes("/hook/razorpay/") && !JSON.stringify(cfgRes).includes(SECRET), "secret saved, hook URL created, secret never sent back");
const hookPath = new URL(cfgRes.config.hookUrl).pathname;
r = await call("/api/config", { headers: H }); const got = await r.json();
ok(got.config.verifiedRole === "100001" && got.config.hasRazorpaySecret, "role settings survive when payment settings are saved");

r = await call("/api/config", { method: "PUT", headers: H, body: JSON.stringify({ razorpaySecret: SECRET }) });
r = await call("/api/config", { headers: H }); const kept = (await r.json()).config;
ok(kept.supporterRole === "100003" && kept.regularMsgs === 3 && kept.hasRazorpaySecret, "saving only the payment secret does not wipe the role settings");

const payEvent = (id, notes, amount = 10000, currency = "INR", event = "payment.captured") =>
  JSON.stringify({ event, payload: { payment: { entity: { id, amount, currency, notes } } } });
const hook = (body, secret = SECRET) => call(hookPath, { method: "POST", body, headers: { "X-Razorpay-Signature": createHmac("sha256", secret).update(body).digest("hex") } });
const events = (after) => call("/api/events?after=" + after, { headers: H }).then((x) => x.json());

let ev = await events(-1); ok(ev.latest === 0 && ev.events.length === 0, "app starts at the newest tip (no replay of old ones)");
r = await call(hookPath, { method: "POST", body: payEvent("pay_1", {}), headers: { "X-Razorpay-Signature": "00" } }); ok(r.status === 400, "forged webhook rejected");
r = await hook(payEvent("pay_1", { name: "Rahul", message: "Great stream bhai!" })); ok(r.status === 200, "valid webhook accepted");
r = await hook(payEvent("pay_1", { name: "Rahul", message: "Great stream bhai!" })); ok(r.status === 200, "duplicate delivery accepted");
r = await hook(payEvent("pay_2", [], 50000)); ok(r.status === 200, "payment with empty notes (array) accepted");
r = await hook(payEvent("pay_3", { "Your Name": "Sam", "Your Message": "Hello from USA", email: "x@y.z" }, 500, "USD")); ok(r.status === 200, "international payment accepted");
r = await hook(payEvent("pay_4", {}, 100, "INR", "payment.failed")); res = await r.json(); ok(res.ignored === "payment.failed", "other events ignored");
ev = await events(0);
ok(ev.events.length === 3, "duplicates and ignored events are not queued (3 tips)");
ok(ev.events[0].name === "Rahul" && ev.events[0].message === "Great stream bhai!" && ev.events[0].display === "₹100", "tip 1: name, message and amount ₹100");
ok(ev.events[1].name === "Someone" && ev.events[1].display === "₹500", "tip 2: no name -> Someone, amount ₹500");
ok(ev.events[2].name === "Sam" && ev.events[2].message === "Hello from USA" && ev.events[2].display === "$5", "tip 3: fields found by label, $5");
const next = await events(ev.events[1].seq); ok(next.events.length === 1 && next.events[0].id === "pay_3", "cursor returns only newer tips");
r = await hook(payEvent("pay_5", { message: "wrong secret" }), "other_secret"); ok(r.status === 400, "signature made with a different secret rejected");
env.DB = undefined;
r = await call("/api/events?after=0", { headers: H }); ok(r.status === 500 && (await r.json()).error.includes("not set up"), "missing database -> clear message");


// 9. invite roles: normal discord.gg invites decide who gets which role (no login page needed)
const minutesAgo = (n) => new Date(Date.now() - n * 60000).toISOString();
const member = (id, joined = 1, bot = false) => ({ user: { id, bot }, joined_at: minutesAgo(joined) });
const runCron = async () => { let p; await worker.scheduled({}, env, { waitUntil: (x) => (p = x) }); await p; };
r = await call("/api/config", { method: "PUT", headers: H, body: JSON.stringify({ inviteRules: [{ code: "https://discord.gg/YTinvite1", role: "100001", label: "YouTube" }, { code: "TWinvite2", role: "100002", label: "Twitch" }] }) });
cfgRes = await r.json();
ok(cfgRes.ok && cfgRes.config.inviteRules.length === 2 && cfgRes.config.inviteRules[0].code === "YTinvite1", "invite roles saved; a full discord.gg link is reduced to its code");
r = await call("/api/config", { method: "PUT", headers: H, body: JSON.stringify({ inviteRules: [{ code: "https://evil.example/abc", role: "100001" }] }) }); ok(r.status === 400, "invite rule with a non-Discord link rejected");
r = await call("/api/config", { headers: H }); ok((await r.json()).config.hasRazorpaySecret, "payment settings still intact after saving invite roles");

invitesNow = [{ code: "YTinvite1", uses: 5 }, { code: "TWinvite2", uses: 2 }, { code: "other", uses: 9 }];
r = await call("/api/invites/check", { method: "POST", headers: H, body: "{}" }); res = await r.json();
ok(!res.error && res.rules[0].found && res.rules[0].uses === 5 && res.notes[0].includes("Now watching"), "first check: invites found and use counts shown, nothing granted");
puts.length = 0; putsFull.length = 0; memberCalls = 0;
await runCron(); ok(memberCalls === 0 && putsFull.length === 0, "no joins: members are not even looked up");

invitesNow = [{ code: "YTinvite1", uses: 6 }, { code: "TWinvite2", uses: 2 }, { code: "other", uses: 9 }];
membersNow = [member("U100", 600), member("U200", 1), member("BOT1", 1, true)];
await runCron();
ok(putsFull.join() === "U200:100001", "one join through the YouTube invite -> that member gets the YouTube role (old members and bots ignored)");
putsFull.length = 0; await runCron(); ok(putsFull.length === 0, "same join is not processed twice");

invitesNow = [{ code: "YTinvite1", uses: 7 }, { code: "TWinvite2", uses: 3 }, { code: "other", uses: 9 }];
membersNow = [member("U200", 3), member("U300", 1), member("U400", 1)];
await runCron(); ok(putsFull.length === 0, "two different invites used at once -> no guessing, no roles");
r = await call("/api/invites/check", { method: "POST", headers: H, body: "{}" }); res = await r.json();
ok(res.assigned.length === 0 && !res.error, "check endpoint still works afterwards");

invitesNow = [{ code: "YTinvite1", uses: 7 }, { code: "TWinvite2", uses: 4 }, { code: "other", uses: 9 }];
membersNow = [member("U500", 1)];
await runCron(); ok(putsFull.join() === "U500:100002", "a join through the Twitch invite gets the Twitch role");

putsFull.length = 0; invitesNow = [{ code: "YTinvite1", uses: 8 }, { code: "TWinvite2", uses: 4 }, { code: "other", uses: 9 }];
membersNow = [member("U600", 1)]; membersStatus = 403;
r = await call("/api/invites/check", { method: "POST", headers: H, body: "{}" }); res = await r.json();
ok(res.error && res.error.includes("Server Members Intent"), "members intent off -> clear instruction");
membersStatus = 200; invitesStatus = 403;
r = await call("/api/invites/check", { method: "POST", headers: H, body: "{}" }); res = await r.json();
ok(res.error && res.error.includes("Manage Server"), "bot without Manage Server -> clear instruction");
invitesStatus = 200;
r = await call("/api/config", { method: "PUT", headers: H, body: JSON.stringify({ inviteRules: [] }) });
puts.length = 0; await runCron(); ok(puts.length === 0, "with no invite roles the scheduled check does nothing");

console.log(fails ? `\n${fails} FAILED` : "\nALL PASSED");
process.exit(fails ? 1 : 0);
