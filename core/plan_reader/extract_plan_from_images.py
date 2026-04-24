"""Plan parser for image-driven measurement plans.

Phase 2 goal:
- extract textual evidence from plan images
- detect interaction fields from that evidence
- keep traceability and confidence/warnings per interaction
"""

from __future__ import annotations

import json
import importlib.util
import re
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

try:
    from rapidocr_onnxruntime import RapidOCR
    RAPIDOCR_IMPORT_ERROR: str | None = None
except Exception as exc:  # optional dependency at runtime
    RapidOCR = None  # type: ignore[assignment]
    RAPIDOCR_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


EVENT_TYPES = {"clic boton", "clic card", "clic link", "clic tap"}
FIELD_LABELS = [
    "evento",
    "activo",
    "seccion",
    "flujo",
    "elemento",
    "titulo card",
    "ubicacion",
    "ej",
]
FIELD_PATTERN = re.compile(
    rf"(?im)^(?P<label>{'|'.join(re.escape(label) for label in FIELD_LABELS)})\s*:\s*"
)


@dataclass
class ImageEvidence:
    """Evidence extracted from one input image."""

    image_path: str
    extracted_lines: list[str]
    extracted_text: str | None
    extraction_method: str
    confidence: float | None
    plan_url_candidates: list[str]


def _detect_opencv_conflict() -> str | None:
    """Detect common cv2 conflict: opencv-python shadows headless build."""
    try:
        opencv_gui = version("opencv-python")
    except PackageNotFoundError:
        opencv_gui = None
    try:
        opencv_headless = version("opencv-python-headless")
    except PackageNotFoundError:
        opencv_headless = None

    if opencv_gui and opencv_headless:
        return (
            "Se detectó opencv-python y opencv-python-headless instalados al tiempo; "
            "puede causar conflicto de importación de cv2."
        )
    return None


def get_ocr_runtime_status() -> dict[str, Any]:
    """Return OCR runtime availability with actionable diagnostics."""
    has_package = importlib.util.find_spec("rapidocr_onnxruntime") is not None
    status: dict[str, Any] = {
        "ocr_available": False,
        "has_rapidocr_package": has_package,
        "import_error": RAPIDOCR_IMPORT_ERROR,
        "init_error": None,
        "opencv_conflict_warning": _detect_opencv_conflict(),
    }

    if not has_package:
        status["hint"] = "Instala dependencias: pip install -r requirements.txt"
        return status

    if RapidOCR is None:
        status["hint"] = "rapidocr_onnxruntime está instalado pero no se pudo importar."
        return status

    try:
        RapidOCR()
    except Exception as exc:
        status["init_error"] = f"{type(exc).__name__}: {exc}"
        status["hint"] = (
            "No se pudo inicializar OCR. Si aparece libGL.so.1 faltante, instala "
            "libgl1 en el sistema o elimina opencv-python y deja solo opencv-python-headless."
        )
        return status

    status["ocr_available"] = True
    status["hint"] = "OCR listo."
    return status


def discover_case_images(case_images_dir: Path) -> list[Path]:
    """Return sorted image paths for a case."""
    if not case_images_dir.exists():
        return []

    allowed_ext = {".png", ".jpg", ".jpeg", ".webp"}
    return sorted(
        p for p in case_images_dir.iterdir() if p.is_file() and p.suffix.lower() in allowed_ext
    )


