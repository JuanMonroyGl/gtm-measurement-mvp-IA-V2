"""Minimal regression checks for generated MVP outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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
    from processing.validation.case_metrics import compute_case_metrics
    from processing.validation.schema_validation import validate_measurement_case_schema

    output_dir = repo_root / "outputs" / case_id
    measurement_case_path = output_dir / "measurement_case.json"
    tag_template_path = output_dir / "tag_template.js"
    trigger_selector_path = output_dir / "trigger_selector.txt"

    _assert(measurement_case_path.exists(), f"Missing file: {measurement_case_path}")
    _assert(tag_template_path.exists(), f"Missing file: {tag_template_path}")
    _assert(trigger_selector_path.exists(), f"Missing file: {trigger_selector_path}")

    measurement_case = json.loads(measurement_case_path.read_text(encoding="utf-8"))
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

    metrics = compute_case_metrics(measurement_case)
    _assert(metrics["total_interactions"] == len(interactions), "metrics total_interactions mismatch")
    _assert(
        metrics["match_count_0"] + metrics["match_count_1"] + metrics["match_count_gt_1"] <= len(interactions),
        "metrics match_count buckets are inconsistent",
    )

    selector_payloads: dict[str, set[tuple[str, str, str]]] = {}
    for interaction in interactions:
        selector = interaction.get("selector_candidato")
        if not selector:
            continue
        selector_payloads.setdefault(selector, set()).add(
            (
                str(interaction.get("tipo_evento") or ""),
                str(interaction.get("flujo") or ""),
                str(interaction.get("ubicacion") or ""),
            )
        )
    conflicts = {selector: payloads for selector, payloads in selector_payloads.items() if len(payloads) > 1}
    _assert(
        not conflicts,
        "duplicate selector_candidato with conflicting payloads detected: "
        + "; ".join(f"{selector} -> {sorted(payloads)}" for selector, payloads in conflicts.items()),
    )

    tag_template = tag_template_path.read_text(encoding="utf-8")
    _assert(tag_template.strip() != "", "tag_template.js is empty")
    for marker in STUB_MARKERS:
        _assert(marker not in tag_template, f"tag_template.js still looks like stub: found '{marker}'")

    trigger_selector = trigger_selector_path.read_text(encoding="utf-8")
    _assert(trigger_selector.strip() != "", "trigger_selector.txt is empty")

    print("OK: minimal output checks passed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run minimal regression checks for a generated case")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--case-id", required=True)
    args = parser.parse_args()

    check_case_outputs(repo_root=Path(args.repo_root), case_id=args.case_id)


if __name__ == "__main__":
    main()
