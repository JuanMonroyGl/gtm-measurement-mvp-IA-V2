"""Inspect case structure and executability."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.application.resolve_case_input import allowed_image, load_metadata_checked, resolve_case_input
from core.cli.context import CaseContext
from core.cli.errors import UserFacingError
from core.plan_reader.extract_plan_from_images import get_ocr_runtime_status


def inspect_case_input_structure(*, context: CaseContext) -> dict[str, Any]:
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
        images = sorted(p for p in images_dir.iterdir() if allowed_image(p))
        if not images:
            missing.append(f"No se encontraron imágenes en: {images_dir}")

    metadata_errors: list[str] = []
    warnings: list[str] = []
    target_url: str | None = None
    infer_messages: list[str] = []
    metadata_present = metadata_path.exists()
    if metadata_path.exists():
        try:
            metadata = load_metadata_checked(case_dir)
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
