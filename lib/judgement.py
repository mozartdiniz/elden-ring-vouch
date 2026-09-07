"""Parameters the data cannot decide, and what the collection says when nobody does.

A judgement parameter is one where the answer moves and no table can settle it: which class
the character started as, whether the weapon is two-handed, what upgrade level to price, what
floors to hold vigor and mind at. Fourteen of the nineteen nodes take at least one.

Until now the schema said `starting_class` was required and said nothing else, so a model
driving the collection had to produce one — and produced a different one each run. Measured
across the 18-question battery at three repeats: **fourteen of fifteen questions where a model
asked drifted between runs, against two of five where none did.** Every run was internally
consistent and every figure attested. Nothing was wrong except that the answer moved, which is
the one thing this collection exists to prevent.

The fix is not to guess better. It is to stop the guessing being the model's to do:

  * the collection **declares** the value it uses when the caller does not name one, so the
    same question reaches the same node with the same arguments every time;
  * the node **reports** it, in `assumed`, so an answer can say "as a Wretch, which you did
    not specify" instead of presenting the collection's choice as the user's;
  * a contract **pins** the report, so the day someone adds a default and forgets to say so,
    the fixtures fail rather than the answers quietly changing.

That third point is the whole difference between this and bug 17, which was this same default
applied silently while the parameter's own guidance said to leave it out. A declared default
that the answer states is honest. A silent one rewrites the question.

The defaults themselves are chosen to distort least, not to be typical — see DEFAULTS.
"""

# `Wretch` is not the popular class; it is the least-distorting one, and that is the whole
# reason it is here. `planner.py` treats a class's stats as a floor — `max(user, class_value)`
# — so whatever class is assumed lifts every stat below its own minimum. Wretch's minimums are
# a flat 10, the lowest *maximum* of any class: the worst it can do to a stat is raise it to
# 10. Every other class carries at least one 14, 15 or 16, so assuming Astrologer would lift a
# 5-intelligence build to 16 and rewrite the answer entirely.
#
#   class        stat sum   highest floor
#   Wretch             80              10
#   Bandit             84              14
#   Astrologer         85              16
#   ...
#   Confessor          89              14
#
# When the caller names a class, none of this applies: the value they gave is used.
LEAST_DISTORTING_CLASS = "Wretch"

# The ten. A closed set the data has always known and no schema said, which is why a model
# could offer "Vagabond" on one run and "Wretch" on the next as though both were free choices.
STARTING_CLASSES = [
    "Astrologer", "Bandit", "Confessor", "Hero", "Prisoner",
    "Prophet", "Samurai", "Vagabond", "Warrior", "Wretch",
]

# What the collection uses when the caller says nothing. Each is a decision with a reason:
#
#   starting_class  the least-distorting floor — see above.
#   two_hand        one-handed. Two-handing multiplies effective strength by 1.5 and moved a
#                   real answer from 342 to 383, so it is a claim about how the weapon is held
#                   and not a neutral default. False asserts the least.
#
# **A parameter belongs here or in CANONICAL below, never both.** The two kinds are answers to
# different questions — *may the collection decide this?* — and the survivability floors are
# the case that proves it matters: `build-allocate`'s own docstring says how much vigor a
# build should hold back is an opinion, and that a node answering it presents opinion as a
# calculation. Putting `vigor` in this dict would quietly overrule that. Keeping the two kinds
# disjoint means the mistake cannot be made by accident.
DEFAULTS = {
    "starting_class": LEAST_DISTORTING_CLASS,
    "two_hand": False,
}


def applied(request, *names):
    """Fill the named judgement parameters, and say which ones the collection chose.

    Returns `(values, assumed)`. `values` has every name in it; `assumed` has only the ones
    the caller left out, and is what belongs in the result. An empty `assumed` means the
    answer is entirely the caller's question — which is the ordinary case and the one where
    there was never any drift to remove.

    A name given as `None` counts as not given: a model that fills a field with a null is
    saying the same thing as a model that omits it, and both must reach the node identically
    or the drift comes straight back.
    """
    values, assumed = {}, {}
    for name in names:
        if name not in DEFAULTS:
            raise KeyError(f"{name} is not a declared judgement parameter")
        given = request.get(name)
        if given is None:
            values[name] = assumed[name] = DEFAULTS[name]
        else:
            values[name] = given
    return values, assumed


def guidance(name, what):
    """The parameter's guidance line, with the declared default stated in it.

    The catalog is what a model reads before every decision, so this is where the default has
    to appear if it is going to stop being invented. `web/engine.trimmed` folds this into the
    JSON Schema description that ships on every planning prompt.
    """
    shown = DEFAULTS[name]
    return f"{what} Optional — the collection uses {shown!r} and reports it in `assumed`."


# ---------------------------------------------------------------- the other kind

# Some judgements must *not* be defaulted, and `build-allocate` says why in its own docstring:
# how much vigor a build "should" hold back is an opinion, and a node that answers it is
# presenting opinion as a calculation. Those parameters stay required.
#
# Required, though, is what makes a model invent them — it offered "40 vigor / 20 mind /
# 25 endurance" on one run and the same plus a focus on the next, and the answer moved. The
# drift is not caused by the parameter being the caller's. It is caused by the collection
# having no opinion about what the *choices* are.
#
# So for these, the collection publishes the option set instead of the value. The model
# relays a fixed list, the user picks, and the same pick reaches the node every time. The
# judgement stays where it belongs and stops being re-invented on the way there.
#
# These three sets are what every model offered unprompted, under a dozen different labels.
CANONICAL = {
    ("vigor", "mind", "endurance"): [
        ("balanced PvE", {"vigor": 40, "mind": 20, "endurance": 25}),
        ("survivability first", {"vigor": 60, "mind": 20, "endurance": 20}),
        ("caster", {"vigor": 40, "mind": 40, "endurance": 15}),
        ("minimum floors, spend the rest on damage",
         {"vigor": 30, "mind": 15, "endurance": 15}),
    ],
    ("target_level",): [
        ("RL150 — the standard co-op and invasion cap", {"target_level": 150}),
        ("RL125 — the older duelling cap", {"target_level": 125}),
        ("RL80 — mid-game co-op", {"target_level": 80}),
    ],
}


def options(*names):
    """The canonical choices for a set of parameters, as one line for a `guidance` string.

    Written for a model to relay rather than to author. The values are what matter — a label
    is a caption and models translate captions — so every option spells its values out.
    """
    for key, sets in CANONICAL.items():
        if tuple(names) == key:
            spelled = "; ".join(
                f"{label} ({', '.join(f'{k} {v}' for k, v in values.items())})"
                for label, values in sets
            )
            return (f"This is the caller's judgement and the node will not make it. If the user "
                    f"has not said, offer exactly these and use the first unless they choose "
                    f"another: {spelled}.")
    raise KeyError(names)
