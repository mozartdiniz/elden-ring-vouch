"""One question to a model, two ways of asking.

The loop does not care which model answers, so the backends share a signature and are
chosen by environment. `claude` is the local one: it uses the CLI session already on the
machine and costs nothing extra to develop against. `openrouter` is the deployed one.

Environment:
    LLM_BACKEND         claude | openrouter          (default: claude)
    LLM_TIMEOUT         seconds per call             (default: 120)
    CLAUDE_BIN          the CLI to shell out to      (default: claude)
    OPENROUTER_API_KEY  required by the openrouter backend
    OPENROUTER_MODEL    e.g. anthropic/claude-sonnet-5
"""

import asyncio
import json
import os

BACKEND = os.environ.get("LLM_BACKEND", "claude")
TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "120"))


class LLMError(RuntimeError):
    """The model could not be reached or refused to reply. Never a wrong answer — just no answer."""


async def _claude(prompt):
    """The Claude CLI, using whatever session is logged in on this machine.

    Good for development and for the 122-question regression run; not for a public box,
    where the session would be one shared account behind every visitor.
    """
    proc = await asyncio.create_subprocess_exec(
        os.environ.get("CLAUDE_BIN", "claude"),
        "-p",
        prompt,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        raise LLMError(f"the model did not reply within {TIMEOUT:.0f}s")
    if proc.returncode != 0:
        # The CLI reports some failures — a usage limit, most usefully — on stdout with an
        # empty stderr, so an error built from stderr alone says nothing at all.
        why = err.decode().strip() or out.decode().strip() or "no reason given"
        raise LLMError(f"claude exited {proc.returncode}: {why[:300]}")
    return out.decode().strip()


async def _openrouter(prompt):
    import httpx

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise LLMError("OPENROUTER_API_KEY is not set")

    body = {
        "model": os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-5"),
        "messages": [{"role": "user", "content": prompt}],
        # The model's job here is routing and narration, not prose. Long replies are a
        # symptom of it trying to answer by itself.
        "max_tokens": int(os.environ.get("OPENROUTER_MAX_TOKENS", "1500")),
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {key}"}
    # Optional attribution headers OpenRouter shows on its dashboard.
    if os.environ.get("APP_URL"):
        headers["HTTP-Referer"] = os.environ["APP_URL"]
    if os.environ.get("APP_NAME"):
        headers["X-Title"] = os.environ["APP_NAME"]

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            reply = await client.post(
                "https://openrouter.ai/api/v1/chat/completions", json=body, headers=headers
            )
        except httpx.HTTPError as failure:
            raise LLMError(f"openrouter unreachable: {failure}")

    if reply.status_code != 200:
        raise LLMError(f"openrouter returned {reply.status_code}: {reply.text[:300]}")

    try:
        payload = reply.json()
        return payload["choices"][0]["message"]["content"].strip()
    except (json.JSONDecodeError, KeyError, IndexError):
        raise LLMError(f"openrouter sent no usable reply: {reply.text[:300]}")


BACKENDS = {"claude": _claude, "openrouter": _openrouter}


async def ask_model(prompt):
    if BACKEND not in BACKENDS:
        raise LLMError(f"unknown LLM_BACKEND {BACKEND!r}; expected one of {', '.join(BACKENDS)}")
    return await BACKENDS[BACKEND](prompt)
