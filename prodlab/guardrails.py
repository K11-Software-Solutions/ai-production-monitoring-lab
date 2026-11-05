"""Runtime guardrails: PII redaction and prompt-injection flagging.

Guardrails run on every request in production, so their error rates matter in
both directions: a missed card number is a privacy incident, and a false
positive blocks or degrades a real customer. evals/datasets/guardrail_labels.jsonl
measures both.
"""
from __future__ import annotations

import re

EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
# Phone numbers: find candidates broadly, then validate. A single strict regex was
# US-only (it missed "+44 20 7946 0958") and also matched bare 13-digit order numbers.
PHONE_CANDIDATE = re.compile(r"(?<![\w+])\+?\(?\d[\d\s().-]{7,}\d(?!\d)")


def _is_phone(candidate: str) -> bool:
    digits = re.sub(r"\D", "", candidate)
    formatted = candidate.startswith("+") or bool(re.search(r"[\s().-]", candidate))
    return (10 <= len(digits) <= 13 and formatted) or len(digits) == 10


CARD_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")

_INJECTION = [re.compile(p, re.IGNORECASE) for p in [
    r"ignore (all |any )?(the |your )?(previous|prior|above) (instructions|rules)",
    r"\b(reveal|print|show|repeat) (me )?(your |the )?(system )?prompt",
    r"\byou are now\b",
    r"\bdeveloper mode\b",
    r"\bjailbreak\b",
]]


def luhn_valid(digits: str) -> bool:
    """Payment card checksum. Filters out order numbers and dates that look like cards."""
    total, parity = 0, len(digits) % 2
    for i, ch in enumerate(digits):
        d = int(ch)
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def find_pii(text: str) -> list[str]:
    kinds = []
    if EMAIL.search(text):
        kinds.append("email")
    for m in CARD_CANDIDATE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and luhn_valid(digits):
            kinds.append("card")
            break
    if "card" not in kinds and any(_is_phone(m.group()) for m in PHONE_CANDIDATE.finditer(EMAIL.sub("", text))):
        kinds.append("phone")
    return kinds


def redact(text: str) -> str:
    def card(m):
        digits = re.sub(r"\D", "", m.group())
        return "[CARD]" if 13 <= len(digits) <= 19 and luhn_valid(digits) else m.group()
    text = EMAIL.sub("[EMAIL]", text)
    text = CARD_CANDIDATE.sub(card, text)
    return PHONE_CANDIDATE.sub(lambda m: "[PHONE]" if _is_phone(m.group()) else m.group(), text)


def is_injection(text: str) -> bool:
    return any(p.search(text) for p in _INJECTION)
