"""Validate selector candidates against grounded DOM evidence."""

from __future__ import annotations

from typing import Any

from core.processing.selectors.build_selectors import (
    SELECTOR_ORIGIN_RENDERED,
    SELECTOR_ORIGIN_REJECTED,
)


def validate_selector_candidates(
    measurement_case: dict[str, Any],
    dom_snapshot: dict[str, Any],
    selector_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    state_html = dom_snapshot.get("state_html") or {}
    if not state_html:
        return {
            "status": "no_dom",
            "validated_interactions": 0,
            "warnings": ["No hay DOM disponible para validar selectores."],
        }

    evidence_by_index = {
        int(item.get("index")): item
        for item in (selector_evidence or [])
        if item.get("index")
    }

    validated = 0
    warnings: list[str] = []

    for idx, interaction in enumerate(measurement_case.get("interacciones", []), start=1):
        evidence = evidence_by_index.get(idx, {})
        chosen = evidence.get("chosen") or {}
        interaction.setdefault("warnings", [])

        if evidence.get("selector_origin") != SELECTOR_ORIGIN_RENDERED or not evidence.get("promoted"):
            interaction["selector_candidato"] = None
            interaction["selector_activador"] = None
            interaction["match_count"] = int(chosen.get("match_count") or 0)
            interaction["warnings"].append(
                "Selector rechazado por no cumplir grounding renderizado suficiente; human_review_required=true."
            )
            continue

        validated += 1
        interaction["match_count"] = int(chosen.get("match_count") or 0)

        if not chosen.get("exists_in_dom"):
            interaction["selector_candidato"] = None
            interaction["selector_activador"] = None
            interaction["warnings"].append(
                "Selector no existe en los estados renderizados validados; se deja null."
            )
            continue
        if not chosen.get("matches_candidate_node"):
            interaction["selector_candidato"] = None
            interaction["selector_activador"] = None
            interaction["warnings"].append(
                "Selector existe en DOM pero no selecciona el nodo candidato observado; se deja null."
            )
            continue
        if not chosen.get("closest_runtime_supported"):
            interaction["selector_candidato"] = None
            interaction["selector_activador"] = None
            interaction["warnings"].append(
                "Selector no demuestra soporte real para event.target.closest(selector); se deja null."
            )
            continue
        if not chosen.get("click_grounded"):
            interaction["selector_candidato"] = None
            interaction["selector_activador"] = None
            interaction["warnings"].append(
                "Selector no queda click_grounded después de validar runtime flags; se deja null."
            )
            continue
        if interaction.get("match_count") != 1:
            interaction["selector_candidato"] = None
            interaction["selector_activador"] = None
            interaction["warnings"].append(
                f"Selector renderizado pero ambiguo ({interaction['match_count']} matches); se deja null."
            )
            continue

    promoted_after_validation = sum(
        1 for interaction in measurement_case.get("interacciones", []) if interaction.get("selector_candidato")
    )
    if promoted_after_validation == 0:
        warnings.append("No quedó ningún selector autopromovido tras la validación final.")

    return {
        "status": "ok" if promoted_after_validation > 0 else SELECTOR_ORIGIN_REJECTED,
        "validated_interactions": validated,
        "promoted_after_validation": promoted_after_validation,
        "warnings": warnings,
    }
