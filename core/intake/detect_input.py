"""Detect supported measurement plan input format for a case."""

from __future__ import annotations

from pathlib import Path


SUPPORTED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}


class InputDetectionError(ValueError):
    """Raised when case input cannot be detected unambiguously."""



def _list_images(images_dir: Path) -> list[Path]:
    if not images_dir.exists() or not images_dir.is_dir():
        return []
    return sorted(path for path in images_dir.iterdir() if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXT)


def _list_candidates(case_dir: Path, suffix: str) -> list[Path]:
    source_dir = case_dir / "source"
    from_root = [p for p in case_dir.iterdir() if p.is_file() and p.suffix.lower() == suffix] if case_dir.exists() else []
    from_source = [p for p in source_dir.iterdir() if p.is_file() and p.suffix.lower() == suffix] if source_dir.exists() else []
    return sorted(from_root + from_source)


def detect_case_input(case_dir: Path) -> dict:
    images_dir = case_dir / "images"

    image_files = _list_images(images_dir)
    pdf_files = _list_candidates(case_dir, ".pdf")
    pptx_files = _list_candidates(case_dir, ".pptx")
    legacy_ppt_files = _list_candidates(case_dir, ".ppt")

    detected: list[tuple[str, list[Path]]] = []
    if image_files:
        detected.append(("images", image_files))
    if pdf_files:
        detected.append(("pdf", pdf_files))
    if pptx_files:
        detected.append(("pptx", pptx_files))

    if len(detected) > 1:
        found = ", ".join(kind for kind, _ in detected)
        raise InputDetectionError(
            "Se detectaron múltiples entradas incompatibles en el caso "
            f"({found}). Deja solo una fuente: images/, un PDF o un PPTX."
        )

    if legacy_ppt_files and not detected:
        names = ", ".join(path.name for path in legacy_ppt_files)
        raise InputDetectionError(
            f"Formato .ppt no soportado en esta fase ({names}). Convierte el archivo a .pptx e intenta de nuevo."
        )

    if len(detected) == 1:
        input_type, files = detected[0]
        if len(files) > 1 and input_type in {"pdf", "pptx"}:
            names = ", ".join(path.name for path in files)
            raise InputDetectionError(
                f"Se detectaron múltiples archivos {input_type} en el caso: {names}. "
                "Deja un único archivo fuente para continuar."
            )
        selected = files[0] if input_type in {"pdf", "pptx"} else images_dir
        return {
            "input_type": input_type,
            "files": files,
            "selected_input_path": selected,
            "legacy_ppt_files": legacy_ppt_files,
        }

    if legacy_ppt_files:
        names = ", ".join(path.name for path in legacy_ppt_files)
        raise InputDetectionError(
            f"Formato .ppt no soportado en esta fase ({names}). Convierte el archivo a .pptx e intenta de nuevo."
        )

    raise InputDetectionError(
        "No se encontró ningún input válido. Usa images/ con PNG/JPG/WebP, "
        "o un único .pdf/.pptx en la raíz del caso o en source/."
    )
