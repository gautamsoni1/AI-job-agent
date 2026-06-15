"""
Scoring Utilities — generic numeric helpers used across agents and services
for normalizing, clamping, and combining scores.
"""


def clamp(value: float, min_value: float = 0.0, max_value: float = 100.0) -> float:
    """Clamp a numeric value between min and max."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return min_value
    return max(min_value, min(max_value, value))


def weighted_average(scores: dict[str, float], weights: dict[str, float]) -> float:
    """Compute a weighted average of scores using matching weight keys."""
    total_weight = 0.0
    total_score = 0.0
    for key, score in scores.items():
        weight = weights.get(key, 0.0)
        total_score += clamp(score) * weight
        total_weight += weight
    if total_weight == 0:
        return 0.0
    return round(total_score / total_weight, 2)


def percentage(part: float, whole: float) -> float:
    """Safe percentage calculation."""
    if not whole:
        return 0.0
    return round((part / whole) * 100, 2)


def normalize_score(value: float, source_min: float, source_max: float, target_max: float = 100.0) -> float:
    """Rescale a value from one range to [0, target_max]."""
    if source_max == source_min:
        return 0.0
    ratio = (value - source_min) / (source_max - source_min)
    return clamp(ratio * target_max)


def score_trend_delta(scores: list[float]) -> float:
    """Return the difference between the last and first score in a sequence."""
    if len(scores) < 2:
        return 0.0
    return round(scores[-1] - scores[0], 2)


def average(values: list[float]) -> float:
    """Simple average, returns 0.0 for empty input."""
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def cap_list(items: list, max_items: int) -> list:
    """Return at most max_items from a list."""
    return items[:max_items] if items else []


def priority_to_score(priority: str) -> float:
    """Map a HIGH/MEDIUM/LOW/SKIP priority label to a numeric weight."""
    mapping = {"HIGH": 100.0, "MEDIUM": 60.0, "LOW": 30.0, "SKIP": 0.0}
    return mapping.get((priority or "").upper(), 0.0)