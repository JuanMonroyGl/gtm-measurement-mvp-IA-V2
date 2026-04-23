#!/usr/bin/env python3
"""Strict regression check: promoted selectors must be grounded in rendered DOM."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from core.checks.output_gate import evaluate_selector_grounding


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate selector grounding against selector_trace/clickable_inventory")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--case-id", required=True)
    args = parser.parse_args()

    root = Path(args.repo_root)
    case_id = args.case_id
    output_dir = root / "outputs" / case_id

    measurement_case_path = output_dir / "measurement_case.json"
    selector_trace_path = output_dir / "selector_trace.json"
    clickable_inventory_path = output_dir / "clickable_inventory.json"

    for path in (measurement_case_path, selector_trace_path, clickable_inventory_path):
        if not path.exists():
            raise SystemExit(f"ERROR: missing required file: {path}")

    measurement_case = json.loads(measurement_case_path.read_text(encoding="utf-8"))
    selector_trace = json.loads(selector_trace_path.read_text(encoding="utf-8"))
    clickable_inventory = json.loads(clickable_inventory_path.read_text(encoding="utf-8"))

    result = evaluate_selector_grounding(measurement_case, selector_trace, clickable_inventory)
    if not result["passed"]:
        raise SystemExit("ERROR: " + "; ".join(result["errors"]))

    print("OK: selector grounding checks passed")


if __name__ == "__main__":
    main()
