"""Run full case pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.application.inspect_case import inspect_case_input_structure
from core.application.resolve_case_input import resolve_case_input
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
from core.web_scraping.fetch_page import fetch_html
from core.web_scraping.snapshot_dom import build_dom_snapshot


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

    resolved_case = resolve_case_input(context, images_dir=Path(prepared_images_dir))
    metadata = resolved_case["resolved_metadata"]
    output_dir = ensure_output_dir(context.repo_root, context.case_id)

    parsed_plan = resolved_case["parsed_plan"]
    measurement_case = normalize_case(metadata=metadata, parsed_plan=parsed_plan)

    if not measurement_case.get("interacciones"):
        raise UserFacingError(
            f"No se detectaron interacciones para {context.case_id}. "
            "Revisa OCR, image_evidence.json o metadata (interacciones/eventos) antes de generar GTM."
        )

    target_url = measurement_case.get("target_url")
    fetch_result = fetch_html(target_url=target_url) if target_url else fetch_html(target_url="")
    dom_snapshot = build_dom_snapshot(
        target_url=target_url or "",
        raw_html=fetch_result.html,
    )

    selector_build_result = propose_selectors(
        measurement_case=measurement_case,
        dom_snapshot=dom_snapshot.__dict__,
    )
    selector_build_result["render_engine"] = dom_snapshot.render_engine

    selector_validation = validate_selector_candidates(
        measurement_case=measurement_case,
        dom_snapshot=dom_snapshot.__dict__,
    )
    case_metrics = compute_case_metrics(measurement_case)
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

    measurement_case_path = output_dir / "measurement_case.json"
    tag_template_path = output_dir / "tag_template.js"
    trigger_selector_path = output_dir / "trigger_selector.txt"
    report_path = output_dir / "report.md"
    resolved_case_input_path = output_dir / "resolved_case_input.json"
    run_summary_path = output_dir / "run_summary.json"

    with measurement_case_path.open("w", encoding="utf-8") as f:
        json.dump(measurement_case, f, ensure_ascii=False, indent=2)

    tag_template_path.write_text(tag_template, encoding="utf-8")
    trigger_selector_path.write_text(trigger_selector, encoding="utf-8")
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
        fetch_warning=fetch_result.warning,
        dom_warning=dom_snapshot.warning,
        selector_build_result=selector_build_result,
        selector_validation=selector_validation,
        schema_validation=schema_validation,
        case_metrics=case_metrics,
    )
    report_path.write_text(report_text, encoding="utf-8")

    evidence = parsed_plan.get("evidence") or []
    used_fallback = any(item.get("extraction_method") == "sidecar_text_support" for item in evidence)
    used_ocr = any(item.get("extraction_method") == "rapidocr_text_support" for item in evidence)
    warning_messages = list(input_check.get("warnings", []))
    warning_messages.extend(resolved_case.get("warnings") or [])
    warning_messages.extend(resolved_case.get("messages") or [])
    warning_messages.extend(parsed_plan.get("warnings") or [])
    if fetch_result.warning:
        warning_messages.append(fetch_result.warning)
    if dom_snapshot.warning:
        warning_messages.append(dom_snapshot.warning)
    for interaction in measurement_case.get("interacciones", []):
        warning_messages.extend(interaction.get("warnings") or [])
    warning_messages = sorted(set(warning_messages))

    ambiguity_detected = any(
        isinstance(interaction.get("match_count"), int) and interaction.get("match_count", 0) > 1
        for interaction in measurement_case.get("interacciones", [])
    )
    run_summary = build_run_summary(
        context=context,
        inspect_result=input_check,
        status="warning" if warning_messages else "success",
        warning_messages=warning_messages,
        outputs_generated={
            "asset_manifest": str((Path(prepared_images_dir).parent / "asset_manifest.json")),
            "measurement_case": str(measurement_case_path),
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
    )
    run_summary_path.write_text(json.dumps(run_summary, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "case_id": context.case_id,
        "output_dir": str(output_dir),
        "measurement_case": str(measurement_case_path),
        "tag_template": str(tag_template_path),
        "trigger_selector": str(trigger_selector_path),
        "report": str(report_path),
        "resolved_case_input": str(resolved_case_input_path),
        "run_summary": str(run_summary_path),
        "status": run_summary["status"],
        "warnings_count": len(warning_messages),
    }
