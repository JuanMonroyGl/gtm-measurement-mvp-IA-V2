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
) -> str:
    lines = [
        f"# Reporte {case_id}",
        "",
        "## Estado",
        "- Extracción de texto desde imágenes: habilitada cuando OCR está disponible.",
        "- Selección y validación básica de selectores: habilitada.",
        "- Generación GTM final: generada en tag_template.js (una etiqueta por caso).",
        "",
        "## Evidencia por imagen",
    ]
    ocr_status = parsed_plan.get("ocr_status") or {}
    lines.insert(7, f"- OCR disponible: {ocr_status.get('ocr_available')}")

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

    lines.extend([
        "",
        "## DOM usado para validación",
        f"- render_engine: {selector_build_result.get('render_engine')}",
        "",
        "## Interacciones detectadas",
        f"- total: {len(measurement_case.get('interacciones', []))}",
    ])

    selector_evidence = selector_build_result.get("selector_evidence") or []

    for idx, interaction in enumerate(measurement_case.get("interacciones", []), start=1):
        lines.append(f"- [{idx}] tipo_evento: {interaction.get('tipo_evento')}")
        lines.append(f"  - flujo: {interaction.get('flujo')}")
        lines.append(f"  - elemento: {interaction.get('elemento')}")
        lines.append(f"  - ubicacion: {interaction.get('ubicacion')}")
        lines.append(f"  - texto_referencia: {interaction.get('texto_referencia')}")
        lines.append(f"  - selector_candidato: {interaction.get('selector_candidato')}")
        lines.append(f"  - selector_activador: {interaction.get('selector_activador')}")
        lines.append(f"  - match_count: {interaction.get('match_count')}")
        lines.append(f"  - confidence: {interaction.get('confidence')}")

        evidence = next((e for e in selector_evidence if e.get("index") == idx), None)
        if evidence and evidence.get("evidence"):
            lines.append(f"  - evidencia_selector: {evidence.get('evidence')}")
        if evidence and evidence.get("selection_trace"):
            trace = evidence.get("selection_trace") or {}
            lines.append("  - trace_selector:")
            lines.append(f"    - kind: {trace.get('kind')}")
            lines.append(f"    - candidates_considered: {trace.get('candidates_considered')}")
            lines.append(f"    - selected_reason: {trace.get('selected_reason')}")
            top_candidates = trace.get("top_candidates") or []
            for rank, candidate in enumerate(top_candidates, start=1):
                stability = candidate.get("stability") or {}
                lines.append(
                    "    - "
                    f"candidate_{rank}: selector={candidate.get('selector')}; "
                    f"score={candidate.get('ranking_score')}; "
                    f"token_matches={candidate.get('token_match_count')}; "
                    f"primary_stability={stability.get('primary')}; "
                    f"matched_tokens={candidate.get('matched_tokens')}"
                )

        for warning in interaction.get("warnings", []):
            lines.append(f"  - warning: {warning}")

        null_fields = _incomplete_fields(interaction)
        if null_fields:
            lines.append(f"  - null_fields: {', '.join(null_fields)}")

    lines.extend([
        "",
        "## Diferencias relevantes frente al ejemplo manual",
    ])

    for interaction in measurement_case.get("interacciones", []):
        if interaction.get("flujo") == "billetera de google":
            lines.append("- Se conserva flujo 'billetera de google' según plan detectado.")
            break

    for interaction in measurement_case.get("interacciones", []):
        match_count = interaction.get("match_count")
        if isinstance(match_count, int) and match_count > 1:
            lines.append(
                f"- {interaction.get('tipo_evento')} usa selector de grupo válido con {match_count} matches en la sección esperada."
            )

    lines.extend([
        "",
        "## Métricas agregadas del caso",
        f"- total_interactions: {case_metrics.get('total_interactions')}",
        f"- interactions_with_selector: {case_metrics.get('interactions_with_selector')}",
        f"- match_count_0: {case_metrics.get('match_count_0')}",
        f"- match_count_1: {case_metrics.get('match_count_1')}",
        f"- match_count_gt_1: {case_metrics.get('match_count_gt_1')}",
        f"- ambiguity_rate: {case_metrics.get('ambiguity_rate')}",
        f"- interactions_with_warnings: {case_metrics.get('interactions_with_warnings')}",
        f"- total_warnings: {case_metrics.get('total_warnings')}",
        "",
        "## Validación de schema",
        f"- schema_path: {schema_validation.schema_path}",
        f"- valid: {schema_validation.valid}",
    ])
    if schema_validation.errors:
        lines.append("- errors:")
        for error in schema_validation.errors:
            lines.append(f"  - {error}")

    lines.extend([
        "",
        "## Scraping/DOM",
        f"- fetch_warning: {fetch_warning}",
        f"- dom_warning: {dom_warning}",
        "",
        "## Selectores",
        f"- build_status: {selector_build_result.get('status')}",
        f"- validation_status: {selector_validation.get('status')}",
        f"- validated_interactions: {selector_validation.get('validated_interactions')}",
    ])

    parser_warnings = parsed_plan.get("warnings") or []
    if parser_warnings:
        lines.append("")
        lines.append("## Warnings del parser")
        lines.extend([f"- {w}" for w in parser_warnings])

    lines.extend([
        "",
        "## Alertas",
        "- Este resultado NO está listo para producción sin revisión humana.",
    ])

    return "\n".join(lines) + "\n"
