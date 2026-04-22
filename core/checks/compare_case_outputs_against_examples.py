#!/usr/bin/env python3
"""Compare generated case outputs against manual benchmark files in assets/examples/."""

from __future__ import annotations

import argparse
import difflib
from pathlib import Path


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _diff(a: str, b: str, from_name: str, to_name: str) -> str:
    lines = difflib.unified_diff(
        a.splitlines(),
        b.splitlines(),
        fromfile=from_name,
        tofile=to_name,
        lineterm="",
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare case outputs vs examples benchmarks")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()

    root = Path(args.repo_root)
    case_id = args.case_id

    generated = {
        "measurement_case": root / "outputs" / case_id / "measurement_case.json",
        "report": root / "outputs" / case_id / "report.md",
        "tag": root / "outputs" / case_id / "tag_template.js",
        "trigger": root / "outputs" / case_id / "trigger_selector.txt",
    }
    expected = {
        "tag": root / "assets" / "examples" / f"{case_id}_expected_tag.js",
        "trigger": root / "assets" / "examples" / f"{case_id}_expected_trigger.txt",
        "notes": root / "assets" / "examples" / f"{case_id}_notes.md",
    }

    missing = [str(path) for path in [*generated.values(), *expected.values()] if not path.exists()]
    if missing:
        print("ERROR: faltan archivos para comparar:")
        for item in missing:
            print(f"- {item}")
        raise SystemExit(1)

    gen_tag = _read_text(generated["tag"])
    exp_tag = _read_text(expected["tag"])
    gen_trigger = _read_text(generated["trigger"])
    exp_trigger = _read_text(expected["trigger"])

    print(f"tag_match: {gen_tag == exp_tag}")
    print(f"trigger_match: {gen_trigger == exp_trigger}")

    if gen_tag != exp_tag:
        print("\n--- tag diff ---")
        print(_diff(exp_tag, gen_tag, str(expected["tag"]), str(generated["tag"])))

    if gen_trigger != exp_trigger:
        print("\n--- trigger diff ---")
        print(_diff(exp_trigger, gen_trigger, str(expected["trigger"]), str(generated["trigger"])))

    print("\nnotes_path:", expected["notes"])


if __name__ == "__main__":
    main()
