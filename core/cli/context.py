"""CLI context utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.cli.errors import UserFacingError


@dataclass
class CaseContext:
    repo_root: Path
    case_dir: Path
    case_id: str


def parse_case_context(*, repo_root: Path, case_path: Path) -> CaseContext:
    case_dir = case_path if case_path.is_absolute() else (repo_root / case_path)
    case_dir = case_dir.resolve()
    if not case_dir.exists():
        raise UserFacingError(f"No existe el caso en la ruta: {case_dir}")
    if not case_dir.is_dir():
        raise UserFacingError(f"La ruta del caso no es un directorio: {case_dir}")
    return CaseContext(repo_root=repo_root.resolve(), case_dir=case_dir, case_id=case_dir.name)
