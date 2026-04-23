"""Manifest helpers for prepared case assets."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json


@dataclass
class PreparedImage:
    source: str
    prepared: str
    index: int


@dataclass
class AssetManifest:
    case_id: str
    input_type: str
    source_files: list[str]
    prepared_images: list[PreparedImage]
    warnings: list[str]
    errors: list[str]
    ready: bool

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["prepared_image_count"] = len(self.prepared_images)
        return payload


def write_manifest(manifest: AssetManifest, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
