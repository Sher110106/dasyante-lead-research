from collections.abc import Mapping, Sequence

from .models import Candidate, Evidence


SIGNAL_WEIGHTS: dict[str, int] = {
    "customer_facing_agent": 18,
    "persistent_memory": 18,
    "reliability": 16,
    "relevant_hiring": 15,
    "multi_model_or_framework": 10,
    "recommendations_or_actions": 8,
    "enterprise_or_regulated": 7,
    "recent_launch_or_scale": 8,
}

_SOURCE_FACTOR = {"T1": 1.0, "T2": 0.8, "T3": 0.25}


def score_signals(evidence: Mapping[str, Sequence[Evidence]]) -> int:
    total = 0.0
    for signal, weight in SIGNAL_WEIGHTS.items():
        candidates = [item for item in evidence.get(signal, ()) if item.status == "yes"]
        if not candidates:
            continue
        strongest = max(
            candidates,
            key=lambda item: item.confidence * _SOURCE_FACTOR.get(item.source_tier, 0.25),
        )
        total += weight * strongest.confidence * _SOURCE_FACTOR.get(strongest.source_tier, 0.25)
    return min(100, max(0, round(total)))


def qualify(
    candidate: Candidate,
    evidence: Mapping[str, Sequence[Evidence]],
    threshold: int = 65,
) -> bool:
    del candidate
    agent_yes = any(item.status == "yes" for item in evidence.get("customer_facing_agent", ()))
    pain_yes = any(
        item.status == "yes"
        for signal in ("persistent_memory", "reliability")
        for item in evidence.get(signal, ())
    )
    return score_signals(evidence) >= threshold and agent_yes and pain_yes
