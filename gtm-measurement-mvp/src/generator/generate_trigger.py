"""Trigger selector generation."""

from __future__ import annotations

from typing import Any


DEFAULT_TRIGGER_SELECTOR = "/* stub trigger selector: pending implementation */"


def build_consolidated_trigger_selector(measurement_case: dict[str, Any]) -> str:
    """Build consolidated trigger selector with `selector` and `selector *`."""
    selectors: list[str] = []
    for interaction in measurement_case.get("interacciones", []):
        selector = interaction.get("selector_candidato")
        if not selector:
            continue
        selectors.append(selector)
        selectors.append(f"{selector} *")

    unique = []
    seen = set()
    for item in selectors:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)

    return ", ".join(unique) if unique else DEFAULT_TRIGGER_SELECTOR
