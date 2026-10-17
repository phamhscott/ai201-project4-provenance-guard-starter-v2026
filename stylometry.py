"""
Signal two: structural measurements and an initial AI-likeness heuristic.

Signal one measures predictability. This one measures the shape of text,
without understanding a word.

Three raw measures are reported. Sentence uniformity and vocabulary repetition
contribute to the style score; punctuation density is diagnostic only.

    sentence_length_spread   do sentences vary in length, or march in step?
    type_token_ratio         how much of the vocabulary repeats?
    punctuation_density      how much punctuation relative to text length?

Why these might differ between human and AI writing: generated prose tends
toward even, mid-length sentences and a narrower band of vocabulary, because
that's what "most likely next word" produces on average. Human writing is
lumpier — a three-word sentence next to a forty-word one.

⚠️ **The blind spot, which you have to name in Milestone 1.**

This signal cannot read. It has no idea what the text says. Anything that
changes the shape without changing the substance moves it — adding typos,
breaking up sentences, pasting in a quotation. That is a very cheap thing for
someone to do on purpose, and unit 8's attack set will do it to you.

Build each function on its own and call it from a terminal before you wire
anything together:

    python stylometry.py "some text to look at"
"""

import re
import statistics
import unicodedata

import config


def sentences(text: str) -> list[str]:
    """Split into sentences. Rough and good enough — given to you."""
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def words(text: str) -> list[str]:
    """Split into lowercase English word tokens, normalizing curly apostrophes."""
    return re.findall(r"[a-z0-9']+", text.lower().replace("\u2019", "'"))


# ── Raw measurements ────────────────────────────────────────────────────────

def sentence_length_spread(text: str) -> float:
    """Population SD / mean of nonempty sentence word counts; 0 if fewer than two."""
    lengths = [len(words(sentence)) for sentence in sentences(text)]
    lengths = [length for length in lengths if length > 0]
    if len(lengths) < 2:
        return 0.0
    return statistics.pstdev(lengths) / statistics.mean(lengths)


def type_token_ratio(text: str) -> float:
    """
    Unique lowercase words over total words; 0 for no words.

    Returns:
        A float between 0 and 1. Higher means more varied vocabulary.

    Worth knowing before you rely on it: this measure falls as text gets
    longer, because common words repeat. Two texts of different lengths aren't
    directly comparable on it, and if your test inputs vary a lot in length,
    that alone can look like a signal.
    """
    tokens = words(text)
    return len(set(tokens)) / len(tokens) if tokens else 0.0


def punctuation_density(text: str) -> float:
    """Unicode punctuation characters / all characters; diagnostic, not scored."""
    if not text:
        return 0.0
    count = sum(unicodedata.category(character).startswith("P") for character in text)
    return count / len(text)


# ── Combining them ───────────────────────────────────────────────────────────

def style_signal(text: str) -> float:
    """Weighted uniformity and repetition, 0–1 AI-likeness; 0.5 with too few sentences."""
    usable_sentences = [sentence for sentence in sentences(text) if words(sentence)]
    if len(usable_sentences) < 2:
        return 0.5

    # A spread of 1 means sentence-length deviation equals mean length.
    uniformity = 1.0 - min(sentence_length_spread(text), 1.0)
    repetition = 1.0 - type_token_ratio(text)
    score = (
        config.WEIGHT_SENTENCE_UNIFORMITY * uniformity
        + config.WEIGHT_VOCABULARY_REPETITION * repetition
    )
    return round(score, 4)


if __name__ == "__main__":
    import sys

    text = " ".join(sys.argv[1:]) or (
        "The system works well. It handles most cases correctly and provides "
        "good results. Users generally find it easy to use and understand."
    )

    print(f"{len(sentences(text))} sentences, {len(words(text))} words\n")
    print(f"sentence_length_spread   {sentence_length_spread(text)}")
    print(f"type_token_ratio         {type_token_ratio(text)}")
    print(f"punctuation_density      {punctuation_density(text)}")
    print(f"style_signal             {style_signal(text)}   (higher = more likely AI)")
    print("\nStyle uses sentence uniformity and vocabulary repetition; punctuation is diagnostic only.")
