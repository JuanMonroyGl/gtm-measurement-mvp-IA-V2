"""Validate selector candidates against DOM snapshot."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup


def validate_selector_candidates(measurement_case: dict[str, Any], dom_snapshot: dict[str, Any]) -> dict[str, Any]:
    """Compute match_count and warnings honoring valid multi-match groups."""
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
    selector_to_indices: dict[str, list[int]] = {}

    for idx, interaction in enumerate(measurement_case.get("interacciones", []), start=1):
        selector = interaction.get("selector_candidato")
        interaction.setdefault("warnings", [])
        interaction["warnings"] = [
            w
            for w in interaction.get("warnings", [])
            if "selector_candidato" not in w
            and "Error al validar selector" not in w
            and "Sin selector_candidato" not in w
        ]

        if not selector:
            interaction["match_count"] = None
            interaction["warnings"].append("Sin selector_candidato; no se puede validar match_count.")
            continue

        try:
            matches = soup.select(selector)
            match_count = len(matches)
            interaction["match_count"] = match_count
            validated += 1
            selector_to_indices.setdefault(selector, []).append(idx)

            if match_count == 0:
                interaction["warnings"].append("selector_candidato no encontró elementos en el DOM.")
            elif match_count > 1:
                interaction["warnings"].append(
                    f"selector_candidato '{selector}' retornó {match_count} matches "
                    "(posible ambigüedad: revisar evidencia de selección y texto de referencia)."
                )
        except Exception as exc:
            interaction["match_count"] = None
            interaction["warnings"].append(f"Error al validar selector: {exc}")
            warnings.append(f"Selector inválido detectado: {selector}")

    for selector, indices in selector_to_indices.items():
        if len(indices) <= 1:
            continue
        warning_text = (
            f"selector_candidato compartido '{selector}' en interacciones {indices}; "
            "riesgo de ramas muertas en if/else if del tag si no hay discriminador adicional."
        )
        warnings.append(warning_text)
        for idx in indices:
            measurement_case["interacciones"][idx - 1]["warnings"].append(warning_text)

    return {
        "status": "ok",
        "validated_interactions": validated,
        "warnings": warnings,
    }
