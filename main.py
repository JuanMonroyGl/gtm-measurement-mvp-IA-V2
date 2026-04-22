"""Thin CLI orchestrator for measurement case flows."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from core.application.inspect_case import inspect_case_input_structure
from core.application.run_case import run_case
from core.cli.context import parse_case_context
from core.cli.errors import UserFacingError
from core.cli.parser import build_parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()

    try:
        if args.command in {"inspect", "run"}:
            context = parse_case_context(repo_root=repo_root, case_path=Path(args.case_path))
            result = inspect_case_input_structure(context=context) if args.command == "inspect" else run_case(context)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        if args.case_id:
            context = parse_case_context(repo_root=repo_root, case_path=Path("inputs") / args.case_id)
            result = inspect_case_input_structure(context=context) if args.inspect_only else run_case(context)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return

        parser.print_help()
        raise SystemExit(2)
    except UserFacingError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
