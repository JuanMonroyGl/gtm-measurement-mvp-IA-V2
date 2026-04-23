"""Strict regression checks for generated MVP outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from core.checks.output_gate import evaluate_output_gate

STUB_MARKERS = [
    "Stub GTM tag template",
    "Pending implementation",
    "TODO: Implement final tag generation",
]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_case_outputs(repo_root: Path, case_id: str) -> None:
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))
    from core.processing.validation.case_metrics import compute_case_metrics
    from core.processing.validation.schema_validation import validate_measurement_case_schema

    output_dir = repo_root / "outputs" / case_id
    measurement_case_path = output_dir / "measurement_case.json"
    tag_template_path = output_dir / "tag_template.js"
    trigger_selector_path = output_dir / "trigger_selector.txt"
    selector_trace_path = output_dir / "selector_trace.json"
    clickable_inventory_path = output_dir / "clickable_inventory.json"

    for path in (
        measurement_case_path,
        tag_template_path,
        trigger_selector_path,
        selector_trace_path,
        clickable_inventory_path,
    ):
        _assert(path.exists(), f"Missing file: {path}")

    measurement_case = json.loads(measurement_case_path.read_text(encoding="utf-8"))
    selector_trace = json.loads(selector_trace_path.read_text(encoding="utf-8"))
    clickable_inventory = json.loads(clickable_inventory_path.read_text(encoding="utf-8"))
    schema_validation = validate_measurement_case_schema(repo_root=repo_root, measurement_case=measurement_case)
    _assert(
        schema_validation.valid,
        "measurement_case.json no cumple schema: " + "; ".join(schema_validation.errors),
    )

    interactions = measurement_case.get("interacciones", [])
    _assert(isinstance(interactions, list), "interacciones must be a list")
    _assert(len(interactions) > 0, "measurement_case.json has empty interacciones")
    for idx, interaction in enumerate(interactions, start=1):
        warnings = interaction.get("warnings")
        _assert(isinstance(warnings, list), f"interaction[{idx}] warnings must be a list")

        confidence = interaction.get("confidence")
        if confidence is not None:
            _assert(
                isinstance(confidence, (int, float)) and 0 <= float(confidence) <= 1,
                f"interaction[{idx}] confidence must be between 0 and 1",
            )

        selector_candidato = interaction.get("selector_candidato")
        selector_activador = interaction.get("selector_activador")
        if selector_candidato:
            expected = f"{selector_candidato}, {selector_candidato} *"
            _assert(
                selector_activador == expected,
                f"interaction[{idx}] selector_activador should match consolidated pattern",
            )

    metrics = compute_case_metrics(measurement_case, selector_trace.get("selector_evidence"))
    _assert(metrics["total_interactions"] == len(interactions), "metrics total_interactions mismatch")
    _assert(
        metrics["match_count_0"] + metrics["match_count_1"] + metrics["match_count_gt_1"] <= len(interactions),
        "metrics match_count buckets are inconsistent",
    )

    tag_template = tag_template_path.read_text(encoding="utf-8")
    _assert(tag_template.strip() != "", "tag_template.js is empty")
    for marker in STUB_MARKERS:
        _assert(marker not in tag_template, f"tag_template.js still looks like stub: found '{marker}'")

    trigger_selector = trigger_selector_path.read_text(encoding="utf-8")
    _assert(trigger_selector.strip() != "", "trigger_selector.txt is empty")

    gate = evaluate_output_gate(
        measurement_case=measurement_case,
        selector_trace=selector_trace,
        clickable_inventory=clickable_inventory,
        tag_template=tag_template,
        trigger_selector=trigger_selector,
    )
    _assert(gate["passed"], "output gate failed: " + "; ".join(gate["errors"]))

    print("OK: strict output checks passed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run strict regression checks for a generated case")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--case-id", required=True)
    args = parser.parse_args()

    check_case_outputs(repo_root=Path(args.repo_root), case_id=args.case_id)


if __name__ == "__main__":
    main()
