"""Normalization utilities for measurement cases."""

from __future__ import annotations

from typing import Any


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
    if image_candidates:
        return image_candidates[0]
    return metadata_plan_url


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

    for raw in parsed_plan.get("interactions_raw", []):
        fields = raw.get("fields", {})
        image_plan_url = _pick_plan_url(
            raw.get("plan_url_candidates", []),
            metadata_plan_url,
        )

        warnings = list(raw.get("warnings", []))

        if _is_conflict(metadata_activo, fields.get("activo")):
            warnings.append("Conflicto activo imagen vs metadata: se prioriza metadata.")
        if _is_conflict(metadata_seccion, fields.get("seccion")):
            warnings.append("Conflicto seccion imagen vs metadata: se prioriza metadata.")
        if _is_conflict(metadata_plan_url, image_plan_url):
            warnings.append("plan_url difiere entre imagen y metadata: se conserva ambas referencias.")
        if metadata_target_url and image_plan_url and metadata_target_url != image_plan_url:
            warnings.append("target_url (ejecución) difiere de plan_url (referencia).")

        normalized_interactions.append(
            {
                "tipo_evento": fields.get("tipo_evento"),
                "activo": metadata_activo,
                "seccion": metadata_seccion,
                "flujo": fields.get("flujo"),
                "elemento": fields.get("elemento"),
                "ubicacion": fields.get("ubicacion"),
                "plan_url": image_plan_url,
                "target_url": metadata_target_url,
                "page_path_regex": metadata_page_path_regex,
                "texto_referencia": fields.get("texto_referencia"),
                "selector_candidato": None,
                "selector_activador": None,
                "match_count": None,
                "confidence": raw.get("confidence"),
                "warnings": warnings,
            }
        )

    return {
        "case_id": metadata.get("case_id"),
        "activo": metadata_activo,
        "seccion": metadata_seccion,
        "plan_url": metadata_plan_url,
        "target_url": metadata_target_url,
        "page_path_regex": metadata_page_path_regex,
        "notes": metadata.get("notes"),
        "interacciones": normalized_interactions,
    }