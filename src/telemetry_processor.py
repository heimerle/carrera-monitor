"""Tiny pure derivation helpers used by `StateManager`.

Kept in their own module so unit assertions stay focused. No side effects,
no I/O, no asyncio.
"""

from __future__ import annotations


def update_best_lap(current_best_ms: int | None, new_lap_ms: int) -> int:
    """Return the smaller of `current_best_ms` and `new_lap_ms` (≥ 0).

    Treats `None` as "no record yet".
    """
    if new_lap_ms < 0:
        raise ValueError("new_lap_ms must be ≥ 0")
    if current_best_ms is None:
        return new_lap_ms
    return min(current_best_ms, new_lap_ms)


def clamp_fuel(level_percent: float) -> float:
    """Clamp fuel percentage to [0.0, 100.0]."""
    if level_percent < 0.0:
        return 0.0
    if level_percent > 100.0:
        return 100.0
    return float(level_percent)


def clamp_unit(value: float) -> float:
    """Clamp a 0..1 input (throttle, brake) to [0.0, 1.0]."""
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


# Inline invariants (the spec waives a separate test file for these helpers).
assert update_best_lap(None, 100) == 100
assert update_best_lap(120, 100) == 100
assert update_best_lap(80, 100) == 80
assert clamp_fuel(150) == 100
assert clamp_fuel(-1) == 0
assert clamp_unit(2.0) == 1.0
assert clamp_unit(-0.5) == 0.0
