// The whole client. It reads the NDJSON stream from /ask and renders one turn per question.
//
// The three exit-code families are the interaction design, so they get three different
// shapes on screen: a refusal is a step the model recovered from, a defect ends the turn
// with no answer at all, and a success is prose with the attestation verdict attached.

const thread = document.getElementById("thread");
const form = document.getElementById("composer");
const box = document.getElementById("question");
const send = document.getElementById("send");
const reset = document.getElementById("reset");

// One conversation, one ledger, and one thread of context. The server decides the id; we
// keep it and send it back, so a follow-up is planned with the earlier turns in front of the
// model and attested against the same calls.
//
// Dropping it is how you change the subject. That is a real reset, not a cosmetic one: the
// next question starts from nothing and is checked against a fresh ledger, which is also a
// stricter check, because a smaller ledger has fewer numbers for a wrong one to collide with.
let conversation = sessionStorage.getItem("conversation") || null;

const EXAMPLES = [
  "What is the attack power of a Blood Uchigatana +10 at 40 dexterity?",
  "Which affinity gives the most damage on a Longsword at 40 strength and 40 dexterity?",
  "Is vigor 40 or 41 the better level?",
  "Does Bloodflame Blade stack with a Blood affinity?",
];

const examples = document.getElementById("examples");
examples.append("Try:");
for (const text of EXAMPLES) {
  const button = document.createElement("button");
  button.textContent = text;
  button.onclick = () => { box.value = text; box.focus(); };
  examples.append(button);
}

reset.onclick = () => {
  conversation = null;
  sessionStorage.removeItem("conversation");
  reset.hidden = true;
  if (thread.children.length) thread.append(el("div", "divider", "new conversation"));
  box.focus();
};

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function scroll() {
  window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
}

// --- one turn ---------------------------------------------------------------

function newTurn(question) {
  const turn = el("div", "turn");
  turn.append(el("p", "asked", question));

  const trace = el("details", "trace");
  trace.open = true;
  const summary = el("summary", null, "working…");
  const steps = el("div", "steps");
  trace.append(summary, steps);
  turn.append(trace);

  thread.append(turn);
  scroll();

  let calls = 0;

  return {
    step(className, label, detail) {
      const line = el("div", "step " + className);
      line.append(el("b", null, label));
      if (detail) line.append(" " + detail);
      steps.append(line);
      scroll();
    },
    countCall() {
      summary.textContent = `${++calls} node call${calls === 1 ? "" : "s"}`;
    },
    finish(node) {
      trace.open = false;
      if (!calls) summary.textContent = "no node calls";
      turn.append(node);
      scroll();
    },
  };
}

function answerBlock(event) {
  const wrap = document.createElement("div");

  if (event.attestation === "failed") {
    const notice = el("div", "notice bad");
    notice.append(el("div", null,
      "I don't know. The results were verified, but the answer written from them contained " +
      "figures the ledger cannot account for, so it is not being shown."));
    for (const line of event.detail || []) notice.append(el("p", null, line));
    wrap.append(notice);
    return wrap;
  }

  wrap.append(el("div", "answer", event.text));
  const badge = el("span", "badge " + event.attestation);
  badge.textContent = event.attestation === "attested"
    ? "attested — every figure traces to a node call"
    : "unchecked — attestation could not run";
  wrap.append(badge);
  return wrap;
}

// What picking an option is taken to have said. Mirrors chosen_text in engine.py, and the
// reason it is not just the label: models caption their options "recommended default" and
// put the actual numbers in `value`, so sending the label back asks the same question again.
// The composer is filled with this, so the chat shows exactly what was sent.
function chosenText(option) {
  const label = String(option.label ?? "").trim();
  const value = option.value;
  if (value === undefined || value === null || value === "") return label || "the first option";

  let spelled;
  if (Array.isArray(value)) spelled = value.join(", ");
  else if (typeof value === "object") spelled = Object.entries(value).map(([k, v]) => `${k} ${v}`).join(", ");
  else spelled = String(value);

  if (!label) return spelled;
  return label.includes(spelled) ? label : `${label} (${spelled})`;
}

