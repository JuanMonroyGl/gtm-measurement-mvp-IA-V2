"""Normalization utilities for measurement cases."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


INTERACTION_FIELDS = [
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
    "warnings",
]


def _is_conflict(meta_value: str | None, image_value: str | None) -> bool:
    if not meta_value or not image_value:
        return False
    return meta_value.strip().lower() != image_value.strip().lower()


def _pick_plan_url(image_candidates: list[str], metadata_plan_url: str | None) -> str | None:
    if metadata_plan_url:
        return metadata_plan_url
    if image_candidates:
        return image_candidates[0]
    return None


def _normalize_text_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    cleaned = cleaned.rstrip(".,;:")
    return cleaned or None


def _derive_top_level_section(*, target_url: str | None, plan_url: str | None) -> str | None:
    """Derive top-level site section from URL path.

    Example:
    - /personas/creditos/consumo/compra-cartera -> personas
    - /pagos/apple-pay -> pagos
    """
    source = target_url or plan_url
    if not source:
        return None
    try:
        path = urlparse(source).path or ""
    except Exception:
        return None
    parts = [p for p in path.split("/") if p]
    return parts[0] if parts else None


def _coalesce_metadata_interactions(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("interacciones", "interactions", "eventos"):
        value = metadata.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _normalize_metadata_interaction(
    *,
    entry: dict[str, Any],
    metadata_activo: str | None,
    metadata_seccion: str | None,
    metadata_plan_url: str | None,
    metadata_target_url: str | None,
    metadata_page_path_regex: str | None,
) -> dict[str, Any]:
    warnings = list(entry.get("warnings") or [])
    warnings.append("Interacción completada desde metadata por falta de extracción confiable en imágenes.")

    return {
        "tipo_evento": _normalize_text_value(entry.get("tipo_evento") or entry.get("evento")),
        "activo": _normalize_text_value(entry.get("activo")) or metadata_activo,
        "seccion": _normalize_text_value(entry.get("seccion")) or metadata_seccion,
        "flujo": _normalize_text_value(entry.get("flujo")),
        "elemento": _normalize_text_value(entry.get("elemento")),
        "ubicacion": _normalize_text_value(entry.get("ubicacion")),
        "plan_url": _normalize_text_value(entry.get("plan_url")) or metadata_plan_url,
        "target_url": _normalize_text_value(entry.get("target_url")) or metadata_target_url,
        "page_path_regex": _normalize_text_value(entry.get("page_path_regex")) or metadata_page_path_regex,
        "texto_referencia": _normalize_text_value(entry.get("texto_referencia")),
        "selector_candidato": _normalize_text_value(entry.get("selector_candidato")),
        "selector_activador": _normalize_text_value(entry.get("selector_activador")),
        "match_count": entry.get("match_count"),
        "confidence": entry.get("confidence"),
        "warnings": warnings,
    }


def normalize_case(metadata: dict[str, Any], parsed_plan: dict[str, Any]) -> dict[str, Any]:
    """Create normalized case from metadata + parsed plan result.

    Rules applied:
    - metadata is authoritative on conflicts
    - target_url is execution URL
    - nulls are preserved for low-confidence/non-inferable fields
    """
    normalized_interactions: list[dict[str, Any]] = []

    metadata_activo = metadata.get("activo")
    metadata_seccion = metadata.get("seccion")
    metadata_plan_url = metadata.get("plan_url")
    metadata_target_url = metadata.get("target_url")
    metadata_page_path_regex = metadata.get("page_path_regex")
    derived_seccion = _derive_top_level_section(
        target_url=metadata_target_url,
        plan_url=metadata_plan_url,
    )
    final_seccion = metadata_seccion or derived_seccion
    derived_section_used = bool(derived_seccion and not metadata_seccion)
    section_conflict_detected = bool(
        metadata_seccion
        and derived_seccion
        and derived_seccion.strip().lower() != str(metadata_seccion).strip().lower()
    )

    for raw in parsed_plan.get("interactions_raw", []):
        fields = raw.get("fields", {})
        selected_plan_url = _pick_plan_url(
            raw.get("plan_url_candidates", []),
            metadata_plan_url,
        )
        image_plan_url = (raw.get("plan_url_candidates") or [None])[0]

        warnings = list(raw.get("warnings", []))

        if _is_conflict(metadata_activo, fields.get("activo")):
            warnings.append("Conflicto activo imagen vs metadata: se prioriza metadata.")
        if _is_conflict(final_seccion, fields.get("seccion")):
            warnings.append("Conflicto seccion imagen vs metadata/url: se prioriza metadata cuando existe.")
        if _is_conflict(metadata_plan_url, image_plan_url):
            warnings.append("plan_url difiere entre imagen y metadata: se conserva ambas referencias.")
        if metadata_target_url and image_plan_url and metadata_target_url != image_plan_url:
            warnings.append("target_url (ejecución) difiere de plan_url (referencia).")
        if section_conflict_detected:
            warnings.append("Conflicto metadata.seccion vs sección derivada de URL: se prioriza metadata.")
        if derived_section_used:
            warnings.append("seccion normalizada desde URL: se usa el segmento raíz del path.")

        normalized_interactions.append(
            {
                "tipo_evento": _normalize_text_value(fields.get("tipo_evento")),
                "activo": metadata_activo,
                "seccion": final_seccion,
                "flujo": _normalize_text_value(fields.get("flujo")),
                "elemento": _normalize_text_value(fields.get("elemento")),
                "ubicacion": _normalize_text_value(fields.get("ubicacion")),
                "plan_url": selected_plan_url,
                "target_url": metadata_target_url,
                "page_path_regex": metadata_page_path_regex,
                "texto_referencia": _normalize_text_value(fields.get("texto_referencia")),
                "selector_candidato": None,
                "selector_activador": None,
                "match_count": None,
                "confidence": raw.get("confidence"),
                "warnings": warnings,
            }
        )

    if not normalized_interactions:
        for entry in _coalesce_metadata_interactions(metadata):
            normalized_interactions.append(
                _normalize_metadata_interaction(
                    entry=entry,
                    metadata_activo=metadata_activo,
                    metadata_seccion=final_seccion,
                    metadata_plan_url=metadata_plan_url,
                    metadata_target_url=metadata_target_url,
                    metadata_page_path_regex=metadata_page_path_regex,
                )
            )

    return {
        "case_id": metadata.get("case_id"),
        "activo": metadata_activo,
        "seccion": final_seccion,
        "plan_url": metadata_plan_url,
        "target_url": metadata_target_url,
        "page_path_regex": metadata_page_path_regex,
        "notes": metadata.get("notes"),
        "interacciones": normalized_interactions,
    }