def _normalize_space(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _extract_urls(text: str) -> list[str]:
    return re.findall(r"https?://\S+", text)


def _find_field(text: str, field_name: str) -> str | None:
    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(FIELD_PATTERN.finditer(normalized_text))
    for idx, match in enumerate(matches):
        label = _normalize_space(match.group("label")).lower()
        if label != field_name.lower():
            continue
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(normalized_text)
        value = normalized_text[start:end]
        value = re.split(r"\nhttps?://\S+", value, maxsplit=1, flags=re.IGNORECASE)[0]
        value = re.sub(r"\n{2,}", "\n", value)
        return _normalize_space(value)
    return None


def _extract_variants(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    match = re.search(r"\{\{(?P<content>.+?)\}\}", raw_value, flags=re.DOTALL)
    if not match:
        return []
    variants = []
    for part in match.group("content").split("|"):
        cleaned = _normalize_space(part)
        if cleaned:
            variants.append(cleaned)
    return variants


def _stringify_variants(raw_value, variants):
    if variants:
        return "{{" + "|".join(variants) + "}}"

    if raw_value is None:
        return None

    return _normalize_space(raw_value)


def _derive_group_context(tipo_evento: str | None, ubicacion: str | None) -> tuple[str | None, str | None]:
    event = _normalize_space(tipo_evento or "").lower()
    location = _normalize_space(ubicacion or "").lower()

    if "barra arriba" in location or "menu" in event:
        return "top_navigation", "header-menu"
    if "lo mas consultado" in location:
        return "faq_collection", "faq-list"
    if "card" in event:
        return "card_collection", "card-grid"
    if "tab" in location or "tab" in event:
        return "shortcut_collection", "shortcut-tabs"
    return None, None


def _derive_value_strategy(
    *,
    interaction_mode: str,
    tipo_evento: str | None,
    title_variants: list[str],
) -> str:
    event = _normalize_space(tipo_evento or "").lower()
    if interaction_mode == "group" and ("card" in event or title_variants):
        return "prefer_title_variant_then_click_text"
    if interaction_mode == "group":
        return "match_element_variant_from_clicked_text"
    return "click_text"


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
    raw_elemento = _find_field(evidence_text, "elemento")
    raw_titulo_card = _find_field(evidence_text, "titulo card")
    ubicacion = _find_field(evidence_text, "ubicacion")
    element_variants = _extract_variants(raw_elemento)
    title_variants = _extract_variants(raw_titulo_card)
    interaction_mode = "group" if len(element_variants) > 1 or len(title_variants) > 1 else "single"
    group_context, zone_hint = _derive_group_context(tipo_evento, ubicacion)

    # Prefer explicit example-like textual reference when available.
    texto_referencia = _find_field(evidence_text, "ej")

    fields = {
        "tipo_evento": tipo_evento,
        "activo": activo,
        "seccion": seccion,
        "flujo": flujo,
        "elemento": _stringify_variants(raw_elemento, element_variants),
        "titulo_card": _stringify_variants(raw_titulo_card, title_variants),
        "ubicacion": ubicacion,
        "texto_referencia": texto_referencia,
        "interaction_mode": interaction_mode,
        "element_variants": element_variants,
        "title_variants": title_variants,
        "group_context": group_context,
        "zone_hint": zone_hint,
        "value_extraction_strategy": _derive_value_strategy(
            interaction_mode=interaction_mode,
            tipo_evento=tipo_evento,
            title_variants=title_variants,
        ),
    }

    warnings: list[str] = []
    for key in ["tipo_evento", "flujo", "elemento", "ubicacion"]:
        if not fields.get(key):
            warnings.append(f"Campo no inferido desde imagen: {key}")
    if interaction_mode == "group" and not element_variants and not title_variants:
        warnings.append("Interacción marcada como group sin variantes estructuradas detectadas.")

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


def _load_sidecar_evidence(case_images_dir: Path) -> list[ImageEvidence]:
    """Load pre-extracted text evidence from inputs/<case_id>/image_evidence.json if present."""
    sidecar_path = case_images_dir.parent / "image_evidence.json"
    if not sidecar_path.exists():
        return []

    try:
        payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    entries = payload if isinstance(payload, list) else payload.get("images", [])
    evidences: list[ImageEvidence] = []

    for entry in entries:
        image_name = entry.get("image")
        lines = entry.get("lines") or []
        if not image_name:
            continue
        image_path = case_images_dir / image_name
        extracted_text = "\n".join(lines) if lines else None
        evidences.append(
            ImageEvidence(
                image_path=str(image_path),
                extracted_lines=lines,
                extracted_text=extracted_text,
                extraction_method="sidecar_text_support",
                confidence=0.7 if lines else 0.0,
                plan_url_candidates=_extract_urls(extracted_text or ""),
            )
        )

    return evidences


def extract_support_text_from_images(case_images_dir: Path) -> list[ImageEvidence]:
    """Extract textual support evidence from images.

    Priority:
    1. Sidecar/native evidence (`image_evidence.json`) when available.
    2. OCR via RapidOCR.
    """
    images = discover_case_images(case_images_dir)
    evidences: list[ImageEvidence] = []

    sidecar_evidences = _load_sidecar_evidence(case_images_dir)
    if sidecar_evidences:
        return sidecar_evidences

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

    try:
        ocr = RapidOCR()
    except Exception:
        for image_path in images:
            evidences.append(
                ImageEvidence(
                    image_path=str(image_path),
                    extracted_lines=[],
                    extracted_text=None,
                    extraction_method="ocr_init_failed",
                    confidence=0.0,
                    plan_url_candidates=[],
                )
            )
        return evidences

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

    ocr_status = get_ocr_runtime_status()
    if not ocr_status.get("ocr_available"):
        reason = ocr_status.get("import_error") or ocr_status.get("init_error") or "OCR no disponible."
        warnings.append(f"OCR no disponible: {reason}")
        if ocr_status.get("opencv_conflict_warning"):
            warnings.append(str(ocr_status["opencv_conflict_warning"]))

    return {
        "parser_status": "ok" if interactions_raw else "partial",
        "image_count": len(evidences),
        "evidence": [e.__dict__ for e in evidences],
        "interactions_raw": interactions_raw,
        "ocr_status": ocr_status,
        "warnings": warnings,
    }
