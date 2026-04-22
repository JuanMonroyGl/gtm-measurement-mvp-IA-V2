"""CLI entrypoint to run the measurement case pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.output_generation.generate_gtm_tag import build_tag_template
from core.output_generation.generate_trigger import build_consolidated_trigger_selector
from core.plan_reader.extract_plan_from_images import get_ocr_runtime_status, parse_measurement_plan
from core.plan_reader.normalize_plan import normalize_case
from core.web_scraping.fetch_page import fetch_html
from core.web_scraping.snapshot_dom import build_dom_snapshot
from core.processing.selectors.build_selectors import propose_selectors
from core.processing.selectors.validate_selectors import validate_selector_candidates
from core.processing.validation.case_metrics import compute_case_metrics
from core.processing.validation.schema_validation import SchemaValidationResult, validate_measurement_case_schema


class UserFacingError(Exception):
    """Error esperado por mal input/uso del CLI."""


@dataclass
class CaseContext:
    repo_root: Path
    case_dir: Path
    case_id: str


def _allowed_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}


def _parse_case_context(*, repo_root: Path, case_path: Path) -> CaseContext:
    case_dir = case_path if case_path.is_absolute() else (repo_root / case_path)
    case_dir = case_dir.resolve()
    if not case_dir.exists():
        raise UserFacingError(f"No existe el caso en la ruta: {case_dir}")
    if not case_dir.is_dir():
        raise UserFacingError(f"La ruta del caso no es un directorio: {case_dir}")
    return CaseContext(repo_root=repo_root.resolve(), case_dir=case_dir, case_id=case_dir.name)


def _load_metadata_checked(case_dir: Path) -> dict[str, Any]:
    metadata_path = case_dir / "metadata.json"
    if not metadata_path.exists():
        raise UserFacingError(f"Falta metadata.json en: {metadata_path}")
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise UserFacingError(
            f"metadata.json no es JSON válido ({metadata_path}): línea {exc.lineno}, columna {exc.colno}."
        ) from exc

    if not isinstance(payload, dict):
        raise UserFacingError("metadata.json debe ser un objeto JSON (diccionario).")

    return payload


def _normalize_url_candidate(url: str) -> str:
    cleaned = url.strip().rstrip(".,;:")
    if cleaned.endswith("/"):
        return cleaned[:-1]
    return cleaned


def _resolve_unique_target_url(url_candidates: list[str]) -> str:
    normalized = []
    for item in url_candidates:
        if not item:
            continue
        candidate = _normalize_url_candidate(str(item))
        if candidate and candidate not in normalized:
            normalized.append(candidate)

    if not normalized:
        raise UserFacingError("No se pudo inferir una target_url única desde las imágenes.")
    if len(normalized) > 1:
        raise UserFacingError("Se detectaron múltiples URLs candidatas; no es posible continuar automáticamente.")
    return normalized[0]


def _first_non_empty(values: list[str | None]) -> str | None:
    for value in values:
        if value:
            cleaned = str(value).strip()
            if cleaned:
                return cleaned
    return None


def _infer_metadata_from_parsed_plan(
    *,
    context: CaseContext,
    parsed_plan: dict[str, Any],
    require_unique_target_url: bool,
) -> dict[str, Any]:
    interactions_raw = parsed_plan.get("interactions_raw") or []
    evidence = parsed_plan.get("evidence") or []

    url_candidates: list[str] = []
    for entry in interactions_raw:
        for url in entry.get("plan_url_candidates") or []:
            url_candidates.append(str(url))
    for item in evidence:
        for url in item.get("plan_url_candidates") or []:
            url_candidates.append(str(url))

    if require_unique_target_url:
        target_url = _resolve_unique_target_url(url_candidates)
    else:
        normalized = []
        for item in url_candidates:
            candidate = _normalize_url_candidate(str(item))
            if candidate and candidate not in normalized:
                normalized.append(candidate)
        target_url = normalized[0] if normalized else None
    plan_url = _first_non_empty([target_url, *url_candidates])

    activo = _first_non_empty([
        (entry.get("fields") or {}).get("activo")
        for entry in interactions_raw
        if isinstance(entry, dict)
    ])
    seccion = _first_non_empty([
        (entry.get("fields") or {}).get("seccion")
        for entry in interactions_raw
        if isinstance(entry, dict)
    ])

    return {
        "case_id": context.case_id,
        "target_url": target_url,
        "plan_url": plan_url,
        "activo": activo,
        "seccion": seccion,
    }


def resolve_case_input(context: CaseContext) -> dict[str, Any]:
    """Resolve case metadata combining optional metadata.json with images inference."""
    case_dir = context.case_dir
    metadata_path = case_dir / "metadata.json"
    images_dir = case_dir / "images"

    parsed_plan = parse_measurement_plan(images_dir)

    messages: list[str] = []
    warnings: list[str] = []
    metadata_source = "images_inferred"
    explicit_metadata: dict[str, Any] = {}

    if metadata_path.exists():
        explicit_metadata = _load_metadata_checked(case_dir)
        metadata_source = "metadata_override"
    else:
        messages.append("No se encontró metadata.json; se usará metadata inferida.")

    inferred_metadata = _infer_metadata_from_parsed_plan(
        context=context,
        parsed_plan=parsed_plan,
        require_unique_target_url=not bool(explicit_metadata.get("target_url")),
    )

    resolved_target_url = explicit_metadata.get("target_url") or inferred_metadata.get("target_url")
    if not explicit_metadata.get("target_url"):
        messages.append("Se detectó target_url automáticamente desde las imágenes.")

    if not resolved_target_url:
        raise UserFacingError("No se pudo inferir una target_url única desde las imágenes.")

    if explicit_metadata.get("target_url") and inferred_metadata.get("target_url"):
        if str(explicit_metadata["target_url"]).strip() != str(inferred_metadata["target_url"]).strip():
            warnings.append("metadata.target_url difiere de URL inferida desde imágenes; se prioriza metadata.")

    resolved_metadata = {
        "case_id": explicit_metadata.get("case_id") or inferred_metadata.get("case_id") or context.case_id,
        "target_url": resolved_target_url,
        "plan_url": explicit_metadata.get("plan_url") or inferred_metadata.get("plan_url"),
        "activo": explicit_metadata.get("activo") or inferred_metadata.get("activo"),
        "seccion": explicit_metadata.get("seccion") or inferred_metadata.get("seccion"),
        "page_path_regex": explicit_metadata.get("page_path_regex"),
        "notes": explicit_metadata.get("notes"),
        "interacciones": explicit_metadata.get("interacciones")
        or explicit_metadata.get("interactions")
        or explicit_metadata.get("eventos"),
    }

    if not resolved_metadata.get("case_id"):
        resolved_metadata["case_id"] = context.case_id

    return {
        "metadata_source": metadata_source,
        "messages": messages,
        "warnings": warnings,
        "explicit_metadata": explicit_metadata,
        "inferred_metadata": inferred_metadata,
        "resolved_metadata": resolved_metadata,
        "parsed_plan": parsed_plan,
    }


def inspect_case_input_structure(*, context: CaseContext) -> dict[str, Any]:
    """Validate required input structure and metadata contract before running pipeline."""
    case_dir = context.case_dir
    images_dir = case_dir / "images"
    metadata_path = case_dir / "metadata.json"
    sidecar_path = case_dir / "image_evidence.json"
    ocr_status = get_ocr_runtime_status()

    missing: list[str] = []
    if not images_dir.exists():
        missing.append(f"Falta carpeta de imágenes: {images_dir}")

    images: list[Path] = []
    if images_dir.exists():
        images = sorted(p for p in images_dir.iterdir() if _allowed_image(p))
        if not images:
            missing.append(f"No se encontraron imágenes en: {images_dir}")

    metadata_errors: list[str] = []
    warnings: list[str] = []
    target_url: str | None = None
    infer_messages: list[str] = []
    metadata_present = metadata_path.exists()
    if metadata_path.exists():
        try:
            metadata = _load_metadata_checked(case_dir)
            if metadata.get("case_id") and metadata["case_id"] != context.case_id:
                warnings.append(
                    f"metadata.case_id ({metadata['case_id']}) no coincide con carpeta ({context.case_id})."
                )
        except UserFacingError as exc:
            metadata_errors.append(str(exc))
    else:
        warnings.append("No se encontró metadata.json; se intentará resolver metadata desde imágenes.")

    executable = not missing and not metadata_errors
    inferred_metadata: dict[str, Any] | None = None
    resolve_error: str | None = None
    if executable:
        try:
            resolved = resolve_case_input(context)
            target_url = resolved["resolved_metadata"].get("target_url")
            inferred_metadata = resolved.get("inferred_metadata")
            infer_messages = resolved.get("messages") or []
            warnings.extend(resolved.get("warnings") or [])
        except UserFacingError as exc:
            resolve_error = str(exc)
            executable = False

    ai_status = {
        "ai_available": False,
        "hint": "Módulos de IA no integrados en esta versión del CLI.",
    }

    return {
        "case_id": context.case_id,
        "case_dir": str(case_dir),
        "metadata_path": str(metadata_path),
        "images_dir": str(images_dir),
        "sidecar_path": str(sidecar_path),
        "image_count": len(images),
        "is_sufficient": executable,
        "is_executable": executable,
        "missing": missing,
        "metadata_present": metadata_present,
        "metadata_errors": metadata_errors,
        "resolve_error": resolve_error,
        "infer_messages": infer_messages,
        "inferred_metadata": inferred_metadata,
        "warnings": warnings,
        "target_url": target_url,
        "ocr_available": bool(ocr_status.get("ocr_available")),
        "ocr_diagnostic": ocr_status,
        "ai_status": ai_status,
        "fallback_available": sidecar_path.exists(),
    }


def ensure_output_dir(repo_root: Path, case_id: str) -> Path:
    output_dir = repo_root.resolve() / "outputs" / case_id
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _build_run_summary(
    *,
    context: CaseContext,
    inspect_result: dict[str, Any],
    status: str,
    warning_messages: list[str],
    outputs_generated: dict[str, str] | None = None,
    interactions_detected: int | None = None,
    ambiguity_detected: bool | None = None,
    used_ocr: bool | None = None,
    used_fallback: bool | None = None,
) -> dict[str, Any]:
    return {
        "case_id": context.case_id,
        "status": status,
        "inputs_detected": {
            "case_dir": inspect_result.get("case_dir"),
            "images_dir": inspect_result.get("images_dir"),
            "metadata_path": inspect_result.get("metadata_path"),
            "fallback_path": inspect_result.get("sidecar_path"),
        },
        "image_count": inspect_result.get("image_count"),
        "target_url": inspect_result.get("target_url"),
        "runtime": {
            "used_ocr": used_ocr,
            "used_fallback": used_fallback,
            "ai_available": (inspect_result.get("ai_status") or {}).get("ai_available"),
            "ocr_available": inspect_result.get("ocr_available"),
            "fallback_available": inspect_result.get("fallback_available"),
        },
        "interactions_detected": interactions_detected,
        "ambiguity_detected": ambiguity_detected,
        "outputs_generated": outputs_generated or {},
        "warnings": warning_messages,
    }


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


def _render_report(
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


def run_case(context: CaseContext) -> dict[str, Any]:
    case_dir = context.case_dir
    images_dir = case_dir / "images"

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

    resolved_case = resolve_case_input(context)
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

    report_text = _render_report(
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
    run_summary = _build_run_summary(
        context=context,
        inspect_result=input_check,
        status="warning" if warning_messages else "success",
        warning_messages=warning_messages,
        outputs_generated={
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI simple para inspeccionar y ejecutar casos de medición.")
    subparsers = parser.add_subparsers(dest="command")

    inspect_parser = subparsers.add_parser("inspect", help="Valida estructura y prerequisitos del caso.")
    inspect_parser.add_argument("--case-path", required=True, help="Ruta del caso. Ej: inputs/case_001")

    run_parser = subparsers.add_parser("run", help="Ejecuta el pipeline completo para un caso.")
    run_parser.add_argument("--case-path", required=True, help="Ruta del caso. Ej: inputs/case_001")

    parser.add_argument(
        "--repo-root",
        default=".",
        help="Raíz del repo que contiene inputs/ y outputs/. Default: .",
    )
    parser.add_argument(
        "--case-id",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()

    try:
        if args.command in {"inspect", "run"}:
            context = _parse_case_context(repo_root=repo_root, case_path=Path(args.case_path))
            result = inspect_case_input_structure(context=context) if args.command == "inspect" else run_case(context)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        if args.case_id:
            context = _parse_case_context(repo_root=repo_root, case_path=Path("inputs") / args.case_id)
            result = inspect_case_input_structure(context=context) if args.inspect_only else run_case(context)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        parser.print_help()
        raise SystemExit(2)
    except UserFacingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
