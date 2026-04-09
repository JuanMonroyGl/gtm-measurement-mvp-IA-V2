"""Selector generation stubs."""

from __future__ import annotations

from typing import Any


def propose_selectors(measurement_case: dict[str, Any], dom_snapshot: dict[str, Any]) -> dict[str, Any]:
    """Attach candidate selector placeholders to each interaction."""
    _ = dom_snapshot

    for interaction in measurement_case.get("interacciones", []):
        interaction.setdefault("selector_candidato", None)
        interaction.setdefault("selector_activador", None)
        interaction.setdefault("match_count", None)
        interaction.setdefault("confidence", None)
        interaction.setdefault("warnings", [])

    return {
        "status": "stub",
        "measurement_case": measurement_case,
        "warnings": ["Generación de selectores en modo stub."],
    }
