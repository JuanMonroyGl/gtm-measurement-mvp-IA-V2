"""Trigger selector generation."""

from __future__ import annotations

from typing import Any

from core.processing.selectors.safety import is_unsafe_group_selector


DEFAULT_TRIGGER_SELECTOR = "/* stub trigger selector: pending implementation */"


def build_consolidated_trigger_selector(measurement_case: dict[str, Any]) -> str:
    """Build consolidated trigger selector with `selector` and `selector *`."""
    selectors: list[str] = []
    for interaction in measurement_case.get("interacciones", []):
        interaction_mode = str(interaction.get("interaction_mode") or "single").lower()
        selector_candidato = interaction.get("selector_item") or interaction.get("selector_candidato")
        selector_activador = interaction.get("selector_activador")
        if selector_candidato:
            base = str(selector_candidato).strip()
            if interaction_mode == "group" and (
                is_unsafe_group_selector(base) or is_unsafe_group_selector(interaction.get("selector_contenedor"))
            ):
                continue
            if is_unsafe_group_selector(base):
                continue
            selectors.append(base)
            selectors.append(f"{base} *")
            continue
        if not selector_activador:
            continue
        for part in str(selector_activador).split(","):
            cleaned = part.strip()
            base = cleaned[:-2].strip() if cleaned.endswith(" *") else cleaned
            if cleaned and not is_unsafe_group_selector(base):
                selectors.append(cleaned)

    unique = []
    seen = set()
    for item in selectors:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)

    return ", ".join(unique) if unique else DEFAULT_TRIGGER_SELECTOR
