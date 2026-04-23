"""Prepare and normalize case assets into outputs/<case_id>/prepared_assets/."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from core.cli.context import CaseContext
from core.intake.detect_input import InputDetectionError, detect_case_input
from core.intake.image_input import prepare_images_from_folder
from core.intake.manifest import AssetManifest, write_manifest
from core.intake.pdf_input import PdfConversionError, prepare_assets_from_pdf
from core.intake.pptx_input import PptxConversionError, prepare_assets_from_pptx


class CaseAssetPreparationError(RuntimeError):
    """User-facing errors for case intake and asset preparation."""



def _clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _write_native_text(prepared_root: Path, entries: list[dict]) -> str | None:
    if not entries:
        return None
    output = prepared_root / "native_text.json"
    output.write_text(json.dumps({"entries": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output)


def _write_sidecar_from_native_text(prepared_root: Path, entries: list[dict], prepared_images: list[dict]) -> None:
    if not entries:
        return

    image_names: list[str] = []
    for item in prepared_images:
        prepared_path = Path(item["prepared"]) if isinstance(item, dict) else Path(item.prepared)
        image_names.append(prepared_path.name)

    images_payload = []
    for idx, entry in enumerate(entries, start=1):
        mapped_image = image_names[idx - 1] if idx - 1 < len(image_names) else f"native_{idx:03d}.txt"
        text = str(entry.get("text") or "")
        lines = [line for line in text.splitlines() if line.strip()]
        images_payload.append({"image": mapped_image, "lines": lines})

    sidecar = prepared_root / "image_evidence.json"
    sidecar.write_text(json.dumps({"images": images_payload}, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_case_assets(*, context: CaseContext) -> dict:
    case_dir = context.case_dir
    prepared_root = context.repo_root / "outputs" / context.case_id / "prepared_assets"
    prepared_images_dir = prepared_root / "images"
    temp_dir = prepared_root / "tmp"
    manifest_path = prepared_root / "asset_manifest.json"

    _clean_dir(prepared_root)
    prepared_images_dir.mkdir(parents=True, exist_ok=True)

    sidecar_source = case_dir / "image_evidence.json"
    if sidecar_source.exists():
        shutil.copy2(sidecar_source, prepared_root / "image_evidence.json")

    warnings: list[str] = []
    errors: list[str] = []
    native_text_entries: list[dict] = []

    try:
        detection = detect_case_input(case_dir)
    except InputDetectionError as exc:
        errors.append(str(exc))
        manifest = AssetManifest(
            case_id=context.case_id,
            input_type="unknown",
            source_files=[],
            selected_input_path=None,
            prepared_images=[],
            warnings=warnings,
            errors=errors,
            ready=False,
            native_text_path=None,
        )
        write_manifest(manifest, manifest_path)
        raise CaseAssetPreparationError(str(exc)) from exc

    input_type = detection["input_type"]
    source_files = detection["files"]
    selected_input_path = detection.get("selected_input_path")

    prepared_images = []
    try:
        if input_type == "images":
            prepared_images = prepare_images_from_folder(
                source_images=source_files,
                destination_dir=prepared_images_dir,
            )
        elif input_type == "pdf":
            prepared = prepare_assets_from_pdf(
                pdf_path=source_files[0],
                destination_dir=prepared_images_dir,
            )
            prepared_images = prepared["prepared_images"]
            native_text_entries = prepared.get("native_text_entries") or []
        elif input_type == "pptx":
            prepared = prepare_assets_from_pptx(
                pptx_path=source_files[0],
                destination_dir=prepared_images_dir,
                temp_dir=temp_dir,
            )
            prepared_images = prepared["prepared_images"]
            native_text_entries = prepared.get("native_text_entries") or []
            warnings.extend(prepared.get("warnings") or [])
        else:
            raise CaseAssetPreparationError(f"Formato no soportado: {input_type}")
    except (PdfConversionError, PptxConversionError, CaseAssetPreparationError) as exc:
        errors.append(str(exc))

    if input_type in {"pdf", "pptx"} and not native_text_entries:
        errors.append(f"No se pudo extraer texto nativo desde {input_type.upper()}.")

    if input_type == "images" and not prepared_images and not errors:
        errors.append("No se prepararon imágenes desde el input detectado.")

    native_text_path = _write_native_text(prepared_root, native_text_entries)
    if native_text_entries:
        _write_sidecar_from_native_text(prepared_root, native_text_entries, prepared_images)

    manifest = AssetManifest(
        case_id=context.case_id,
        input_type=input_type,
        source_files=[str(path) for path in source_files],
        selected_input_path=str(selected_input_path) if selected_input_path else None,
        prepared_images=prepared_images,
        warnings=warnings,
        errors=errors,
        ready=not errors,
        native_text_path=native_text_path,
    )
    write_manifest(manifest, manifest_path)

    if errors:
        raise CaseAssetPreparationError("; ".join(errors))

    return {
        "prepared_root": str(prepared_root),
        "prepared_images_dir": str(prepared_images_dir),
        "manifest_path": str(manifest_path),
        "native_text_path": native_text_path,
        "selected_input_path": str(selected_input_path) if selected_input_path else None,
        "manifest": manifest.to_dict(),
        "native_text_entries": native_text_entries,
    }
