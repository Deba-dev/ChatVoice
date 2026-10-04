import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { createService, matchRules } from "./server.mjs";

test("blocked word and link rules match; moderators are exempt", () => {
  const config = { blockedWords: ["badword"], deleteLinks: true, deleteSpam: false };
  const recent = new Map();
  const item = (text, extra = {}) => ({ snippet: { displayMessage: text }, authorDetails: { channelId: "UCuser", ...extra } });
  assert.equal(matchRules(item("this is BADWORD"), config, recent), "blocked word");
  assert.equal(matchRules(item("visit https://example.com"), config, recent), "link");
  assert.equal(matchRules(item("normal chat", { isChatModerator: true }), config, recent), null);
  assert.equal(matchRules(item("normal chat", { isChatOwner: true }), config, recent), null);
});

test("duplicate messages from one viewer are classified as spam", () => {
  const recent = new Map();
  const item = { snippet: { displayMessage: "hello chat" }, authorDetails: { channelId: "UCuser" } };
  const config = { blockedWords: [], deleteLinks: false, deleteSpam: true };
  assert.equal(matchRules(item, config, recent), null);
  assert.equal(matchRules(item, config, recent), "spam");
});

test("health is public and admin API rejects missing bearer token", async () => {
  const dataDir = await mkdtemp(path.join(os.tmpdir(), "chatvoice-youtube-"));
  const service = createService({
    dataDir,
    env: {
      BOT_ADMIN_KEY: "x".repeat(48),
      PUBLIC_URL: "https://bot.example",
      GOOGLE_CLIENT_ID: "client-id",
      GOOGLE_CLIENT_SECRET: "client-secret",
      PORT: "0",
    },
  });
  try {
    await service.start();
    const address = service.server.address();
    const base = `http://127.0.0.1:${address.port}`;
    const health = await fetch(`${base}/health`);
    assert.equal(health.status, 200);
    assert.deepEqual(await health.json(), { ok: true, authorized: false, streams: 0 });
    const unauthorized = await fetch(`${base}/api/streams`);
    assert.equal(unauthorized.status, 401);
    const config = {
      channelId: `UC${"a".repeat(22)}`,
      videoId: "abcdefghijk",
      blockedWords: ["badword"],
      deleteLinks: true,
      dryRun: true,
    };
    const saved = await fetch(`${base}/api/streams`, {
      method: "POST",
      headers: { authorization: `Bearer ${"x".repeat(48)}`, "content-type": "application/json" },
      body: JSON.stringify(config),
    });
    assert.equal(saved.status, 201);
    const listed = await fetch(`${base}/api/streams`, { headers: { authorization: `Bearer ${"x".repeat(48)}` } });
    const result = await listed.json();
    assert.equal(result.streams.length, 1);
    assert.equal(result.streams[0].dryRun, true);
  } finally {
    await service.close();
    await rm(dataDir, { recursive: true, force: true });
  }
});
