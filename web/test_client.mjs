// The client, exercised without a browser.
//
// `node test_client.mjs`. This is not a rendering test — nothing here knows what the page
// looks like. It tests the part that is actually fragile: a JSON event split across two
// network chunks, and one branch per event type, including the two that must never show an
// answer. Run it after touching static/app.js.

import { readFileSync } from "node:fs";
import assert from "node:assert";

// --- the smallest DOM that app.js will accept ------------------------------

class Node {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.className = "";
    this.style = {};
    this.open = false;
    this._text = "";
  }
  set textContent(value) { this._text = value; this.children = []; }
  get textContent() { return this._text + this.children.map((c) => c.textContent ?? c).join(""); }
  append(...items) { this.children.push(...items); }
  addEventListener() {}
  requestSubmit() { return this.onsubmit({ preventDefault() {} }); }
  focus() {}
}

const byId = {};
for (const id of ["thread", "composer", "question", "send", "examples", "reset"]) byId[id] = new Node(id);

globalThis.document = {
  getElementById: (id) => byId[id],
  createElement: (tag) => new Node(tag),
};
globalThis.sessionStorage = {
  store: {},
  getItem(k) { return this.store[k] ?? null; },
  setItem(k, v) { this.store[k] = v; },
  removeItem(k) { delete this.store[k]; },
};
globalThis.window = { scrollTo() {}, location: { search: "" } };
globalThis.document.body = { scrollHeight: 0 };

// --- a response whose lines do not line up with its chunks ------------------

function streamed(events, { status = 200, splitAt = 7 } = {}) {
  const body = events.map((e) => JSON.stringify(e) + "\n").join("");
  // Deliberately awkward: fixed-size chunks, so events straddle chunk boundaries.
  const chunks = [];
  for (let i = 0; i < body.length; i += splitAt) chunks.push(body.slice(i, i + splitAt));

  return {
    ok: status === 200,
    status,
    json: async () => JSON.parse(body || "{}"),
    body: {
      pipeThrough: () => ({
        getReader: () => {
          let i = 0;
          return { read: async () => (i < chunks.length ? { value: chunks[i++], done: false } : { done: true }) };
        },
      }),
    },
  };
}

globalThis.TextDecoderStream = class {};

let nextResponse = null;
let lastUrl = null;
globalThis.fetch = async (url) => {
  lastUrl = url;
  if (nextResponse instanceof Error) throw nextResponse;
  return nextResponse;
};

// --- load the client --------------------------------------------------------

const source = readFileSync(new URL("./static/app.js", import.meta.url), "utf8");
await import("data:text/javascript," + encodeURIComponent(source));

const form = byId.composer;
const box = byId.question;

async function turn(events, options) {
  byId.thread.children = [];
  nextResponse = events instanceof Error ? events : streamed(events, options);
  box.value = "what is the attack power?";
  await form.requestSubmit();
  return byId.thread.textContent;
}

// --- what must be true ------------------------------------------------------

const checks = [];
const check = (name, fn) => checks.push([name, fn]);

check("an attested answer is shown, with its badge", async () => {
  const text = await turn([
    { type: "session", conversation: "abc123" },
    { type: "thinking", what: "choosing a node" },
    { type: "call", node: "attack-power", input: { weapon: "Uchigatana" } },
    { type: "result", node: "attack-power", result: { attack: 229 } },
    { type: "answer", attestation: "attested", text: "It comes to 229 physical.", detail: [] },
  ]);
  assert.match(text, /It comes to 229 physical\./);
  assert.match(text, /every figure traces to a node call/);
  assert.equal(sessionStorage.getItem("conversation"), "abc123");
});

check("a failed attestation shows NO answer text", async () => {
  const text = await turn([
    { type: "answer", attestation: "failed", text: null, detail: ["line 1, column 4: 97.73"] },
  ]);
  assert.match(text, /figures the ledger cannot account for/);
  assert.match(text, /97\.73/);
  assert.doesNotMatch(text, /null/);
});

check("an unchecked answer is shown but labelled", async () => {
  const text = await turn([
    { type: "answer", attestation: "unchecked", text: "Probably 229.", detail: ["no ledger"] },
  ]);
  assert.match(text, /Probably 229\./);
  assert.match(text, /attestation could not run/);
});

check("a defect ends the turn with no answer", async () => {
  const text = await turn([
    { type: "call", node: "attack-power", input: {} },
    { type: "defect", node: "attack-power", reason: "postcondition failed", code: 13 },
  ]);
  assert.match(text, /attack-power` node is broken/);
  assert.match(text, /reporting, not retrying/);
});

check("a refusal is a step, and the turn still answers", async () => {
  const text = await turn([
    { type: "refusal", node: "build-allocate", reason: "vigor is required", code: 11 },
    { type: "call", node: "build-allocate", input: { vigor: 40 } },
    { type: "result", node: "build-allocate", result: { level: 125 } },
    { type: "answer", attestation: "attested", text: "Level 125.", detail: [] },
  ]);
  assert.match(text, /vigor is required/);
  assert.match(text, /Level 125\./);
});

check("no_answer is shown as a concession", async () => {
  const text = await turn([{ type: "no_answer", reason: "No node can answer that." }]);
  assert.match(text, /I don't know\. No node can answer that\./);
});

check("a rate limit shows the server's message, not a crash", async () => {
  byId.thread.children = [];
  nextResponse = { ok: false, status: 429, json: async () => ({ error: "slow down" }) };
  box.value = "again";
  await form.requestSubmit();
  assert.match(byId.thread.textContent, /slow down/);
});

check("a conversation id is kept and sent back, until it is reset", async () => {
  sessionStorage.store = {};
  await turn([
    { type: "session", conversation: "keepme" },
    { type: "answer", attestation: "attested", text: "229.", detail: [] },
  ]);
  assert.equal(sessionStorage.getItem("conversation"), "keepme");
  assert.equal(byId.reset.hidden, false, "the reset control should appear");

  byId.reset.onclick();
  assert.equal(sessionStorage.getItem("conversation"), null, "reset must drop the id");
  assert.equal(byId.reset.hidden, true);
  assert.match(byId.thread.textContent, /new conversation/);
});

check("the key that opened the page is carried to /ask", async () => {
  window.location.search = "";
  await turn([{ type: "answer", attestation: "attested", text: "229.", detail: [] }]);
  assert.equal(lastUrl, "/ask");

  window.location.search = "?k=s3cret";
  await turn([{ type: "answer", attestation: "attested", text: "229.", detail: [] }]);
  assert.equal(lastUrl, "/ask?k=s3cret");
  window.location.search = "";
});

check("an unreachable server is reported", async () => {
  const text = await turn(new Error("network down"));
  assert.match(text, /Could not reach the server/);
});

check("a one-byte-at-a-time stream parses the same", async () => {
  const text = await turn(
    [{ type: "answer", attestation: "attested", text: "It comes to 229.", detail: [] }],
    { splitAt: 1 }
  );
  assert.match(text, /It comes to 229\./);
});

let failed = 0;
for (const [name, fn] of checks) {
  try {
    await fn();
    console.log(`  ok    ${name}`);
  } catch (failure) {
    failed++;
    console.log(`  FAIL  ${name}\n        ${failure.message.split("\n")[0]}`);
  }
}
console.log(`\n${checks.length - failed}/${checks.length} passed`);
process.exit(failed ? 1 : 0);
