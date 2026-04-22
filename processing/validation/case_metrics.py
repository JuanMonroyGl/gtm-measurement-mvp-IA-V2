"""Aggregate deterministic case-level metrics for selector quality reporting."""

from __future__ import annotations

from typing import Any


def compute_case_metrics(measurement_case: dict[str, Any]) -> dict[str, Any]:
    """Compute summary metrics from finalized interactions."""
    interactions = measurement_case.get("interacciones", [])
    total = len(interactions)

    with_selector = 0
    match_count_0 = 0
    match_count_1 = 0
    match_count_gt_1 = 0
    interactions_with_warnings = 0
    total_warnings = 0

    for interaction in interactions:
        if interaction.get("selector_candidato"):
            with_selector += 1

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

    ambiguity_rate = round((match_count_gt_1 / total), 4) if total > 0 else 0.0

    return {
        "total_interactions": total,
        "interactions_with_selector": with_selector,
        "match_count_0": match_count_0,
        "match_count_1": match_count_1,
        "match_count_gt_1": match_count_gt_1,
        "ambiguity_rate": ambiguity_rate,
        "interactions_with_warnings": interactions_with_warnings,
        "total_warnings": total_warnings,
    }

