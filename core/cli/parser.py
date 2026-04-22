"""Argument parser for the main CLI."""

from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CLI simple para inspeccionar y ejecutar casos de medición.")
    subparsers = parser.add_subparsers(dest="command")

    inspect_parser = subparsers.add_parser("inspect", help="Valida estructura y prerequisitos del caso.")
    inspect_parser.add_argument("--case-path", required=True, help="Ruta del caso. Ej: inputs/case_001")

    run_parser = subparsers.add_parser("run", help="Ejecuta el pipeline completo para un caso.")
    run_parser.add_argument("--case-path", required=True, help="Ruta del caso. Ej: inputs/case_001")

    parser.add_argument(
        "--repo-root",
        default=".",
        help="Raíz del repo que contiene inputs/ y outputs/. Default: .",
    )
    parser.add_argument(
        "--case-id",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--inspect-only",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser
