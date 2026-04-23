"""PDF source ingestion and conversion to prepared images + native text."""

from __future__ import annotations

from pathlib import Path

from core.intake.manifest import PreparedImage


class PdfConversionError(RuntimeError):
    """Raised when a PDF source cannot be converted to images/text."""



def _extract_native_text(pdf_path: Path) -> list[dict[str, str]]:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise PdfConversionError(
            "No se pudo extraer texto nativo del PDF porque falta dependencia `pypdf`."
        ) from exc

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:
        raise PdfConversionError(f"No se pudo abrir el PDF para lectura de texto: {pdf_path.name}.") from exc

    pages: list[dict[str, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        pages.append({"page": index, "text": text})
    return pages


def _render_images(pdf_path: Path, destination_dir: Path) -> list[PreparedImage]:
    try:
        import pypdfium2 as pdfium
    except Exception as exc:
        raise PdfConversionError(
            "No se pudo convertir PDF a imágenes porque falta dependencia `pypdfium2`."
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
        raise PdfConversionError("No se pudo convertir PDF a imágenes. Verifica que el archivo no esté corrupto.") from exc

    return prepared_images


def prepare_assets_from_pdf(*, pdf_path: Path, destination_dir: Path) -> dict:
    native_text_pages = _extract_native_text(pdf_path)
    prepared_images = _render_images(pdf_path, destination_dir)

    return {
        "prepared_images": prepared_images,
        "native_text_entries": [
            {
                "index": item["page"],
                "source": f"{pdf_path}#page={item['page']}",
                "text": item["text"],
                "kind": "pdf_page",
            }
            for item in native_text_pages
        ],
    }
