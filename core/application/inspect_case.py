"""Inspect case structure, intake readiness and executability."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.application.resolve_case_input import load_metadata_checked, resolve_case_input
from core.cli.context import CaseContext
from core.cli.errors import UserFacingError
from core.intake.prepare_case_assets import CaseAssetPreparationError, prepare_case_assets
from core.plan_reader.extract_plan_from_images import get_ocr_runtime_status


def inspect_case_input_structure(*, context: CaseContext) -> dict[str, Any]:
    case_dir = context.case_dir
    metadata_path = case_dir / "metadata.json"
    sidecar_path = case_dir / "image_evidence.json"
    ocr_status = get_ocr_runtime_status()

    warnings: list[str] = []
    missing: list[str] = []
    metadata_errors: list[str] = []
    target_url: str | None = None
    infer_messages: list[str] = []
    inferred_metadata: dict[str, Any] | None = None

    metadata_present = metadata_path.exists()
    if metadata_present:
        try:
            metadata = load_metadata_checked(case_dir)
            if metadata.get("case_id") and metadata["case_id"] != context.case_id:
                warnings.append(
                    f"metadata.case_id ({metadata['case_id']}) no coincide con carpeta ({context.case_id})."
                )
        except UserFacingError as exc:
            metadata_errors.append(str(exc))
    else:
        warnings.append("No se encontró metadata.json; se intentará resolver metadata desde el plan preparado.")

    intake_result: dict[str, Any] | None = None
    intake_error: str | None = None
    prepared_images_dir: str | None = None

    try:
        intake_result = prepare_case_assets(context=context)
        prepared_images_dir = intake_result["prepared_images_dir"]
    except CaseAssetPreparationError as exc:
        intake_error = str(exc)
        missing.append(str(exc))

    executable = not missing and not metadata_errors
    resolve_error: str | None = None

    if executable and prepared_images_dir:
        try:
            resolved = resolve_case_input(context, images_dir=Path(prepared_images_dir))
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

    prepared_manifest = (intake_result or {}).get("manifest") or {}
    intake_files = prepared_manifest.get("source_files") or []
    prepared_images = prepared_manifest.get("prepared_images") or []

    return {
        "case_id": context.case_id,
        "case_dir": str(case_dir),
        "metadata_path": str(metadata_path),
        "images_dir": str(case_dir / "images"),
        "sidecar_path": str(sidecar_path),
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
        "image_count": len(prepared_images),
        "intake": {
            "detected_input_type": prepared_manifest.get("input_type"),
            "files_found": intake_files,
            "prepared_images_dir": (intake_result or {}).get("prepared_images_dir"),
            "prepared_images": prepared_images,
            "prepared_images_count": len(prepared_images),
            "manifest_path": (intake_result or {}).get("manifest_path"),
            "warnings": prepared_manifest.get("warnings") or [],
            "errors": prepared_manifest.get("errors") or ([] if not intake_error else [intake_error]),
            "ready": bool(prepared_manifest.get("ready")),
        },
    }
