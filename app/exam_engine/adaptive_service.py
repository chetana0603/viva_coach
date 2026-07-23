"""Adaptive level movement. Same rules as the Streamlit prototype, clamped to the exam ceiling."""


def calculate_next_level(current_level: int, is_correct: bool, max_level: int = 5) -> int:
    if is_correct:
        nxt = current_level + 1
    else:
        nxt = current_level - 1
    return max(0, min(max_level, nxt))


def nearest_available_level(target: int, available_levels):
    """Closest level that actually has questions; ties prefer the easier level."""
    if not available_levels:
        return None
    return sorted(available_levels, key=lambda l: (abs(l - target), l))[0]
