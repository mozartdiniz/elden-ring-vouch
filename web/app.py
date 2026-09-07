"""The web front of the collection: a question in, a stream of verified steps out.

One endpoint does the work. `POST /ask` streams newline-delimited JSON — the same events
`engine.answer` yields — so the browser can show the node calls as they happen rather than
staring at a spinner for twenty seconds. Streaming with `fetch` and NDJSON rather than SSE,
because SSE's EventSource cannot POST.

Environment:
    COLLECTION      path to the vouch collection   (default: the parent directory)
    LLM_BACKEND     claude | openrouter            (see llm.py)
    DAILY_BUDGET    model-answered questions per day, 0 for no limit  (default: 200)
    DAILY_SPEND     dollars per day, 0 for no limit (default: 5)
    RATE_PER_MIN    questions per IP per minute    (default: 6)
"""

import hmac
import os
import json
import re
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

import engine
from llm import LLMError, ask_model

HERE = os.path.dirname(os.path.abspath(__file__))
COLLECTION = os.path.abspath(os.environ.get("COLLECTION", os.path.dirname(HERE)))

DAILY_BUDGET = int(os.environ.get("DAILY_BUDGET", "200"))
# The ceiling that is denominated in the thing you actually care about. See over_budget().
DAILY_SPEND = float(os.environ.get("DAILY_SPEND", "5"))
RATE_PER_MIN = int(os.environ.get("RATE_PER_MIN", "6"))
MAX_QUESTION = 500

# How much of a conversation is carried into the next question. Six turns is enough for the
# shape this exists for — ask for a spread, then ask what changes if dexterity replaces
# strength — and it bounds two things that would otherwise grow without limit: the planning
# prompt, and the ledger a follow-up is attested against. See the note in README.md.
KEEP_TURNS = int(os.environ.get("KEEP_TURNS", "6"))
KEEP_CONVERSATIONS = int(os.environ.get("KEEP_CONVERSATIONS", "500"))
CONVERSATION_TTL = float(os.environ.get("CONVERSATION_TTL", "3600"))

# Unset, everything is open — which is right for localhost. Set, every request must carry
# ?k=<token>, which is what makes it safe to listen on anything but 127.0.0.1: this endpoint
# spends model calls on someone else's account and has no other authentication. run.sh will
# not bind a non-local address without it.
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", "")

CATALOG = {}


@asynccontextmanager
async def lifespan(app):
    # Read the catalog once. It is ~4,000 tokens of routing context, identical for every
    # conversation, and a failure here should stop the box rather than every question.
    CATALOG["value"] = await engine.load_catalog(COLLECTION)
    yield


app = FastAPI(title="Elden Ring, computed", lifespan=lifespan)


# ------------------------------------------------------------------- keeping the lights on
#
# Both of these are in-memory and reset on restart, which is enough for one box and not
# enough for anything public. The spend limit that actually matters is the one set on the
# OpenRouter key itself, where application code cannot get it wrong.

SEEN = defaultdict(deque)
SPENT = {"day": None, "count": 0, "cost": 0.0}


class Conversations:
    """What each conversation has already asked, so a follow-up knows what "it" refers to.

    In memory, capped both ways, and gone on restart. The durable half of a conversation is
    its ledger on disk — which is what the answers are checked against — and this is only the
    prompt context needed to route the next question. Losing it costs a user their thread,
    not the correctness of anything.
    """

    def __init__(self):
        self.turns = {}
        self.touched = {}

    def _forget(self, session):
        """Drop a conversation, and the ledger it was attesting against.

        The ledger is only useful while the conversation is alive: it is what a follow-up
        question is checked against. Once the thread is gone nothing will ever read it
        again, and one file per visitor accumulating forever is how a box fills its disk
        at three in the morning for no reason at all.

        Deleting it is safe in a way that deleting a ledger usually is not — this one
        belongs to a conversation the process has just decided is over, and every answer it
        ever backed was attested at the time it was shown.
        """
        self.turns.pop(session, None)
        self.touched.pop(session, None)
        try:
            os.remove(engine.ledger_path(COLLECTION, session))
        except OSError:
            # Never written (no call was made), or already gone. Neither is worth a word.
            pass

    def _evict(self):
        now = time.monotonic()
        for session in [s for s, at in self.touched.items() if now - at > CONVERSATION_TTL]:
            self._forget(session)
        while len(self.turns) > KEEP_CONVERSATIONS:
            self._forget(min(self.touched, key=self.touched.get))

    def history(self, session):
        self._evict()
        self.touched[session] = time.monotonic()
        return list(self.turns.get(session, ()))

    def remember(self, session, turn):
        # A turn that gave no answer is kept too, and is the more useful of the two: when a
        # node refused for want of a weapon, the next message is usually the weapon.
        kept = self.turns.setdefault(session, deque(maxlen=KEEP_TURNS))
        kept.append(turn)
        self.touched[session] = time.monotonic()


CONVERSATIONS = Conversations()


def rate_limited(ip):
    if RATE_PER_MIN <= 0:
        return False
    now = time.monotonic()
    recent = SEEN[ip]
    while recent and now - recent[0] > 60:
        recent.popleft()
    if len(recent) >= RATE_PER_MIN:
        return True
    recent.append(now)
    return False


