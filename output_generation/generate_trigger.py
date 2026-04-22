"""Trigger selector generation."""

from __future__ import annotations

from typing import Any


DEFAULT_TRIGGER_SELECTOR = "/* stub trigger selector: pending implementation */"


def build_consolidated_trigger_selector(measurement_case: dict[str, Any]) -> str:
    """Build consolidated trigger selector with `selector` and `selector *`."""
    selectors: list[str] = []
    for interaction in measurement_case.get("interacciones", []):
        selector_candidato = interaction.get("selector_candidato")
        selector_activador = interaction.get("selector_activador")
        if selector_candidato:
            base = str(selector_candidato).strip()
            selectors.append(base)
            selectors.append(f"{base} *")
            continue
        if not selector_activador:
            continue
        for part in str(selector_activador).split(","):
            cleaned = part.strip()
            if cleaned:
                selectors.append(cleaned)

    unique = []
    seen = set()
    for item in selectors:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)

    return ", ".join(unique) if unique else DEFAULT_TRIGGER_SELECTOR
