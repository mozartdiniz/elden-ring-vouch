"""Did the answer address what was asked? Attestation cannot tell you.

Attestation proves every figure came from a node. It says nothing about an answer that quotes
two real numbers and silently drops half the question — which is a failure a reader would
notice immediately and the pipeline would not. Two runs of `gpt-5.6-luna` did exactly that:
one answered about Radagon and never mentioned the Elden Beast, and both attested cleanly.

The check needs no model. Lookup nodes resolve the names in a question — `weapon-lookup`,
`boss-lookup` and `spell-lookup` all return `query` and `resolved` — so when the user named a
thing, the collection resolved it, and the answer never mentions it, something was dropped.

What it deliberately does not do: judge whether the answer is *right*, or whether it covered
every figure. It catches a dropped subject, which is the failure that has actually happened.
"""

import re

LOOKUPS = ("weapon-lookup", "boss-lookup", "spell-lookup")

# Words too common to identify anything. "Blade", "sword" and "great" are in dozens of weapon
# names, so matching on them would call an answer complete when it named a different weapon.
VAGUE = {
    "the", "of", "and", "a", "an", "de", "da", "do", "das", "dos", "el", "la",
    "blade", "sword", "great", "greatsword", "staff", "seal", "knight", "beast",
    "lord", "dragon", "black", "golden", "order", "flame", "fire", "holy", "blood",
}


def tokens(text):
    return [t for t in re.split(r"[^0-9a-z]+", (text or "").lower()) if t]


def distinctive(name):
    """The parts of a name that would identify it if quoted alone.

    "Radagon of the Golden Order" keeps only "radagon"; "Elden Beast" keeps "elden". A name
    made entirely of common words keeps all of them rather than none, so that it still has to
    match something.
    """
    parts = [t for t in tokens(name) if len(t) >= 4]
    sharp = [t for t in parts if t not in VAGUE]
    return sharp or parts


def mentioned(name, text):
    haystack = (text or "").lower()
    if name and name.lower() in haystack:
        return True
    return any(part in haystack for part in distinctive(name))


def subjects(question, results):
    """Entities the collection resolved that the user had actually named, grouped by kind.

    Restricted to what the question mentions on purpose: a model may look a weapon up to
    compare it and reasonably not name it in a two-sentence answer. An entity the *user*
    named is different — dropping that is dropping the question.
    """
    asked = " ".join(tokens(question))
    found = {}
    for node, result in results:
        if node not in LOOKUPS or not isinstance(result, dict):
            continue
        resolved = (result.get("resolved") or "").strip()
        if not resolved or result.get("ambiguous"):
            continue
        # The model builds `query` from the question, so a query the question echoes marks an
        # entity the user asked about rather than one the model went looking for.
        query = result.get("query") or resolved
        if any(part in asked for part in distinctive(query)):
            found.setdefault(node, set()).add(resolved)
    return {node: sorted(names) for node, names in found.items()}


def owed(question, results):
    """The entities an answer has to name, which is not all of them.

    One weapon resolved is the subject of the question and can be left implicit: *"switch to
    Fire against Radagon"* is a complete answer to a question about one weapon and two bosses,
    and demanding it repeat the weapon's name would be pedantry that trains you to ignore the
    check. **Two or more of the same kind is different** — the user asked about both, the
    answer differs per entity, and naming one is answering half.
    """
    return sorted(
        name for names in subjects(question, results).values() if len(names) > 1
        for name in names
    )


def check(question, results, answer):
    """Returns (complete, omitted, owed_names).

    A warning, not a verdict. "Which of these two is better" is answered by naming the winner
    alone, and this cannot tell that apart from dropping one — so it reports what an answer
    left unsaid and lets a person judge.
    """
    expected = owed(question, results)
    omitted = [name for name in expected if not mentioned(name, answer)]
    return (not omitted), omitted, expected
