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

# Two transient failures are worth waiting out rather than reporting as an answer that could
# not be had. Both were measured, not imagined: a 14-question run lost eleven questions to
# OpenRouter's new-account rate limit, and five more to a reasoning model returning empty
# content — neither of which says anything about whether the question was answerable.
ATTEMPTS = int(os.environ.get("LLM_ATTEMPTS", "4"))
BACKOFF = float(os.environ.get("LLM_BACKOFF", "4"))


class LLMError(RuntimeError):
    """The model could not be reached or refused to reply. Never a wrong answer — just no answer."""


async def _claude(prompt, model=None, usage=None):
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


async def _openrouter(prompt, model=None, usage=None):
    import httpx

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise LLMError("OPENROUTER_API_KEY is not set")

    body = {
        "model": model or os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-5"),
        "messages": [{"role": "user", "content": prompt}],
        # Reasoning tokens are drawn from this same budget, and a model that spends it all
        # thinking returns an empty `content` — which is how moonshotai/kimi-k3 failed, with
        # 663 of 707 completion tokens going to reasoning. The replies wanted here are still
        # small; the headroom is for the thinking in front of them.
        "max_tokens": int(os.environ.get("OPENROUTER_MAX_TOKENS", "20000")),
        "temperature": 0,
        # Ask for token counts and the actual charge. Without this the reply carries no cost,
        # and a model comparison with no cost in it is not a comparison.
        "usage": {"include": True},
    }
    headers = {"Authorization": f"Bearer {key}"}
    # Optional attribution headers OpenRouter shows on its dashboard.
    if os.environ.get("APP_URL"):
        headers["HTTP-Referer"] = os.environ["APP_URL"]
    if os.environ.get("APP_NAME"):
        headers["X-Title"] = os.environ["APP_NAME"]

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for attempt in range(ATTEMPTS):
            last = attempt == ATTEMPTS - 1
            try:
                reply = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions", json=body, headers=headers
                )
            except httpx.HTTPError as failure:
                raise LLMError(f"openrouter unreachable: {failure}")

            # 429 is the account's rate limit and 5xx is the provider having a moment. Both
            # pass. Honour Retry-After when it is given, since guessing shorter than the
            # provider asked for is how a rate limit becomes a ban.
            if reply.status_code == 429 or reply.status_code >= 500:
                if last:
                    raise LLMError(f"openrouter returned {reply.status_code}: {reply.text[:300]}")
                pause = BACKOFF * (2**attempt)
                try:
                    pause = max(pause, float(reply.headers.get("retry-after", 0)))
                except ValueError:
                    pass
                await asyncio.sleep(pause)
                continue

            if reply.status_code != 200:
                raise LLMError(f"openrouter returned {reply.status_code}: {reply.text[:300]}")

            try:
                payload = reply.json()
                content = payload["choices"][0]["message"]["content"]
            except (json.JSONDecodeError, KeyError, IndexError):
                raise LLMError(f"openrouter sent no usable reply: {reply.text[:300]}")

            # A reasoning model that spends its whole completion budget thinking returns an
            # empty `content` and a large `completion_tokens`. Retrying costs a call; not
            # retrying costs the question.
            if (content or "").strip() or last:
                break
            await asyncio.sleep(BACKOFF)

    if usage is not None:
        spent = payload.get("usage") or {}
        usage["calls"] = usage.get("calls", 0) + 1
        for field in ("prompt_tokens", "completion_tokens", "cost"):
            usage[field] = usage.get(field, 0) + (spent.get(field) or 0)
        cached = (spent.get("prompt_tokens_details") or {}).get("cached_tokens") or 0
        usage["cached_tokens"] = usage.get("cached_tokens", 0) + cached

    if not (content or "").strip():
        spent = (payload.get("usage") or {}).get("completion_tokens")
        raise LLMError(
            f"{body['model']} returned an empty reply after {ATTEMPTS} attempts"
            + (f" (spent {spent} completion tokens on the last one)" if spent else "")
        )
    return content.strip()


BACKENDS = {"claude": _claude, "openrouter": _openrouter}


async def ask_model(prompt, model=None, usage=None):
    """Ask once. `model` overrides the configured one; `usage` accumulates tokens and cost."""
    if BACKEND not in BACKENDS:
        raise LLMError(f"unknown LLM_BACKEND {BACKEND!r}; expected one of {', '.join(BACKENDS)}")
    return await BACKENDS[BACKEND](prompt, model, usage)
