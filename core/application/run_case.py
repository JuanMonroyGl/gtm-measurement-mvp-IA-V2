"""Run full case pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.application.inspect_case import inspect_case_input_structure
from core.application.resolve_case_input import resolve_case_input
from core.ai.config import AIConfig
from core.ai.registry import image_parse_provider
from core.checks.output_gate import evaluate_output_gate
from core.cli.context import CaseContext
from core.cli.errors import UserFacingError
from core.output_generation.generate_gtm_tag import build_tag_template
from core.output_generation.generate_trigger import build_consolidated_trigger_selector
from core.output_generation.report_renderer import render_report
from core.output_generation.run_summary import build_run_summary
from core.plan_reader.normalize_plan import normalize_case
from core.processing.selectors.build_selectors import propose_selectors
from core.processing.selectors.validate_selectors import validate_selector_candidates
from core.processing.validation.case_metrics import compute_case_metrics
from core.processing.validation.schema_validation import validate_measurement_case_schema
from web_scraping.snapshot_dom import build_dom_snapshot


def ensure_output_dir(repo_root: Path, case_id: str) -> Path:
    output_dir = repo_root.resolve() / "outputs" / case_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def run_case(context: CaseContext) -> dict[str, Any]:
    input_check = inspect_case_input_structure(context=context)
    if not input_check.get("is_sufficient"):
        details = [
            *input_check.get("missing", []),
            *input_check.get("metadata_errors", []),
        ]
        if input_check.get("resolve_error"):
            details.append(str(input_check.get("resolve_error")))
        formatted = "\n".join(f"- {item}" for item in details)
        raise UserFacingError(f"Estructura de entrada incompleta para {context.case_id}.\n{formatted}")
    if not input_check.get("ocr_available") and not input_check.get("fallback_available"):
        ocr_diag = input_check.get("ocr_diagnostic") or {}
        reason = ocr_diag.get("import_error") or ocr_diag.get("init_error") or "No diagnostic details."
        hint = ocr_diag.get("hint") or "Instala OCR o agrega image_evidence.json como respaldo."
        raise UserFacingError(
            "No se puede procesar el caso: OCR no disponible y no existe image_evidence.json.\n"
            f"OCR diagnostic: {reason}\n"
            f"Sugerencia: {hint}"
        )

    intake = input_check.get("intake") or {}
    prepared_images_dir = intake.get("prepared_images_dir")
    if not prepared_images_dir:
        raise UserFacingError("No existe prepared_assets/images para continuar el pipeline.")

    native_text_entries = intake.get("native_text_entries") or []
    resolved_case = resolve_case_input(
        context,
        images_dir=Path(prepared_images_dir),
        native_text_entries=native_text_entries,
    )
    metadata = resolved_case["resolved_metadata"]
    output_dir = ensure_output_dir(context.repo_root, context.case_id)
    ai_config = AIConfig.from_env()
    ai_image_parse_result: dict[str, Any] | None = None

    image_paths = sorted(
        path
        for path in Path(prepared_images_dir).iterdir()
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    )
    if image_paths:
        provider = image_parse_provider(ai_config)
        ai_image_parse_result = provider.parse(case_id=context.case_id, image_paths=image_paths)

    parsed_plan = resolved_case["parsed_plan"]
    if ai_image_parse_result:
        parsed_plan["ai_extraction"] = ai_image_parse_result
    measurement_case = normalize_case(metadata=metadata, parsed_plan=parsed_plan)

    if not measurement_case.get("interacciones"):
        ai_parsed = (ai_image_parse_result or {}).get("parsed") or {}
        ai_interactions = ai_parsed.get("interactions") or []
        if ai_interactions:
            measurement_case["interacciones"] = [
                {
                    "tipo_evento": item.get("tipo_evento"),
                    "activo": ai_parsed.get("activo") or metadata.get("activo"),
                    "seccion": ai_parsed.get("seccion") or metadata.get("seccion"),
                    "flujo": item.get("flujo"),
                    "elemento": None,
                    "interaction_mode": item.get("interaction_mode") or "single",
                    "element_variants": None,
                    "title_variants": None,
                    "group_context": item.get("group_context"),
                    "zone_hint": item.get("zone_hint"),
                    "value_extraction_strategy": "click_text",
                    "ubicacion": item.get("ubicacion"),
                    "plan_url": metadata.get("plan_url"),
                    "target_url": metadata.get("target_url"),
                    "page_path_regex": metadata.get("page_path_regex"),
                    "texto_referencia": item.get("texto_referencia"),
                    "selector_candidato": None,
                    "selector_contenedor": None,
                    "selector_item": None,
                    "selector_activador": None,
                    "match_count": None,
                    "confidence": item.get("confidence"),
                    "warnings": [item.get("warning")] if item.get("warning") else [],
                }
                for item in ai_interactions
            ]

    if not measurement_case.get("interacciones"):
        raise UserFacingError(
            f"No se detectaron interacciones para {context.case_id}. "
            "Revisa OCR, image_evidence.json o metadata (interacciones/eventos) antes de generar GTM."
        )

    target_url = measurement_case.get("target_url")
    dom_snapshot = build_dom_snapshot(target_url=target_url or "")

    selector_build_result = propose_selectors(
        measurement_case=measurement_case,
        dom_snapshot=dom_snapshot.__dict__,
    )
    selector_build_result["render_engine"] = dom_snapshot.render_engine
    selector_build_result["states_captured"] = dom_snapshot.states_captured

    selector_validation = validate_selector_candidates(
        measurement_case=measurement_case,
        dom_snapshot=dom_snapshot.__dict__,
        selector_evidence=selector_build_result.get("selector_evidence"),
    )
    case_metrics = compute_case_metrics(measurement_case, selector_build_result.get("selector_evidence"))
    schema_validation = validate_measurement_case_schema(repo_root=context.repo_root, measurement_case=measurement_case)
    if not schema_validation.valid:
        details = "\n".join(f"- {err}" for err in schema_validation.errors)
        raise UserFacingError(
            "measurement_case.json no cumple el schema del proyecto.\n"
            f"Schema: {schema_validation.schema_path}\n"
            f"{details}"
        )

    tag_template = build_tag_template(measurement_case)
    trigger_selector = build_consolidated_trigger_selector(measurement_case)

    clickable_inventory_payload = {
        "states_captured": dom_snapshot.states_captured,
        "render_engine": dom_snapshot.render_engine,
        "state_metadata": dom_snapshot.state_metadata or [],
        "items": dom_snapshot.clickable_inventory or [],
    }
    selector_trace_payload = {
        "render_engine": dom_snapshot.render_engine,
        "selector_summary": selector_build_result.get("selector_summary") or {},
        "selector_evidence": selector_build_result.get("selector_evidence") or [],
    }
    gate_result = evaluate_output_gate(
        measurement_case=measurement_case,
        selector_trace=selector_trace_payload,
        clickable_inventory=clickable_inventory_payload,
        tag_template=tag_template,
        trigger_selector=trigger_selector,
    )

    measurement_case_path = output_dir / "measurement_case.json"
    tag_template_path = output_dir / "tag_template.js"
    trigger_selector_path = output_dir / "trigger_selector.txt"
    report_path = output_dir / "report.md"
    resolved_case_input_path = output_dir / "resolved_case_input.json"
    run_summary_path = output_dir / "run_summary.json"
    clickable_inventory_path = output_dir / "clickable_inventory.json"
    selector_trace_path = output_dir / "selector_trace.json"
    ai_extraction_path = output_dir / "ai_extraction.json"

    with measurement_case_path.open("w", encoding="utf-8") as file_handle:
        json.dump(measurement_case, file_handle, ensure_ascii=False, indent=2)

    tag_template_path.write_text(tag_template, encoding="utf-8")
    clickable_inventory_path.write_text(
        json.dumps(clickable_inventory_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    selector_trace_path.write_text(
        json.dumps(selector_trace_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    trigger_selector_path.write_text(trigger_selector, encoding="utf-8")
    if ai_image_parse_result:
        ai_extraction_path.write_text(
            json.dumps(ai_image_parse_result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    resolved_case_input_path.write_text(
        json.dumps(
            {
                "case_id": context.case_id,
                "metadata_source": resolved_case.get("metadata_source"),
                "messages": resolved_case.get("messages"),
                "warnings": resolved_case.get("warnings"),
                "explicit_metadata": resolved_case.get("explicit_metadata"),
                "inferred_metadata": resolved_case.get("inferred_metadata"),
                "resolved_metadata": resolved_case.get("resolved_metadata"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    report_text = render_report(
        case_id=context.case_id,
        parsed_plan=parsed_plan,
        measurement_case=measurement_case,
        fetch_warning=dom_snapshot.fetch_warning,
        dom_warning=dom_snapshot.warning,
        selector_build_result=selector_build_result,
        selector_validation=selector_validation,
        schema_validation=schema_validation,
        case_metrics=case_metrics,
        gate_result=gate_result,
    )
    report_path.write_text(report_text, encoding="utf-8")

    evidence = parsed_plan.get("evidence") or []
    used_fallback = any(item.get("extraction_method") == "sidecar_text_support" for item in evidence)
    used_ocr = any(item.get("extraction_method") == "rapidocr_text_support" for item in evidence)
    warning_messages = list(input_check.get("warnings", []))
    warning_messages.extend(resolved_case.get("warnings") or [])
    warning_messages.extend(resolved_case.get("messages") or [])
    warning_messages.extend(parsed_plan.get("warnings") or [])
    warning_messages.extend(selector_build_result.get("warnings") or [])
    warning_messages.extend(selector_validation.get("warnings") or [])
    warning_messages.extend(gate_result.get("warnings") or [])
    if dom_snapshot.fetch_warning:
        warning_messages.append(dom_snapshot.fetch_warning)
    if dom_snapshot.warning:
        warning_messages.append(dom_snapshot.warning)
    for interaction in measurement_case.get("interacciones", []):
        warning_messages.extend(interaction.get("warnings") or [])
    warning_messages = sorted(set(warning_messages))

    ambiguity_detected = any(
        isinstance(interaction.get("match_count"), int) and interaction.get("match_count", 0) > 1
        for interaction in measurement_case.get("interacciones", [])
    )
    status = "error" if not gate_result.get("passed") else ("warning" if warning_messages else "success")
    run_summary = build_run_summary(
        context=context,
        inspect_result=input_check,
        status=status,
        warning_messages=warning_messages,
        outputs_generated={
            "asset_manifest": str((Path(prepared_images_dir).parent / "asset_manifest.json")),
            "measurement_case": str(measurement_case_path),
            "clickable_inventory": str(clickable_inventory_path),
            "selector_trace": str(selector_trace_path),
            "ai_extraction": str(ai_extraction_path) if ai_image_parse_result else None,
            "tag_template": str(tag_template_path),
            "trigger_selector": str(trigger_selector_path),
            "report": str(report_path),
            "resolved_case_input": str(resolved_case_input_path),
            "run_summary": str(run_summary_path),
        },
        interactions_detected=len(measurement_case.get("interacciones", [])),
        ambiguity_detected=ambiguity_detected,
        used_ocr=used_ocr,
        used_fallback=used_fallback,
        render_engine=dom_snapshot.render_engine,
        selector_metrics=case_metrics,
        gate_result=gate_result,
    )
    run_summary_path.write_text(json.dumps(run_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    if not gate_result.get("passed"):
        details = "\n".join(f"- {error}" for error in gate_result.get("errors") or [])
        raise UserFacingError(
            "El caso generó artefactos pero falló el gate estricto de grounding/uso GTM.\n"
            f"{details}"
        )

    return {
        "case_id": context.case_id,
        "output_dir": str(output_dir),
        "measurement_case": str(measurement_case_path),
        "clickable_inventory": str(clickable_inventory_path),
        "selector_trace": str(selector_trace_path),
        "ai_extraction": str(ai_extraction_path) if ai_image_parse_result else None,
        "tag_template": str(tag_template_path),
        "trigger_selector": str(trigger_selector_path),
        "report": str(report_path),
        "resolved_case_input": str(resolved_case_input_path),
        "run_summary": str(run_summary_path),
        "status": run_summary["status"],
        "warnings_count": len(warning_messages),
    }
