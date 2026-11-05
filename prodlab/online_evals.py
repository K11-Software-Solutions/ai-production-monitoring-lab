"""Reference-free online evaluators, run on a sample of live traffic.

In production there is no expected answer. Online evals therefore check
properties that can be judged from the trace alone: is the answer supported
by the retrieved context, did it refuse, is it in the user's language?
"""
from __future__ import annotations

import random
import re

from prodlab.simulate import detect_language
from prodlab.system import REFUSAL

_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset("a an and are as at be by can do for from has have how i if in is it its of on or "
                  "so that the this to was we what when with you your will all any".split())
# Conversational filler is not a factual claim, so it is not checked for support.
_FILLER = [re.compile(p, re.IGNORECASE) for p in [r"hope this helps", r"let me know if", r"anything else"]]


def content_words(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


def is_refusal(answer: str) -> bool:
    return answer.strip().startswith(REFUSAL[:12])


def grounded(answer: str, context: str, threshold: float = 0.7) -> bool:
    """Every factual sentence must share most of its content words with the context."""
    if is_refusal(answer):
        return True
    ctx = content_words(context)
    for sentence in re.split(r"(?<=[.!?])\s+", answer.strip()):
        if not sentence or any(p.search(sentence) for p in _FILLER):
            continue
        words = content_words(sentence)
        if words and len(words & ctx) / len(words) < threshold:
            return False
    return True


def language_mismatch(query: str, answer: str) -> bool:
    return detect_language(query) != detect_language(answer)


def sample(traces: list, rate: float, seed: int = 0, include_risky: bool = True) -> list:
    """Random sample plus every risky trace (thumbs-down, flagged, no retrieval).

    Risk-based sampling spends a limited evaluation budget where problems are
    most likely, while the random part keeps an unbiased view of the whole.
    """
    rng = random.Random(seed)
    out = []
    for t in traces:
        risky = include_risky and (t.feedback == "down" or t.injection_flag or t.topic is None)
        if risky or rng.random() < rate:
            out.append(t)
    return out
