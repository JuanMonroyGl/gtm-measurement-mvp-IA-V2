"""Run summary payload builder."""

from __future__ import annotations

from typing import Any

from core.cli.context import CaseContext


def build_run_summary(
    *,
    context: CaseContext,
    inspect_result: dict[str, Any],
    status: str,
    warning_messages: list[str],
    outputs_generated: dict[str, str] | None = None,
    interactions_detected: int | None = None,
    ambiguity_detected: bool | None = None,
    used_ocr: bool | None = None,
    used_fallback: bool | None = None,
    render_engine: str | None = None,
    selector_metrics: dict[str, Any] | None = None,
    gate_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "case_id": context.case_id,
        "status": status,
        "inputs_detected": {
            "case_dir": inspect_result.get("case_dir"),
            "images_dir": inspect_result.get("images_dir"),
            "metadata_path": inspect_result.get("metadata_path"),
            "fallback_path": inspect_result.get("sidecar_path"),
        },
        "image_count": inspect_result.get("image_count"),
        "target_url": inspect_result.get("target_url"),
        "runtime": {
            "used_ocr": used_ocr,
            "used_fallback": used_fallback,
            "render_engine": render_engine,
            "ai_available": (inspect_result.get("ai_status") or {}).get("ai_available"),
            "ocr_available": inspect_result.get("ocr_available"),
            "fallback_available": inspect_result.get("fallback_available"),
        },
        "interactions_detected": interactions_detected,
        "ambiguity_detected": ambiguity_detected,
        "selector_metrics": selector_metrics or {},
        "gate": gate_result or {},
        "outputs_generated": outputs_generated or {},
        "warnings": warning_messages,
    }
