"""PPTX source ingestion via LibreOffice conversion to PDF, then images."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from core.intake.manifest import PreparedImage
from core.intake.pdf_input import PdfConversionError, prepare_images_from_pdf


class PptxConversionError(RuntimeError):
    """Raised when a PPTX source cannot be converted to images."""



def prepare_images_from_pptx(*, pptx_path: Path, destination_dir: Path, temp_dir: Path) -> list[PreparedImage]:
    soffice = shutil.which("soffice")
    libreoffice = shutil.which("libreoffice")
    office_bin = soffice or libreoffice

    if office_bin is None:
        raise PptxConversionError(
            "No se pudo convertir PPTX porque LibreOffice no está disponible (soffice/libreoffice). "
            "Instala LibreOffice o convierte el archivo manualmente a PDF."
        )

    temp_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        office_bin,
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(temp_dir),
        str(pptx_path),
    ]

    process = subprocess.run(cmd, capture_output=True, text=True)
    if process.returncode != 0:
        details = (process.stderr or process.stdout or "").strip()
        raise PptxConversionError(
            "No se pudo convertir PPTX a PDF con LibreOffice. "
            f"Detalle: {details or 'sin detalle adicional.'}"
        )

    pdf_path = temp_dir / f"{pptx_path.stem}.pdf"
    if not pdf_path.exists():
        raise PptxConversionError(
            "No se encontró el PDF convertido desde PPTX. Verifica permisos o formato del archivo."
        )

    try:
        return prepare_images_from_pdf(pdf_path=pdf_path, destination_dir=destination_dir)
    except PdfConversionError as exc:
        raise PptxConversionError(str(exc)) from exc
