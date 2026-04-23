"""PDF source ingestion and conversion to prepared images."""

from __future__ import annotations

from pathlib import Path

from core.intake.manifest import PreparedImage


class PdfConversionError(RuntimeError):
    """Raised when a PDF source cannot be converted to images."""



def prepare_images_from_pdf(*, pdf_path: Path, destination_dir: Path) -> list[PreparedImage]:
    try:
        import pypdfium2 as pdfium
    except Exception as exc:
        raise PdfConversionError(
            "No se pudo convertir PDF a imágenes porque falta dependencia `pypdfium2`. "
            "Instala requirements.txt y reintenta."
        ) from exc

    destination_dir.mkdir(parents=True, exist_ok=True)

    prepared_images: list[PreparedImage] = []
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
    except Exception as exc:
        raise PdfConversionError(f"No se pudo abrir el PDF: {pdf_path.name}.") from exc

    try:
        for index in range(len(pdf)):
            page = pdf[index]
            bitmap = page.render(scale=2)
            image = bitmap.to_pil()

            prepared_path = destination_dir / f"{index + 1:03d}.png"
            image.save(prepared_path)
            prepared_images.append(
                PreparedImage(
                    source=f"{pdf_path}#page={index + 1}",
                    prepared=str(prepared_path),
                    index=index + 1,
                )
            )
    except Exception as exc:
        raise PdfConversionError(
            "No se pudo convertir PDF a imágenes. Verifica que el archivo no esté corrupto."
        ) from exc

    return prepared_images
