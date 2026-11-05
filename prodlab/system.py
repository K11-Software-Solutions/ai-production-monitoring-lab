"""The production system being monitored: a small support assistant.

It retrieves one help article by keyword and asks a (simulated) model to
answer from it. Model *versions* differ in verbosity, hallucination rate,
refusal rate and speed, so a silent provider update changes behaviour the way
real model updates do. Every answer carries hidden ground-truth labels
(`truth`) that only the simulator knows; online evaluators never see them,
which is what lets us validate those evaluators (article 04).
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

KNOWLEDGE_BASE = {
    "refund": "Refunds are available within 30 days of the first payment. Request a refund in Settings under Billing.",
    "billing": "The Pro plan costs 8 dollars per month or 80 dollars per year. You can change plans at any time.",
    "password": "Password reset links expire after one hour. After five failed sign-in attempts the account locks for 15 minutes.",
    "sync": "Notes sync automatically when you are online. Edits made offline are kept and merged when you reconnect.",
    "export": "You can export all notes from Settings under Data. Exports are delivered as a ZIP file of Markdown files.",
    "api": "The public API allows 60 requests per minute on Pro. Exceeding the limit returns HTTP status 429.",
}

KEYWORDS = {
    "refund": ["refund", "money back", "reimburse"],
    "billing": ["price", "cost", "plan", "billing", "pay"],
    "password": ["password", "locked", "sign in", "login", "reset"],
    "sync": ["sync", "offline", "devices"],
    "export": ["export", "download", "backup"],
    "api": ["api", "rate limit", "429", "requests per minute"],
}

REFUSAL = "I don't know based on the help articles."

# Unsupported claims a model might invent. Used for hallucinations; the simulator labels them.
FABRICATIONS = [
    "Team workspaces cost 5 dollars per user and include unlimited storage.",
    "Refunds are also available by phone 24 hours a day.",
    "Enterprise customers get a dedicated account manager for free.",
    "The API limit is doubled on weekends.",
    # Subtle fabrications: mostly the right words, one wrong fact. Hard for overlap-based evaluators.
    "Refunds are available within 60 days of the first payment.",
    "Password reset links expire after one day.",
]


@dataclass(frozen=True)
class ModelVersion:
    name: str
    verbosity: float          # multiplier on answer length
    hallucination_rate: float # chance of adding an unsupported sentence to an answerable question
    unknown_hallucination: float  # chance of inventing an answer when retrieval finds nothing
    base_latency_ms: float
    ms_per_output_token: float
    price_in_per_1k: float
    price_out_per_1k: float


MODELS = {
    # The version the team evaluated before launch.
    "model-a-2026-09": ModelVersion("model-a-2026-09", 1.0, 0.02, 0.30, 600, 6, 0.0005, 0.0015),
    # The provider's silent update: chattier and less careful.
    "model-a-2026-11": ModelVersion("model-a-2026-11", 1.7, 0.07, 0.45, 600, 6, 0.0005, 0.0015),
    # Release candidates for shadow testing (article 06).
    "model-b-good": ModelVersion("model-b-good", 0.9, 0.01, 0.15, 500, 5, 0.0004, 0.0012),
    "model-b-bad": ModelVersion("model-b-bad", 1.2, 0.10, 0.70, 550, 6, 0.0003, 0.0010),
}

PROMPTS = {"v1": 350, "v2-bloated": 1900}  # system + context tokens per request


def tokens(text: str) -> int:
    return max(1, round(len(text) / 4))


def retrieve(query: str) -> tuple[str | None, float]:
    """Return (topic, score). Score is the share of a topic's keywords seen, 0 if none."""
    q = query.lower()
    best, best_score = None, 0.0
    for topic, words in KEYWORDS.items():
        hits = sum(1 for w in words if re.search(rf"\b{re.escape(w)}\b", q))
        score = hits / len(words)
        if score > best_score:
            best, best_score = topic, score
    return best, round(best_score, 3)


@dataclass
class Answer:
    text: str
    topic: str | None
    retrieval_score: float
    context: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    cost_usd: float
    truth: dict = field(default_factory=dict)  # hidden labels: hallucinated, refused, answerable


def answer(query: str, model: ModelVersion, prompt_version: str, rng: random.Random,
           latency_multiplier: float = 1.0, extra_latency_ms: float = 0.0) -> Answer:
    topic, score = retrieve(query)
    context = KNOWLEDGE_BASE.get(topic, "") if topic else ""
    hallucinated = False
    if context:
        sentences = context.split(". ")
        n = 1 if model.verbosity < 1.3 else 2
        text = ". ".join(sentences[:n]).rstrip(".") + "."
        if model.verbosity >= 1.3:
            text += " I hope this helps! Let me know if there is anything else I can do for you today."
        if rng.random() < model.hallucination_rate:
            text += " " + rng.choice(FABRICATIONS)
            hallucinated = True
    elif rng.random() < model.unknown_hallucination:
        text = rng.choice(FABRICATIONS)
        hallucinated = True
    else:
        text = REFUSAL
    tokens_in = PROMPTS[prompt_version] + tokens(query) + tokens(context)
    tokens_out = tokens(text)
    latency = (model.base_latency_ms * rng.lognormvariate(0, 0.25)
               + tokens_out * model.ms_per_output_token) * latency_multiplier + extra_latency_ms
    cost = tokens_in / 1000 * model.price_in_per_1k + tokens_out / 1000 * model.price_out_per_1k
    return Answer(text, topic, score, context, tokens_in, tokens_out, round(latency, 1), round(cost, 6),
                  truth={"hallucinated": hallucinated, "refused": text == REFUSAL, "answerable": bool(context)})