function askBlock(event) {
  const wrap = el("div", "notice ask");
  wrap.append(el("div", null, event.question));

  const choices = el("div", "choices");
  for (const option of event.options || []) {
    const button = el("button", null, option.label);
    if (option.note) button.title = option.note;
    // Answering is just the next message, so the conversation carries the question with it
    // and the model sees what was asked alongside what was chosen.
    // Returning it is a no-op in a browser, where requestSubmit gives back undefined; it is
    // what lets test_client.mjs await the follow-up.
    button.onclick = () => {
      box.value = chosenText(option);
      return form.requestSubmit();
    };
    choices.append(button);
  }
  if (choices.children.length) wrap.append(choices);
  return wrap;
}

function render(turn, event) {
  switch (event.type) {
    case "session":
      conversation = event.conversation;
      sessionStorage.setItem("conversation", conversation);
      reset.hidden = false;
      break;

    case "thinking":
      turn.step("thinking", "…", event.what);
      break;

    case "call":
      turn.countCall();
      turn.step("call", event.node, JSON.stringify(event.input));
      break;

    case "result":
      turn.step("result", "→", JSON.stringify(event.result));
      break;

    // A precondition said no. The model is told why, in words written to be acted on, and
    // gets another go — so this is a step in the trace, not the end of the turn.
    case "refusal":
      turn.step("refusal", "refused", `${event.node}: ${event.reason}`);
      break;

    case "answer":
      turn.finish(answerBlock(event));
      break;

    // Not a failure: the collection needs one value that is the user's to decide. Rendered
    // as buttons, which is both a better interaction than free text and free of tokens.
    case "ask":
      turn.finish(askBlock(event));
      break;

    // The model's reply would not parse and it is being asked again. Worth showing — a model
    // that does this every turn is a model to stop paying for.
    case "malformed":
      turn.step("refusal", "unparseable", event.reason);
      break;

    case "no_answer":
      turn.finish(el("div", "notice dim", "I don't know. " + event.reason));
      break;

    // A node broke its own contract. No answer is shown, not even a hedged one — that is
    // the behaviour this whole thing exists to have.
    case "defect":
      turn.finish(el("div", "notice bad",
        `I can't answer that. The \`${event.node}\` node is broken — ${event.reason}. ` +
        "That needs reporting, not retrying."));
      break;

    case "error":
      turn.finish(el("div", "notice bad", "Something broke on the way: " + event.reason));
      break;
  }
}

// --- the stream -------------------------------------------------------------

async function ask(question) {
  const turn = newTurn(question);

  let reply;
  try {
    // Carry whatever key opened this page through to the request, so a shared link works
    // without a login and a bare /ask still does not.
    reply = await fetch("/ask" + window.location.search, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, conversation }),
    });
  } catch (failure) {
    turn.finish(el("div", "notice bad", "Could not reach the server."));
    return;
  }

  if (!reply.ok) {
    const body = await reply.json().catch(() => ({}));
    turn.finish(el("div", "notice dim", body.error || `The server said ${reply.status}.`));
    return;
  }

  // NDJSON: one event per line, and a line can arrive split across two chunks.
  const reader = reply.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    const lines = buffer.split("\n");
    buffer = lines.pop();
    for (const line of lines) {
      if (line.trim()) render(turn, JSON.parse(line));
    }
  }
}

form.onsubmit = async (event) => {
  event.preventDefault();
  const question = box.value.trim();
  if (!question) return;

  box.value = "";
  box.style.height = "auto";
  send.disabled = box.disabled = true;
  try {
    await ask(question);
  } finally {
    send.disabled = box.disabled = false;
    box.focus();
  }
};

box.addEventListener("input", () => {
  box.style.height = "auto";
  box.style.height = box.scrollHeight + "px";
});

box.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});
