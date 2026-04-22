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


def _stability_signals(element: Tag) -> dict[str, Any]:
    data_attrs = sorted([k for k in element.attrs if str(k).startswith("data-")])
    aria_attrs = [k for k in ("aria-label", "aria-controls", "aria-labelledby") if element.get(k)]
    classes = element.get("class") or []
    stable_classes = [c for c in classes if len(c) > 3 and not c.startswith("swiper-")]

    if element.get("id"):
        primary = "id"
    elif data_attrs:
        primary = "data-*"
    elif aria_attrs:
        primary = "aria-*"
    elif stable_classes:
        primary = "stable_class"
    else:
        primary = "none"

    stability_score = (
        (100 if element.get("id") else 0)
        + (40 if data_attrs else 0)
        + (20 if aria_attrs else 0)
        + min(len(stable_classes), 2) * 5
    )
    return {
        "primary": primary,
        "has_id": bool(element.get("id")),
        "data_attrs": data_attrs[:3],
        "aria_attrs": aria_attrs[:3],
        "stable_classes": stable_classes[:3],
        "stability_score": stability_score,
    }


def _candidate_trace(
    *,
    element: Tag,
    kind: str,
    tokens: list[str],
) -> dict[str, Any]:
    haystack = _element_text_for_matching(element)
    matched_tokens = [token for token in tokens if token in haystack]
    selector = _selector_from_element(element)
    signals = _stability_signals(element)
    ranking_score = len(matched_tokens) * 10 + int(signals["stability_score"])
    text_preview = _normalize(" ".join(element.get_text(" ", strip=True).split()))[:120]

    return {
        "kind": kind,
        "selector": selector,
        "matched_tokens": matched_tokens[:6],
        "token_match_count": len(matched_tokens),
        "stability": signals,
        "ranking_score": ranking_score,
        "text_preview": text_preview,
    }


def _rank_candidates(interaction: dict[str, Any], candidates: list[Tag], kind: str) -> list[dict[str, Any]]:
    tokens: list[str] = []
    for field in ("texto_referencia", "elemento", "ubicacion", "flujo"):
        tokens.extend(_tokenize(interaction.get(field)))

    traces = [_candidate_trace(element=el, kind=kind, tokens=tokens) for el in candidates]
    traces = [trace for trace in traces if trace.get("selector")]
    traces.sort(
        key=lambda trace: (
            int(trace.get("ranking_score", 0)),
            int(trace.get("token_match_count", 0)),
            int((trace.get("stability") or {}).get("stability_score", 0)),
        ),
        reverse=True,
    )
    return traces


def _preferred_selector(interaction: dict[str, Any], soup: BeautifulSoup) -> tuple[str | None, str | None]:
    """Prefer stable selectors from best candidate using neutral text/attribute matching."""
    kind = _interaction_kind(interaction)
    candidates = _candidate_elements(kind, soup)
    ranked = _rank_candidates(interaction, candidates, kind=kind)
    if not ranked:
        return None, None
    best = ranked[0]
    selector = best.get("selector")
    if not selector:
        return None, None
    stability = best.get("stability") or {}
    score = best.get("token_match_count", 0)
    evidence = (
        "selector priorizado por score combinado "
        f"(kind={kind}, token_matches={score}, primary_stability={stability.get('primary')})"
        if score > 0
        else (
            "selector priorizado por estabilidad de atributo sin coincidencia textual fuerte "
            f"(kind={kind}, primary_stability={stability.get('primary')})"
        )
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
    used_selectors: set[str] = set()

    for index, interaction in enumerate(measurement_case.get("interacciones", []), start=1):
        interaction.setdefault("warnings", [])
        interaction["warnings"] = [w for w in interaction.get("warnings", []) if "selector_candidato" not in w and "No se encontró selector" not in w]

        selector, evidence = _preferred_selector(interaction, soup)
        kind = _interaction_kind(interaction)
        candidate_pool = _candidate_elements(kind, soup)
        ranked_candidates = _rank_candidates(interaction, candidate_pool, kind=kind)
        if not selector:
            selector, evidence = _fallback_selector(interaction, soup)

        if not selector:
            interaction["selector_candidato"] = None
            interaction["selector_activador"] = None
            interaction["warnings"].append("No se encontró selector con evidencia suficiente.")
            selector_evidence.append(
                {
                    "index": index,
                    "tipo_evento": interaction.get("tipo_evento"),
                    "selector": None,
                    "evidence": None,
                    "selection_trace": {
                        "kind": kind,
                        "candidates_considered": len(candidate_pool),
                        "top_candidates": ranked_candidates[:3],
                        "selected_reason": "No hubo candidato con selector estable disponible.",
                    },
                }
            )
            continue

        if selector in used_selectors:
            alternative = next(
                (candidate for candidate in ranked_candidates if candidate.get("selector") and candidate.get("selector") not in used_selectors),
                None,
            )
            if alternative and alternative.get("selector"):
                selector = str(alternative["selector"])
                evidence = (
                    "selector alternativo elegido para evitar condición runtime duplicada "
                    f"(kind={kind}, score={alternative.get('ranking_score')}, "
                    f"primary_stability={(alternative.get('stability') or {}).get('primary')})"
                )

        interaction["selector_candidato"] = selector
        interaction["selector_activador"] = f"{selector}, {selector} *"
        used_selectors.add(selector)

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
                "selection_trace": {
                    "kind": kind,
                    "candidates_considered": len(candidate_pool),
                    "top_candidates": ranked_candidates[:3],
                    "selected_reason": evidence,
                },
            }
        )

    return {
        "status": "ok",
        "measurement_case": measurement_case,
        "warnings": [],
        "selector_evidence": selector_evidence,
    }
