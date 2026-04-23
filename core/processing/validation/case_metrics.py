"""Aggregate deterministic case-level metrics for selector quality reporting."""

from __future__ import annotations

from typing import Any

from core.processing.selectors.build_selectors import (
    SELECTOR_ORIGIN_FALLBACK,
    SELECTOR_ORIGIN_RENDERED,
    SELECTOR_ORIGIN_REJECTED,
)


def compute_case_metrics(
    measurement_case: dict[str, Any],
    selector_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compute summary metrics from finalized interactions and selector trace."""
    interactions = measurement_case.get("interacciones", [])
    total = len(interactions)

    with_selector = 0
    null_selectors = 0
    match_count_0 = 0
    match_count_1 = 0
    match_count_gt_1 = 0
    interactions_with_warnings = 0
    total_warnings = 0

    for interaction in interactions:
        if interaction.get("selector_candidato"):
            with_selector += 1
        else:
            null_selectors += 1

        match_count = interaction.get("match_count")
        if match_count == 0:
            match_count_0 += 1
        elif match_count == 1:
            match_count_1 += 1
        elif isinstance(match_count, int) and match_count > 1:
            match_count_gt_1 += 1

        warnings = interaction.get("warnings") or []
        if warnings:
            interactions_with_warnings += 1
            total_warnings += len(warnings)

    promoted_from_rendered = 0
    candidates_from_fallback = 0
    rejected_for_safety = 0
    human_review_required = 0
    for evidence in selector_evidence or []:
        chosen = evidence.get("chosen") or {}
        chosen_origin = chosen.get("selector_origin") or evidence.get("selector_origin") or SELECTOR_ORIGIN_REJECTED
        if evidence.get("promoted") and chosen_origin == SELECTOR_ORIGIN_RENDERED:
            promoted_from_rendered += 1
        if chosen_origin == SELECTOR_ORIGIN_FALLBACK:
            candidates_from_fallback += 1
        if not evidence.get("promoted"):
            rejected_for_safety += 1
        if evidence.get("human_review_required"):
            human_review_required += 1

    ambiguity_rate = round((match_count_gt_1 / total), 4) if total > 0 else 0.0

    return {
        "total_interactions": total,
        "interactions_with_selector": with_selector,
        "null_selectors": null_selectors,
        "match_count_0": match_count_0,
        "match_count_1": match_count_1,
        "match_count_gt_1": match_count_gt_1,
        "ambiguity_rate": ambiguity_rate,
        "interactions_with_warnings": interactions_with_warnings,
        "total_warnings": total_warnings,
        "promoted_from_rendered_dom": promoted_from_rendered,
        "candidates_from_raw_html_fallback": candidates_from_fallback,
        "rejected_for_safety": rejected_for_safety,
        "human_review_required": human_review_required,
    }
