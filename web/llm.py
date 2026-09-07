"""One question to a model, two ways of asking.

The loop does not care which model answers, so the backends share a signature and are
chosen by environment. `claude` is the local one: it uses the CLI session already on the
machine and costs nothing extra to develop against. `openrouter` is the deployed one.

Environment:
    LLM_BACKEND         claude | openrouter          (default: claude)
    LLM_TIMEOUT         seconds per call             (default: 120)
    CLAUDE_BIN          the CLI to shell out to      (default: claude)
    OPENROUTER_API_KEY  required by the openrouter backend
    OPENROUTER_MODEL    the model to drive the loop  (default: openai/gpt-5.6-luna)

Four more govern what a run costs. All have defaults that are the intended shipping
configuration; the last two exist so an arm of a comparison can reproduce the old numbers.

    OPENROUTER_MAX_TOKENS  ceiling for the narration reply    (default: 20000)
    PLANNING_MAX_TOKENS    ceiling for a routing decision     (default: 8000)
    PLANNING_REASONING     low | off | default | <effort>     (default: low)
    CACHE_TTL              e.g. 1h; empty uses the provider's (default: empty)
    CACHE_BREAKPOINTS      how many to place, 0 disables      (default: 4)
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
#
# Four and four was not enough: an 18-question battery at concurrency 2 still lost a question
# to `new-account-rpm`, which caps some models at 20 requests a minute and which one question
# can approach on its own, since a question is eight to fifteen sequential calls.
ATTEMPTS = int(os.environ.get("LLM_ATTEMPTS", "6"))
BACKOFF = float(os.environ.get("LLM_BACKOFF", "10"))


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


def _content(prompt):
    """The user message, with a cache breakpoint wherever the prompt says one is legal.

    `engine.Prompt` marks the points its text is identical to the previous call up to — the
    rules and the catalog, then the calls made so far. Without a mark, a model pays full
    price for the same 18,000 tokens on all six to sixteen decisions of every question.

    **Do not assume a provider caches on its own.** It was measured: with the breakpoints
    turned off, `openai/gpt-5.6-luna` reported 0% cached on a prompt whose first 19k tokens
    were byte-identical across eight decisions. With them on, the same question came back
    77% cached and cost a third as much, with an identical answer. Some providers do match
    the longest prefix automatically — `moonshotai/kimi-k3` was already at 87% before any of
    this — but that is a property of the provider, not a rule.

    Marking costs nothing where it is not needed: a provider that ignores `cache_control`
    reads the same text either way. A plain string is sent as a plain string, so nothing that
    hands this module an ordinary prompt changes shape.
    """
    # Anthropic allows four; two is what the planning prompt actually has. Zero is a true
    # no-op — the request goes out as a plain string, exactly as it did before — so a
    # comparison can run an arm without caching and change nothing else.
    breakpoints = int(os.environ.get("CACHE_BREAKPOINTS", "4"))
    ttl = os.environ.get("CACHE_TTL", "").strip()

    segments = getattr(prompt, "segments", None)
    if not segments or breakpoints < 1 or not any(cache for _, cache in segments):
        return str(prompt)

    blocks = []
    for text, cache in segments:
        # Adjacent uncacheable text is one block; nothing is gained by splitting it.
        if blocks and not cache and "cache_control" not in blocks[-1]:
            blocks[-1]["text"] += text
            continue
        block = {"type": "text", "text": text}
        if cache and breakpoints > 0:
            block["cache_control"] = {"type": "ephemeral"}
            if ttl:
                block["cache_control"]["ttl"] = ttl
            breakpoints -= 1
        blocks.append(block)
    return blocks


async def _openrouter(prompt, model=None, usage=None):
    import httpx

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise LLMError("OPENROUTER_API_KEY is not set")

    planning = getattr(prompt, "kind", None) == "planning"

    body = {
        "model": model or os.environ.get("OPENROUTER_MODEL", "openai/gpt-5.6-luna"),
        "messages": [{"role": "user", "content": _content(prompt)}],
        # Reasoning tokens are drawn from this same budget, and a model that spends it all
        # thinking returns an empty `content` — which is how moonshotai/kimi-k3 failed, with
        # 663 of 707 completion tokens going to reasoning. The replies wanted here are still
        # small; the headroom is for the thinking in front of them.
        "max_tokens": int(
            os.environ.get("PLANNING_MAX_TOKENS", "8000")
            if planning
            else os.environ.get("OPENROUTER_MAX_TOKENS", "20000")
        ),
        "temperature": 0,
        # Ask for token counts and the actual charge. Without this the reply carries no cost,
        # and a model comparison with no cost in it is not a comparison.
        "usage": {"include": True},
    }

    # Completion tokens are the part of the bill no cache touches, and a planning decision
    # spends them on deliberation it does not need: the reply is one JSON object choosing a
    # node, and every choice it can make is checked by the runtime — a bad route comes back
    # as a refusal, not as a wrong number. That is what makes this the safe place to be
    # cheap, and kimi's 663-of-707 split is what makes it worth doing.
    #
    # Set PLANNING_REASONING=default to send nothing and reproduce the earlier measurements.
    effort = os.environ.get("PLANNING_REASONING", "low").strip()
    if planning and effort and effort != "default":
        body["reasoning"] = {"exclude": True} if effort == "off" else {"effort": effort}
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
        details = spent.get("prompt_tokens_details") or {}
        usage["cached_tokens"] = usage.get("cached_tokens", 0) + (details.get("cached_tokens") or 0)
        # What it cost to put the prefix there in the first place. Anthropic bills a cache
        # write above the normal input rate, so a run that writes on every call rather than
        # reading is *worse* than no caching at all — and the cached-token share alone cannot
        # tell those two apart.
        usage["cache_write_tokens"] = usage.get("cache_write_tokens", 0) + (
            details.get("cache_creation_tokens") or details.get("cached_write_tokens") or 0
        )

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