def over_budget():
    """Two ceilings, because a count of questions is not a ceiling on money.

    The count was the only guard, and it silently changes meaning whenever the model does:
    200 questions is $1.28 on gpt-5.6-luna and $19 on gpt-5.6-terra. The money cap is the
    one that actually bounds the damage, and it is the reason this endpoint can be public
    without an account system — the worst case is a number you chose, not a number an
    attacker chose.

    The cost of a question is only known once it has run, so this checks the running total
    before starting the next one. One question can therefore overshoot, by at most what one
    question costs. Reserving an estimate up front would be tighter and would also refuse
    questions that turn out to be cheap.
    """
    today = time.strftime("%Y%m%d")
    if SPENT["day"] != today:
        SPENT.update(day=today, count=0, cost=0.0)
    if DAILY_SPEND > 0 and SPENT["cost"] >= DAILY_SPEND:
        return True
    if DAILY_BUDGET <= 0:
        return False
    if SPENT["count"] >= DAILY_BUDGET:
        return True
    SPENT["count"] += 1
    return False


def record_spend(usage):
    """What the question actually cost, from the provider's own figure.

    Zero on the `claude` backend, which reports none — so the money cap simply never fires
    there, which is right: that backend spends a session, not an account.
    """
    SPENT["cost"] = SPENT.get("cost", 0.0) + float(usage.get("cost") or 0)


# ------------------------------------------------------------------------------ the session
#
# The conversation id becomes a ledger filename and is therefore never trusted as sent.

SAFE = re.compile(r"^[a-z0-9-]{1,40}$")


def admitted(request):
    # compare_digest rather than ==, so the check does not leak the token one character at a
    # time to anyone willing to measure.
    if not ACCESS_TOKEN:
        return True
    return hmac.compare_digest(request.query_params.get("k", ""), ACCESS_TOKEN)


def session_for(raw):
    return f"web-{raw}" if isinstance(raw, str) and SAFE.match(raw) else f"web-{uuid.uuid4().hex}"


# -------------------------------------------------------------------------------- endpoints


@app.post("/ask")
async def ask(request: Request):
    if not admitted(request):
        return JSONResponse({"error": "not for you"}, status_code=403)

    body = await request.json()
    question = (body.get("question") or "").strip()

    if not question:
        return JSONResponse({"error": "ask something"}, status_code=400)
    if len(question) > MAX_QUESTION:
        return JSONResponse({"error": f"questions are capped at {MAX_QUESTION} characters"}, 400)

    client = request.client.host if request.client else "unknown"
    if rate_limited(client):
        return JSONResponse({"error": "slow down — a few questions a minute"}, status_code=429)
    if over_budget():
        return JSONResponse(
            {"error": "today's budget is spent. It resets tomorrow."}, status_code=429
        )

    session = session_for(body.get("conversation"))

    history = CONVERSATIONS.history(session)

    async def stream():
        # The client stores this and sends it back, so a follow-up question attests against
        # the same ledger the first one wrote to.
        yield json.dumps({"type": "session", "conversation": session[len("web-") :]}) + "\n"

        turn = {"question": question, "calls": [], "answer": None, "asked": "", "outcome_reason": ""}
        # What this one question costs, so the daily ceiling is denominated in money rather
        # than in a count of questions whose price depends on which model is configured.
        spend = {}

        async def asking(prompt):
            return await ask_model(prompt, usage=spend)

        try:
            async for event in engine.answer(
                question, COLLECTION, session, CATALOG["value"], asking, history
            ):
                if event["type"] == "call":
                    turn["calls"].append({"node": event["node"], "input": event["input"]})
                elif event["type"] == "answer" and event["attestation"] != "failed":
                    turn["answer"] = event["text"]
                elif event["type"] == "ask":
                    turn["asked"] = event["question"]
                elif event["type"] in ("no_answer", "defect"):
                    turn["outcome_reason"] = event.get("reason", "")
                yield json.dumps(event) + "\n"
        except LLMError as failure:
            # Recorded before returning: a question that died halfway still spent whatever
            # it spent, and a ceiling that only counts successes is not a ceiling.
            record_spend(spend)
            yield json.dumps({"type": "error", "reason": str(failure)}) + "\n"
            return

        record_spend(spend)

        # An answer that failed attestation is deliberately not remembered as an answer: it
        # was never shown, and carrying it forward would put unverified figures in the next
        # prompt through the back door.
        CONVERSATIONS.remember(session, turn)

    return StreamingResponse(stream(), media_type="application/x-ndjson")


@app.get("/nodes")
async def nodes():
    """What the collection can answer — enough for the UI to say so without a model call."""
    catalog = CATALOG["value"]
    return {
        "collection": catalog["collection"],
        "about": catalog["about"],
        "nodes": [{"node": n["node"], "purpose": n["purpose"]} for n in catalog["nodes"]],
    }


@app.get("/")
async def index(request: Request):
    if not admitted(request):
        return JSONResponse({"error": "not for you"}, status_code=403)
    return FileResponse(os.path.join(HERE, "static", "index.html"))


app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
