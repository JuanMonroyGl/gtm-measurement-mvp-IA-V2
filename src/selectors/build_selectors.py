"""Selector proposal logic based on DOM + interaction hints."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    replacements = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "¿": "", "?": ""}
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def _css_escape(value: str) -> str:
    return value.replace('"', '\\"')


def _interaction_kind(interaction: dict[str, Any]) -> str:
    elemento = _normalize(interaction.get("elemento"))
    tipo_evento = _normalize(interaction.get("tipo_evento"))
    ubicacion = _normalize(interaction.get("ubicacion"))

    if "menu" in elemento or "clic menu" in tipo_evento or "menu" in ubicacion:
        return "menu"
    if "link" in elemento or "clic link" in tipo_evento:
        return "link"
    if "card" in elemento or "clic card" in tipo_evento:
        return "card"
    if "tap" in elemento or "clic tap" in tipo_evento:
        return "tap"
    return "button"


def _candidate_elements(kind: str, soup: BeautifulSoup) -> list[Tag]:
    if kind == "link":
        return list(soup.select("a[href]"))
    if kind == "tap":
        return list(soup.select("button, summary, [role='button'], [aria-expanded]"))
    if kind == "card":
        return list(soup.select("[class*='card'], article, section, [role='button']"))
    if kind == "menu":
        return list(soup.select("nav a, header a, button, [role='button']"))
    return list(soup.select("button, a[href], [role='button']"))


def _tokenize(value: str | None) -> list[str]:
    normalized = _normalize(value)
    if not normalized:
        return []
    stopwords = {
        "de",
        "la",
        "el",
        "los",
        "las",
        "y",
        "en",
        "del",
        "para",
        "con",
        "por",
        "un",
        "una",
        "al",
    }
    return [
        token
        for token in re.split(r"[^a-z0-9]+", normalized)
        if len(token) >= 3 and token not in stopwords
    ]


def _element_text_for_matching(element: Tag) -> str:
    parts: list[str] = []
    parts.append(" ".join(element.get_text(" ", strip=True).split()))
    for attr in ("aria-label", "title", "alt", "name"):
        value = element.get(attr)
        if isinstance(value, str) and value.strip():
            parts.append(value)
    for attr, value in element.attrs.items():
        if not str(attr).startswith("data-"):
            continue
        if isinstance(value, str) and value.strip():
            parts.append(value)
    return _normalize(" ".join(parts))


def _best_matching_element(
    interaction: dict[str, Any], candidates: list[Tag]
) -> tuple[Tag | None, int]:
    tokens = []
    for field in ("texto_referencia", "elemento", "ubicacion", "flujo"):
        tokens.extend(_tokenize(interaction.get(field)))
    if not tokens:
        return (candidates[0], 0) if candidates else (None, 0)

    best: Tag | None = None
    best_score = 0
    for el in candidates:
        haystack = _element_text_for_matching(el)
        if not haystack:
            continue
        score = sum(1 for token in tokens if token in haystack)
        if score > best_score:
            best = el
            best_score = score
    return best, best_score


def _preferred_selector(interaction: dict[str, Any], soup: BeautifulSoup) -> tuple[str | None, str | None]:
    """Prefer stable selectors from best candidate using neutral text/attribute matching."""
    kind = _interaction_kind(interaction)
    candidates = _candidate_elements(kind, soup)
    best, score = _best_matching_element(interaction, candidates)
    if not best:
        return None, None
    selector = _selector_from_element(best)
    if not selector:
        return None, None
    evidence = (
        f"selector por atributos estables y coincidencia textual (kind={kind}, score={score})"
        if score > 0
        else f"selector por atributo estable sin coincidencia textual fuerte (kind={kind})"
    )
    return selector, evidence


def _selector_from_element(element: Tag) -> str | None:
    if element.get("id"):
        return f"#{_css_escape(element['id'])}"

    data_attrs = sorted([k for k in element.attrs if k.startswith("data-")])
    for attr in data_attrs:
        value = element.get(attr)
        if isinstance(value, str) and value.strip():
            return f'{element.name}[{attr}="{_css_escape(value.strip())}"]'

    for attr in ["aria-label", "aria-controls", "aria-labelledby"]:
        value = element.get(attr)
        if isinstance(value, str) and value.strip():
            return f'{element.name}[{attr}="{_css_escape(value.strip())}"]'

    classes = element.get("class") or []
    stable_classes = [c for c in classes if len(c) > 3 and not c.startswith("swiper-")]
    if stable_classes:
        return f"{element.name}." + ".".join(stable_classes[:2])

    return None


def _fallback_selector(interaction: dict[str, Any], soup: BeautifulSoup) -> tuple[str | None, str | None]:
    kind = _interaction_kind(interaction)
    candidates = _candidate_elements(kind, soup)

    text_ref = _normalize(interaction.get("texto_referencia"))
    best: Tag | None = None
    for el in candidates:
        txt = _normalize(" ".join(el.get_text(" ", strip=True).split()))
        if text_ref and text_ref in txt:
            best = el
            break

    if best is None and candidates:
        best = candidates[0]

    if not best:
        return None, None

    selector = _selector_from_element(best)
    if not selector:
        return None, None

    return selector, "selector fallback por coincidencia textual/estructural"


def propose_selectors(measurement_case: dict[str, Any], dom_snapshot: dict[str, Any]) -> dict[str, Any]:
    html = dom_snapshot.get("rendered_dom_html") or dom_snapshot.get("raw_html")
    if not html:
        return {
            "status": "no_dom",
            "measurement_case": measurement_case,
            "warnings": ["No hay DOM disponible para construir selectores."],
            "selector_evidence": [],
        }

    soup = BeautifulSoup(html, "lxml")
    selector_evidence: list[dict[str, Any]] = []

    for index, interaction in enumerate(measurement_case.get("interacciones", []), start=1):
        interaction.setdefault("warnings", [])
        interaction["warnings"] = [w for w in interaction.get("warnings", []) if "selector_candidato" not in w and "No se encontró selector" not in w]

        selector, evidence = _preferred_selector(interaction, soup)
        if not selector:
            selector, evidence = _fallback_selector(interaction, soup)

        if not selector:
            interaction["selector_candidato"] = None
            interaction["selector_activador"] = None
            interaction["warnings"].append("No se encontró selector con evidencia suficiente.")
            selector_evidence.append({"index": index, "tipo_evento": interaction.get("tipo_evento"), "selector": None, "evidence": None})
            continue

        interaction["selector_candidato"] = selector
        interaction["selector_activador"] = f"{selector}, {selector} *"

        previous_confidence = interaction.get("confidence")
        base_conf = 0.8 if "fallback" not in (evidence or "") else 0.65
        if isinstance(previous_confidence, (int, float)):
            interaction["confidence"] = round((float(previous_confidence) + base_conf) / 2, 2)
        else:
            interaction["confidence"] = base_conf

        selector_evidence.append(
            {
                "index": index,
                "tipo_evento": interaction.get("tipo_evento"),
                "selector": selector,
                "evidence": evidence,
            }
        )

    return {
        "status": "ok",
        "measurement_case": measurement_case,
        "warnings": [],
        "selector_evidence": selector_evidence,
    }
