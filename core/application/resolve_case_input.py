"""Resolve case metadata from optional metadata.json and image-derived evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.cli.context import CaseContext
from core.cli.errors import UserFacingError
from core.plan_reader.extract_plan_from_images import parse_measurement_plan


def allowed_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}


def load_metadata_checked(case_dir: Path) -> dict[str, Any]:
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


def normalize_url_candidate(url: str) -> str:
    cleaned = url.strip().rstrip(".,;:")
    if cleaned.endswith("/"):
        return cleaned[:-1]
    return cleaned


def resolve_unique_target_url(url_candidates: list[str]) -> str:
    normalized = []
    for item in url_candidates:
        if not item:
            continue
        candidate = normalize_url_candidate(str(item))
        if candidate and candidate not in normalized:
            normalized.append(candidate)

    if not normalized:
        raise UserFacingError("No se pudo inferir una target_url única desde las imágenes.")
    if len(normalized) > 1:
        raise UserFacingError("Se detectaron múltiples URLs candidatas; no es posible continuar automáticamente.")
    return normalized[0]


def first_non_empty(values: list[str | None]) -> str | None:
    for value in values:
        if value:
            cleaned = str(value).strip()
            if cleaned:
                return cleaned
    return None


def infer_metadata_from_parsed_plan(
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
        target_url = resolve_unique_target_url(url_candidates)
    else:
        normalized = []
        for item in url_candidates:
            candidate = normalize_url_candidate(str(item))
            if candidate and candidate not in normalized:
                normalized.append(candidate)
        target_url = normalized[0] if normalized else None
    plan_url = first_non_empty([target_url, *url_candidates])

    activo = first_non_empty([
        (entry.get("fields") or {}).get("activo")
        for entry in interactions_raw
        if isinstance(entry, dict)
    ])
    seccion = first_non_empty([
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


def resolve_case_input(context: CaseContext, *, images_dir: Path | None = None) -> dict[str, Any]:
    """Resolve case metadata combining optional metadata.json with images inference."""
    case_dir = context.case_dir
    metadata_path = case_dir / "metadata.json"
    resolved_images_dir = images_dir or (case_dir / "images")

    parsed_plan = parse_measurement_plan(resolved_images_dir)

    messages: list[str] = []
    warnings: list[str] = []
    metadata_source = "images_inferred"
    explicit_metadata: dict[str, Any] = {}

    if metadata_path.exists():
        explicit_metadata = load_metadata_checked(case_dir)
        metadata_source = "metadata_override"
    else:
        messages.append("No se encontró metadata.json; se usará metadata inferida.")

    inferred_metadata = infer_metadata_from_parsed_plan(
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
