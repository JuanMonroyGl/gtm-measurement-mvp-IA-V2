"""Strict output gate for selector grounding and GTM usefulness."""

from __future__ import annotations

from typing import Any

from core.processing.selectors.build_selectors import SELECTOR_ORIGIN_RENDERED

DEFAULT_TRIGGER_SELECTOR = "/* stub trigger selector: pending implementation */"


def evaluate_selector_grounding(
    measurement_case: dict[str, Any],
    selector_trace: dict[str, Any],
    clickable_inventory: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    observed_rendered_selectors = set()
    for item in clickable_inventory.get("items", []):
        if item.get("source") != SELECTOR_ORIGIN_RENDERED:
            continue
        for selector in item.get("selector_candidates") or []:
            observed_rendered_selectors.add(str(selector))

    evidence_by_index = {
        int(item.get("index")): item
        for item in (selector_trace.get("selector_evidence") or [])
        if item.get("index")
    }

    for idx, interaction in enumerate(measurement_case.get("interacciones", []), start=1):
        selector = interaction.get("selector_candidato")
        evidence = evidence_by_index.get(idx, {})
        chosen = evidence.get("chosen") or {}
        interaction_mode = str(interaction.get("interaction_mode") or "single").lower()

        if selector is None:
            continue
        if evidence.get("selector_origin") != SELECTOR_ORIGIN_RENDERED:
            errors.append(f"interaction[{idx}] selector no proviene de observed_rendered_dom: {selector}")
            continue
        if interaction_mode == "single" and selector not in observed_rendered_selectors:
            errors.append(f"interaction[{idx}] selector no aparece en clickable inventory renderizado: {selector}")
        if not chosen.get("matches_candidate_node"):
            errors.append(f"interaction[{idx}] selector no matchea el nodo candidato observado: {selector}")
        if not chosen.get("closest_runtime_supported"):
            errors.append(f"interaction[{idx}] selector no soporta event.target.closest: {selector}")
        if not chosen.get("click_grounded"):
            errors.append(f"interaction[{idx}] selector no queda click_grounded: {selector}")
        if interaction_mode == "single" and int(interaction.get("match_count") or 0) != 1:
            errors.append(f"interaction[{idx}] selector no es único en validación final: {selector}")
        if interaction_mode == "group" and int(interaction.get("match_count") or 0) < 2:
            errors.append(f"interaction[{idx}] selector grupal no cubre múltiples items: {selector}")
        if interaction_mode == "group" and not interaction.get("selector_item"):
            errors.append(f"interaction[{idx}] falta selector_item para interacción grupal.")

    if not observed_rendered_selectors:
        warnings.append("No hay selectores observados en DOM renderizado dentro del clickable inventory.")

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "observed_rendered_selector_count": len(observed_rendered_selectors),
    }


def evaluate_output_gate(
    *,
    measurement_case: dict[str, Any],
    selector_trace: dict[str, Any],
    clickable_inventory: dict[str, Any],
    tag_template: str,
    trigger_selector: str,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    promoted_selectors = [
        interaction.get("selector_candidato")
        for interaction in measurement_case.get("interacciones", [])
        if interaction.get("selector_candidato")
    ]
    if not promoted_selectors:
        errors.append("No hay selectores autopromovidos útiles: todos quedaron en null.")

    trigger_clean = trigger_selector.strip()
    if not trigger_clean or trigger_clean == DEFAULT_TRIGGER_SELECTOR:
        errors.append("trigger_selector.txt quedó vacío o en stub.")

    tag_clean = tag_template.strip()
    if not tag_clean:
        errors.append("tag_template.js quedó vacío.")
    if (
        "e.closest('" not in tag_clean
        and 'e.closest("' not in tag_clean
        and ".closest(" not in tag_clean
        and "resolveGroupNode(" not in tag_clean
    ):
        errors.append("tag_template.js no contiene reglas útiles basadas en closest(...).")
    if "No interaction rules available for this case." in tag_clean:
        errors.append("tag_template.js quedó sin reglas útiles.")

    grounding = evaluate_selector_grounding(measurement_case, selector_trace, clickable_inventory)
    errors.extend(grounding["errors"])
    warnings.extend(grounding["warnings"])

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "grounding": grounding,
        "promoted_selectors": len(promoted_selectors),
    }
