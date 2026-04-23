"""Prepare and normalize case assets into outputs/<case_id>/prepared_assets/."""

from __future__ import annotations

import shutil
from pathlib import Path

from core.cli.context import CaseContext
from core.intake.detect_input import InputDetectionError, detect_case_input
from core.intake.image_input import prepare_images_from_folder
from core.intake.manifest import AssetManifest, write_manifest
from core.intake.pdf_input import PdfConversionError, prepare_images_from_pdf
from core.intake.pptx_input import PptxConversionError, prepare_images_from_pptx


class CaseAssetPreparationError(RuntimeError):
    """User-facing errors for case intake and asset preparation."""



def _clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def prepare_case_assets(*, context: CaseContext) -> dict:
    case_dir = context.case_dir
    prepared_root = context.repo_root / "outputs" / context.case_id / "prepared_assets"
    prepared_images_dir = prepared_root / "images"
    temp_dir = prepared_root / "tmp"
    manifest_path = prepared_root / "asset_manifest.json"

    _clean_dir(prepared_root)
    prepared_images_dir.mkdir(parents=True, exist_ok=True)

    sidecar_source = case_dir / "image_evidence.json"
    sidecar_dest = prepared_root / "image_evidence.json"
    if sidecar_source.exists():
        shutil.copy2(sidecar_source, sidecar_dest)

    warnings: list[str] = []
    errors: list[str] = []

    try:
        detection = detect_case_input(case_dir)
    except InputDetectionError as exc:
        errors.append(str(exc))
        manifest = AssetManifest(
            case_id=context.case_id,
            input_type="unknown",
            source_files=[],
            prepared_images=[],
            warnings=warnings,
            errors=errors,
            ready=False,
        )
        write_manifest(manifest, manifest_path)
        raise CaseAssetPreparationError(str(exc)) from exc

    input_type = detection["input_type"]
    source_files = detection["files"]

    try:
        if input_type == "images":
            prepared_images = prepare_images_from_folder(
                source_images=source_files,
                destination_dir=prepared_images_dir,
            )
        elif input_type == "pdf":
            prepared_images = prepare_images_from_pdf(
                pdf_path=source_files[0],
                destination_dir=prepared_images_dir,
            )
        elif input_type == "pptx":
            prepared_images = prepare_images_from_pptx(
                pptx_path=source_files[0],
                destination_dir=prepared_images_dir,
                temp_dir=temp_dir,
            )
        else:
            raise CaseAssetPreparationError(f"Formato no soportado: {input_type}")
    except (PdfConversionError, PptxConversionError, CaseAssetPreparationError) as exc:
        errors.append(str(exc))
        prepared_images = []

    if not prepared_images and not errors:
        errors.append("No se prepararon imágenes desde el input detectado.")

    manifest = AssetManifest(
        case_id=context.case_id,
        input_type=input_type,
        source_files=[str(path) for path in source_files],
        prepared_images=prepared_images,
        warnings=warnings,
        errors=errors,
        ready=not errors,
    )
    write_manifest(manifest, manifest_path)

    if errors:
        raise CaseAssetPreparationError("; ".join(errors))

    return {
        "prepared_root": str(prepared_root),
        "prepared_images_dir": str(prepared_images_dir),
        "manifest_path": str(manifest_path),
        "manifest": manifest.to_dict(),
    }
