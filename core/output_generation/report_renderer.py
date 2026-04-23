"""Render report.md content for a processed case."""

from __future__ import annotations

from typing import Any

from core.processing.validation.schema_validation import SchemaValidationResult


def _incomplete_fields(interaction: dict[str, Any]) -> list[str]:
    required = [
        "tipo_evento",
        "activo",
        "seccion",
        "flujo",
        "elemento",
        "interaction_mode",
        "ubicacion",
        "plan_url",
        "target_url",
        "page_path_regex",
        "texto_referencia",
        "selector_candidato",
        "selector_activador",
        "match_count",
        "confidence",
    ]
    return [field for field in required if interaction.get(field) is None]


def render_report(
    case_id: str,
    parsed_plan: dict[str, Any],
    measurement_case: dict[str, Any],
    fetch_warning: str | None,
    dom_warning: str | None,
    selector_build_result: dict[str, Any],
    selector_validation: dict[str, Any],
    schema_validation: SchemaValidationResult,
    case_metrics: dict[str, Any],
    gate_result: dict[str, Any],
) -> str:
    selector_evidence = selector_build_result.get("selector_evidence") or []
    selector_summary = selector_build_result.get("selector_summary") or {}
    state_metadata = selector_build_result.get("state_metadata") or []

    lines = [
        f"# Reporte {case_id}",
        "",
        "## Estado",
        f"- OCR disponible: {(parsed_plan.get('ocr_status') or {}).get('ocr_available')}",
        f"- render_engine: {selector_build_result.get('render_engine')}",
        f"- gate_passed: {gate_result.get('passed')}",
        f"- promoted_selectors: {selector_summary.get('promoted_selectors')}",
        f"- human_review_required: {selector_summary.get('human_review_required')}",
        "",
        "## Evidencia por imagen",
    ]

    for evidence in parsed_plan.get("evidence", []):
        lines.append(f"- image: {evidence.get('image_path')}")
        lines.append(f"  - method: {evidence.get('extraction_method')}")
        lines.append(f"  - confidence: {evidence.get('confidence')}")

        plan_urls = evidence.get("plan_url_candidates") or []
        if plan_urls:
            lines.append(f"  - plan_url_candidates: {', '.join(plan_urls)}")

        extracted_lines = evidence.get("extracted_lines") or []
        sample = extracted_lines[:3]
        if sample:
            lines.append(f"  - sample_text: {' | '.join(sample)}")
        else:
            lines.append("  - sample_text: <sin texto>")

    lines.extend(
        [
            "",
            "## DOM y estados",
            f"- clickable_inventory_items: {len((selector_build_result.get('clickable_inventory') or []))}",
            f"- states_captured: {', '.join(selector_build_result.get('states_captured') or []) or '<none>'}",
        ]
    )
    for state in state_metadata:
        lines.append(f"- state: {state.get('state')}")
        lines.append(f"  - source: {state.get('source')}")
        lines.append(f"  - attempted: {state.get('attempted')}")
        lines.append(f"  - verified: {state.get('verified')}")
        if state.get("selector"):
            lines.append(f"  - selector: {state.get('selector')}")
        if state.get("target_text"):
            lines.append(f"  - target_text: {state.get('target_text')}")
        if state.get("candidate_count") is not None:
            lines.append(f"  - candidate_count: {state.get('candidate_count')}")
        change_signal = state.get("change_signal") or {}
        lines.append(
            f"  - change_signal: dom_changed={change_signal.get('dom_changed')} signature_changed={change_signal.get('signature_changed')}"
        )
        if state.get("warning"):
            lines.append(f"  - warning: {state.get('warning')}")

    lines.extend(
        [
            "",
            "## Interacciones detectadas",
            f"- total: {len(measurement_case.get('interacciones', []))}",
        ]
    )

    for idx, interaction in enumerate(measurement_case.get("interacciones", []), start=1):
        lines.append(f"- [{idx}] tipo_evento: {interaction.get('tipo_evento')}")
        lines.append(f"  - interaction_mode: {interaction.get('interaction_mode')}")
        lines.append(f"  - flujo: {interaction.get('flujo')}")
        lines.append(f"  - elemento: {interaction.get('elemento')}")
        lines.append(f"  - element_variants: {interaction.get('element_variants')}")
        lines.append(f"  - title_variants: {interaction.get('title_variants')}")
        lines.append(f"  - group_context: {interaction.get('group_context')}")
        lines.append(f"  - zone_hint: {interaction.get('zone_hint')}")
        lines.append(f"  - value_extraction_strategy: {interaction.get('value_extraction_strategy')}")
        lines.append(f"  - ubicacion: {interaction.get('ubicacion')}")
        lines.append(f"  - texto_referencia: {interaction.get('texto_referencia')}")
        lines.append(f"  - selector_candidato: {interaction.get('selector_candidato')}")
        lines.append(f"  - selector_contenedor: {interaction.get('selector_contenedor')}")
        lines.append(f"  - selector_item: {interaction.get('selector_item')}")
        lines.append(f"  - selector_activador: {interaction.get('selector_activador')}")
        lines.append(f"  - match_count: {interaction.get('match_count')}")
        lines.append(f"  - confidence: {interaction.get('confidence')}")

        evidence = next((item for item in selector_evidence if item.get("index") == idx), None)
        if evidence:
            lines.append(f"  - promoted: {evidence.get('promoted')}")
            lines.append(f"  - selector_origin: {evidence.get('selector_origin')}")
            lines.append(f"  - human_review_required: {evidence.get('human_review_required')}")
            if evidence.get("rejection_reason"):
                lines.append(f"  - rejection_reason: {evidence.get('rejection_reason')}")
            chosen = evidence.get("chosen") or {}
            if chosen:
                lines.append(f"  - chosen_selector: {chosen.get('selector')}")
                lines.append(f"  - chosen_selector_origin: {chosen.get('selector_origin')}")
                lines.append(f"  - selector_type: {chosen.get('selector_type')}")
                lines.append(f"  - dom_state: {chosen.get('state')}")
                if chosen.get("selector_contenedor"):
                    lines.append(f"  - chosen_selector_contenedor: {chosen.get('selector_contenedor')}")
                if chosen.get("selector_item"):
                    lines.append(f"  - chosen_selector_item: {chosen.get('selector_item')}")
                lines.append(f"  - exists_in_dom: {chosen.get('exists_in_dom')}")
                lines.append(f"  - matches_candidate_node: {chosen.get('matches_candidate_node')}")
                lines.append(f"  - closest_runtime_supported: {chosen.get('closest_runtime_supported')}")
                lines.append(f"  - click_grounded: {chosen.get('click_grounded')}")
                lines.append(f"  - alignment_score: {chosen.get('alignment_score')}")
                lines.append(f"  - specificity_score: {chosen.get('specificity_score')}")
                if chosen.get("variant_coverage") is not None:
                    lines.append(f"  - variant_coverage: {chosen.get('variant_coverage')}")
                if chosen.get("group_item_count") is not None:
                    lines.append(f"  - group_item_count: {chosen.get('group_item_count')}")
                lines.append(f"  - matched_direct_tokens: {chosen.get('matched_direct_tokens')}")
                lines.append(f"  - matched_context_tokens: {chosen.get('matched_context_tokens')}")
                if chosen.get("matched_variants") is not None:
                    lines.append(f"  - matched_variants: {chosen.get('matched_variants')}")
                lines.append(f"  - promotion_blockers: {chosen.get('promotion_blockers')}")
                lines.append(f"  - outer_html_excerpt: {chosen.get('outer_html_excerpt')}")

        for warning in interaction.get("warnings", []):
            lines.append(f"  - warning: {warning}")

        null_fields = _incomplete_fields(interaction)
        if null_fields:
            lines.append(f"  - null_fields: {', '.join(null_fields)}")

    lines.extend(
        [
            "",
            "## Métricas agregadas del caso",
            f"- total_interactions: {case_metrics.get('total_interactions')}",
            f"- single_interactions: {case_metrics.get('single_interactions')}",
            f"- group_interactions: {case_metrics.get('group_interactions')}",
            f"- interactions_with_selector: {case_metrics.get('interactions_with_selector')}",
            f"- null_selectors: {case_metrics.get('null_selectors')}",
            f"- match_count_0: {case_metrics.get('match_count_0')}",
            f"- match_count_1: {case_metrics.get('match_count_1')}",
            f"- match_count_gt_1: {case_metrics.get('match_count_gt_1')}",
            f"- promoted_from_rendered_dom: {case_metrics.get('promoted_from_rendered_dom')}",
            f"- candidates_from_raw_html_fallback: {case_metrics.get('candidates_from_raw_html_fallback')}",
            f"- rejected_for_safety: {case_metrics.get('rejected_for_safety')}",
            f"- human_review_required: {case_metrics.get('human_review_required')}",
            f"- ambiguity_rate: {case_metrics.get('ambiguity_rate')}",
            "",
            "## Gate final",
            f"- passed: {gate_result.get('passed')}",
        ]
    )
    for error in gate_result.get("errors") or []:
        lines.append(f"- gate_error: {error}")
    for warning in gate_result.get("warnings") or []:
        lines.append(f"- gate_warning: {warning}")

    lines.extend(
        [
            "",
            "## Validación de schema",
            f"- schema_path: {schema_validation.schema_path}",
            f"- valid: {schema_validation.valid}",
        ]
    )
    if schema_validation.errors:
        for error in schema_validation.errors:
            lines.append(f"- schema_error: {error}")

    lines.extend(
        [
            "",
            "## Scraping/DOM",
            f"- fetch_warning: {fetch_warning}",
            f"- dom_warning: {dom_warning}",
            "",
            "## Selectores",
            "- policy: solo observed_rendered_dom puede autopromover selector final",
            f"- build_status: {selector_build_result.get('status')}",
            f"- validation_status: {selector_validation.get('status')}",
            f"- validated_interactions: {selector_validation.get('validated_interactions')}",
            f"- promoted_after_validation: {selector_validation.get('promoted_after_validation')}",
        ]
    )
    for warning in selector_validation.get("warnings") or []:
        lines.append(f"- validation_warning: {warning}")

    parser_warnings = parsed_plan.get("warnings") or []
    if parser_warnings:
        lines.append("")
        lines.append("## Warnings del parser")
        lines.extend([f"- {warning}" for warning in parser_warnings])

    lines.extend(
        [
            "",
            "## Alertas",
            "- Este resultado NO está listo para producción sin revisión humana.",
        ]
    )

    return "\n".join(lines) + "\n"
