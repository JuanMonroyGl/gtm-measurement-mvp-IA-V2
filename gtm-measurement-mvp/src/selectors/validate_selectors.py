"""Selector validation stubs against DOM snapshots."""

from __future__ import annotations

from typing import Any


def validate_selector_candidates(measurement_case: dict[str, Any], dom_snapshot: dict[str, Any]) -> dict[str, Any]:
    """Placeholder validator for candidate selectors."""
    _ = dom_snapshot

    return {
        "status": "stub",
        "validated_interactions": len(measurement_case.get("interacciones", [])),
        "warnings": ["Validación de selectores no implementada en esta fase."],
    }
