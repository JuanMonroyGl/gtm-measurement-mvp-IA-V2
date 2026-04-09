"""Plan parser for image-driven measurement plans.

Phase 2 goal:
- extract textual evidence from plan images
- detect interaction fields from that evidence
- keep traceability and confidence/warnings per interaction
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:  # optional dependency at runtime
    RapidOCR = None  # type: ignore[assignment]


EVENT_TYPES = {"clic boton", "clic card", "clic link", "clic tap"}


@dataclass
class ImageEvidence:
    """Evidence extracted from one input image."""

    image_path: str
    extracted_lines: list[str]
    extracted_text: str | None
    extraction_method: str
    confidence: float | None
    plan_url_candidates: list[str]


def discover_case_images(case_images_dir: Path) -> list[Path]:
    """Return sorted image paths for a case."""
    if not case_images_dir.exists():
        return []

    allowed_ext = {".png", ".jpg", ".jpeg", ".webp"}
    return sorted(
        p for p in case_images_dir.iterdir() if p.is_file() and p.suffix.lower() in allowed_ext
    )


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://\S+", text)


def _find_field(text: str, field_name: str) -> str | None:
    pattern = re.compile(rf"{field_name}\s*:\s*(.+?)(?:\n|$)", flags=re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return None
    return _normalize_space(match.group(1))


def _safe_event_type(raw_value: str | None) -> str | None:
    if not raw_value:
        return None
    cleaned = _normalize_space(raw_value).lower()
    if cleaned in EVENT_TYPES:
        return cleaned.title()
    return raw_value


def _interaction_confidence(fields: dict[str, str | None]) -> float:
    keys = ["tipo_evento", "activo", "seccion", "flujo", "elemento", "ubicacion"]
    present = sum(1 for key in keys if fields.get(key))
    return round(present / len(keys), 2)


def _parse_interaction_from_text(evidence_text: str, image_path: Path) -> dict[str, Any]:
    tipo_evento = _safe_event_type(_find_field(evidence_text, "evento"))
    activo = _find_field(evidence_text, "activo")
    seccion = _find_field(evidence_text, "seccion")
    flujo = _find_field(evidence_text, "flujo")
    elemento = _find_field(evidence_text, "elemento")
    ubicacion = _find_field(evidence_text, "ubicacion")

    # Prefer explicit example-like textual reference when available.
    texto_referencia = _find_field(evidence_text, "ej")

    fields = {
        "tipo_evento": tipo_evento,
        "activo": activo,
        "seccion": seccion,
        "flujo": flujo,
        "elemento": elemento,
        "ubicacion": ubicacion,
        "texto_referencia": texto_referencia,
    }

    warnings: list[str] = []
    for key in ["tipo_evento", "flujo", "elemento", "ubicacion"]:
        if not fields.get(key):
            warnings.append(f"Campo no inferido desde imagen: {key}")

    return {
        "source_image": str(image_path),
        "fields": fields,
        "plan_url_candidates": _extract_urls(evidence_text),
        "confidence": _interaction_confidence(fields),
        "warnings": warnings,
    }


def _extract_lines_with_ocr(image_path: Path, ocr: Any) -> list[str]:
    result, _ = ocr(str(image_path))
    if not result:
        return []

    lines: list[str] = []
    for item in result:
        text = str(item[1]).strip()
        if text:
            lines.append(text)
    return lines


def extract_support_text_from_images(case_images_dir: Path) -> list[ImageEvidence]:
    """Extract textual support evidence from images.

    This extraction is multimodal-ready by interface, but currently uses OCR text
    extraction as the available first signal.
    """
    images = discover_case_images(case_images_dir)
    evidences: list[ImageEvidence] = []

    if RapidOCR is None:
        for image_path in images:
            evidences.append(
                ImageEvidence(
                    image_path=str(image_path),
                    extracted_lines=[],
                    extracted_text=None,
                    extraction_method="no_ocr_dependency",
                    confidence=0.0,
                    plan_url_candidates=[],
                )
            )
        return evidences

    ocr = RapidOCR()
    for image_path in images:
        lines = _extract_lines_with_ocr(image_path, ocr)
        full_text = "\n".join(lines) if lines else None
        evidences.append(
            ImageEvidence(
                image_path=str(image_path),
                extracted_lines=lines,
                extracted_text=full_text,
                extraction_method="rapidocr_text_support",
                confidence=0.8 if lines else 0.0,
                plan_url_candidates=_extract_urls(full_text or ""),
            )
        )

    return evidences


def parse_measurement_plan(case_images_dir: Path) -> dict[str, Any]:
    """Analyze images and produce interaction candidates + textual evidence."""
    evidences = extract_support_text_from_images(case_images_dir)

    interactions_raw: list[dict[str, Any]] = []
    warnings: list[str] = []

    if not evidences:
        warnings.append("No se encontraron imágenes del caso.")

    for evidence in evidences:
        if not evidence.extracted_text:
            warnings.append(f"Sin texto extraído para {evidence.image_path}")
            continue

        interactions_raw.append(
            _parse_interaction_from_text(
                evidence_text=evidence.extracted_text,
                image_path=Path(evidence.image_path),
            )
        )

    return {
        "parser_status": "ok" if interactions_raw else "partial",
        "image_count": len(evidences),
        "evidence": [e.__dict__ for e in evidences],
        "interactions_raw": interactions_raw,
        "warnings": warnings,
    }
