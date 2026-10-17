"""
Turning two numbers into one, and one number into something a person can read.
← YOU BUILD THIS IN MILESTONES 4 AND 5

The combining rule and reader-facing label mapping are implemented.

`combine_signals` is where your false-positive decision from Milestone 1
actually gets made. Everything above it — the labels, the appeal path — is
downstream of a number this function produced.

`score_to_label` is where you stop writing for a machine and start writing for
a person. A score of 0.62 means nothing to a writer.

⚠️ Your README's **Signals and Scoring** section has to name the file and
function holding your combining rule. The grader checks your code against what
you claim, so that line should read `scoring.py::combine_signals`.
"""

import math

import config


LABEL_TEXT = {
    "human": (
        "Our signals suggest this was probably written by a person. "
        "This assessment can be wrong."
    ),
    "unsure": (
        "Our signals cannot reliably tell whether this was written by a person or AI. "
        "This is not an accusation of AI use. "
        "You can request a review if you disagree."
    ),
    "ai": (
        "Our signals suggest this text may be AI-generated. "
        "This assessment can be wrong. "
        "You can request a review if you disagree."
    ),
}


def combine_signals(model_score: float, style_score: float) -> float:
    """
    Combine two 0–1 AI-likeness signals with the documented config weights.

    Both inputs point the same way: higher means more likely AI. Your output
    should too.

    Args:
        model_score: from `detector.model_signal` — how predictable the text is.
        style_score: from `stylometry.style_signal` — the shape of the text.

    Returns:
        A float from 0.0 (low AI-likeness) to 1.0 (high AI-likeness).

    ⚠️ **Write the rule down before you code it, and put the numbers in your
    README.** A weighted average is the obvious choice and it is not the only
    one. Things worth thinking about:

      - **What happens when they disagree?** One signal at 0.9 and the other at
        0.1 averages to 0.5 — "unsure". Is that what you want? It might be
        exactly right: two methods disagreeing IS uncertainty. Or you might
        decide one signal is more trustworthy when they split.

      - **Which way do you want to be wrong?** Weighting toward the signal that
        reads more human means fewer false accusations and more AI text
        getting through. There's no weighting that avoids the trade.

      - Milestone 4 asks you to find a case where your two signals split and
        write it down. That case is what this rule exists to handle.

    """
    if not all(math.isfinite(value) and 0.0 <= value <= 1.0
               for value in (model_score, style_score)):
        raise ValueError("Signal scores must be finite numbers within 0–1.")
    weights = (config.WEIGHT_MODEL_SIGNAL, config.WEIGHT_STYLE_SIGNAL)
    if (not all(math.isfinite(weight) and weight >= 0.0 for weight in weights)
            or not math.isclose(sum(weights), 1.0, rel_tol=0.0, abs_tol=1e-9)):
        raise ValueError("Signal weights must be finite, nonnegative, and sum to 1.")
    return round(
        config.WEIGHT_MODEL_SIGNAL * model_score
        + config.WEIGHT_STYLE_SIGNAL * style_score,
        4,
    )


def score_to_label(score: float) -> tuple[str, str]:
    """
    Turn a score into a guess and the text a reader actually sees.
    Scores at the outer cutoffs belong to the human and AI bands respectively.

    Returns:
        (guess, label_text) — where `guess` is a short machine-readable string
        like "ai" / "human" / "unsure", and `label_text` is the full sentence
        shown to a person.

    ⚠️ Write the label text for someone who has never heard the word
    "threshold".

        ✗ "human, 0.81 confidence"
        ✓ "We think this was probably written by a person."

    All three labels have to be **reachable**. If no score can produce one of
    them, your ranges have a gap — and Milestone 5 asks you to submit text that
    produces each one, which is how you'd find out.

    The hardest one to write is "unsure". It has to admit uncertainty without
    sounding like an accusation, because the person reading it may well have
    written every word themselves. Your breakout asks your group what they'd
    think if they got it on their own work. That question is the whole
    milestone.
    """
    if not math.isfinite(score) or not 0.0 <= score <= 1.0:
        raise ValueError("The combined score must be finite and within 0–1.")
    if not 0.0 <= config.HUMAN_THRESHOLD < config.AI_THRESHOLD <= 1.0:
        raise ValueError("Label cutoffs must satisfy 0 <= human < AI <= 1.")
    if score >= config.AI_THRESHOLD:
        return "ai", LABEL_TEXT["ai"]
    if score <= config.HUMAN_THRESHOLD:
        return "human", LABEL_TEXT["human"]
    return "unsure", LABEL_TEXT["unsure"]


def label_ranges() -> list[tuple[str, str]]:
    """
    The score range each label covers. Your README needs these beside the
    label text — given to you so the numbers can't drift apart from config.py.
    """
    return [
        ("high-confidence human", f"0 <= score <= {config.HUMAN_THRESHOLD:g}"),
        ("unsure", f"{config.HUMAN_THRESHOLD:g} < score < {config.AI_THRESHOLD:g}"),
        ("high-confidence AI", f"{config.AI_THRESHOLD:g} <= score <= 1"),
    ]
