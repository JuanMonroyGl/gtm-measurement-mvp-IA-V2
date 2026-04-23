"""Prepare raw image folder into standardized prepared_assets format."""

from __future__ import annotations

import shutil
from pathlib import Path

from core.intake.manifest import PreparedImage


SUPPORTED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def prepare_images_from_folder(*, source_images: list[Path], destination_dir: Path) -> list[PreparedImage]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    prepared_images: list[PreparedImage] = []

    for index, source_path in enumerate(sorted(source_images), start=1):
        ext = source_path.suffix.lower()
        if ext not in SUPPORTED_IMAGE_EXT:
            continue

        prepared_name = f"{index:03d}{ext}"
        prepared_path = destination_dir / prepared_name
        shutil.copy2(source_path, prepared_path)

        prepared_images.append(
            PreparedImage(
                source=str(source_path),
                prepared=str(prepared_path),
                index=index,
            )
        )

    return prepared_images
