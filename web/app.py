"""The web front of the collection: a question in, a stream of verified steps out.

One endpoint does the work. `POST /ask` streams newline-delimited JSON — the same events
`engine.answer` yields — so the browser can show the node calls as they happen rather than
staring at a spinner for twenty seconds. Streaming with `fetch` and NDJSON rather than SSE,
because SSE's EventSource cannot POST.

Environment:
    COLLECTION      path to the vouch collection   (default: the parent directory)
    LLM_BACKEND     claude | openrouter            (see llm.py)
    DAILY_BUDGET    model-answered questions per day, 0 for no limit  (default: 200)
    RATE_PER_MIN    questions per IP per minute    (default: 6)
"""

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
RATE_PER_MIN = int(os.environ.get("RATE_PER_MIN", "6"))
MAX_QUESTION = 500

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
SPENT = {"day": None, "count": 0}


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
    if DAILY_BUDGET <= 0:
        return False
    today = time.strftime("%Y%m%d")
    if SPENT["day"] != today:
        SPENT.update(day=today, count=0)
    if SPENT["count"] >= DAILY_BUDGET:
        return True
    SPENT["count"] += 1
    return False


# ------------------------------------------------------------------------------ the session
#
# The conversation id becomes a ledger filename and is therefore never trusted as sent.

SAFE = re.compile(r"^[a-z0-9-]{1,40}$")


def session_for(raw):
    return f"web-{raw}" if isinstance(raw, str) and SAFE.match(raw) else f"web-{uuid.uuid4().hex}"


# -------------------------------------------------------------------------------- endpoints


@app.post("/ask")
async def ask(request: Request):
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

    async def stream():
        # The client stores this and sends it back, so a follow-up question attests against
        # the same ledger the first one wrote to.
        yield json.dumps({"type": "session", "conversation": session[len("web-") :]}) + "\n"
        try:
            async for event in engine.answer(
                question, COLLECTION, session, CATALOG["value"], ask_model
            ):
                yield json.dumps(event) + "\n"
        except LLMError as failure:
            yield json.dumps({"type": "error", "reason": str(failure)}) + "\n"

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
async def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"))


app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
