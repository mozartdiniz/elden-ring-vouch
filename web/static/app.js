// The whole client. It reads the NDJSON stream from /ask and renders one turn per question.
//
// The three exit-code families are the interaction design, so they get three different
// shapes on screen: a refusal is a step the model recovered from, a defect ends the turn
// with no answer at all, and a success is prose with the attestation verdict attached.

const thread = document.getElementById("thread");
const form = document.getElementById("composer");
const box = document.getElementById("question");
const send = document.getElementById("send");

// One conversation, one ledger. The server decides the id; we keep it for follow-ups so
// they attest against the same calls.
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

function render(turn, event) {
  switch (event.type) {
    case "session":
      conversation = event.conversation;
      sessionStorage.setItem("conversation", conversation);
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
    reply = await fetch("/ask", {
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
