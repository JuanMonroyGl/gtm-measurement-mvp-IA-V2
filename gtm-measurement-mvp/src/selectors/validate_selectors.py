"""Validate selector candidates against DOM snapshot."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup


def validate_selector_candidates(measurement_case: dict[str, Any], dom_snapshot: dict[str, Any]) -> dict[str, Any]:
    """Compute match_count and ambiguity warnings for each selector."""
    html = dom_snapshot.get("rendered_dom_html") or dom_snapshot.get("raw_html")
    if not html:
        return {
            "status": "no_dom",
            "validated_interactions": 0,
            "warnings": ["No hay DOM disponible para validar selectores."],
        }

    soup = BeautifulSoup(html, "lxml")
    validated = 0
    warnings: list[str] = []

    for interaction in measurement_case.get("interacciones", []):
        selector = interaction.get("selector_candidato")
        interaction.setdefault("warnings", [])
        interaction["warnings"] = [w for w in interaction.get("warnings", []) if "selector_candidato" not in w and "Error al validar selector" not in w and "Sin selector_candidato" not in w]

        if not selector:
            interaction["match_count"] = None
            interaction["warnings"].append("Sin selector_candidato; no se puede validar match_count.")
            continue

        try:
            matches = soup.select(selector)
            match_count = len(matches)
            interaction["match_count"] = match_count
            validated += 1

            if match_count == 0:
                interaction["warnings"].append("selector_candidato no encontró elementos en el DOM.")
            elif match_count > 1:
                interaction["warnings"].append(
                    f"selector_candidato retornó {match_count} matches (posible ambigüedad)."
                )
        except Exception as exc:
            interaction["match_count"] = None
            interaction["warnings"].append(f"Error al validar selector: {exc}")
            warnings.append(f"Selector inválido detectado: {selector}")

    return {
        "status": "ok",
        "validated_interactions": validated,
        "warnings": warnings,
    }
