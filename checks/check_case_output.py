"""Minimal regression checks for generated MVP outputs."""

from __future__ import annotations

import argparse
import json
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
    output_dir = repo_root / "outputs" / case_id
    measurement_case_path = output_dir / "measurement_case.json"
    tag_template_path = output_dir / "tag_template.js"
    trigger_selector_path = output_dir / "trigger_selector.txt"

    _assert(measurement_case_path.exists(), f"Missing file: {measurement_case_path}")
    _assert(tag_template_path.exists(), f"Missing file: {tag_template_path}")
    _assert(trigger_selector_path.exists(), f"Missing file: {trigger_selector_path}")

    measurement_case = json.loads(measurement_case_path.read_text(encoding="utf-8"))
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
