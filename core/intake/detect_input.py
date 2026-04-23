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


def detect_case_input(case_dir: Path) -> dict:
    images_dir = case_dir / "images"
    source_dir = case_dir / "source"

    image_files = _list_images(images_dir)
    source_files = sorted(path for path in source_dir.iterdir() if path.is_file()) if source_dir.exists() else []

    pdf_files = [path for path in source_files if path.suffix.lower() == ".pdf"]
    pptx_files = [path for path in source_files if path.suffix.lower() == ".pptx"]
    legacy_ppt_files = [path for path in source_files if path.suffix.lower() == ".ppt"]

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
            f"({found}). Deja solo un tipo de input: images/, plan.pdf o plan.pptx."
        )

    if len(detected) == 1:
        input_type, files = detected[0]
        if len(files) > 1 and input_type in {"pdf", "pptx"}:
            names = ", ".join(path.name for path in files)
            raise InputDetectionError(
                f"Se detectaron múltiples archivos {input_type} en source/: {names}. "
                "Deja un solo archivo fuente para el caso."
            )
        return {
            "input_type": input_type,
            "files": files,
            "legacy_ppt_files": legacy_ppt_files,
            "source_files": source_files,
        }

    if legacy_ppt_files:
        names = ", ".join(path.name for path in legacy_ppt_files)
        raise InputDetectionError(
            f"Formato .ppt no soportado en esta fase ({names}). Convierte el archivo a .pptx e intenta de nuevo."
        )

    raise InputDetectionError(
        "No se encontró ningún input válido. Usa una de estas estructuras: "
        "images/ con PNG/JPG/WebP, source/plan.pdf o source/plan.pptx."
    )
