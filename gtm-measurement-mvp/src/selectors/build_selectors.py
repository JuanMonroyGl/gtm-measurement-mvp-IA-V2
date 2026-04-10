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


def _preferred_selector(interaction: dict[str, Any], soup: BeautifulSoup) -> tuple[str | None, str | None]:
    """Domain-aware but non-hardcoded selector candidates for known interaction shapes."""
    kind = _interaction_kind(interaction)
    text_ref = _normalize(interaction.get("texto_referencia"))
    ubicacion = _normalize(interaction.get("ubicacion"))

    if kind == "button" and "descarga" in text_ref and soup.select('a[href*="apps.apple.com"]'):
        return 'a[href*="apps.apple.com"]', "href estable de App Store"

    if kind == "link" and "compra de cartera" in ubicacion and soup.select('.cardSuperiorDesk .cardBannerDesk'):
        return ".cardSuperiorDesk .cardBannerDesk", "bloque superior de compra de cartera detectado"

    if kind == "menu" and "menu principal" in ubicacion and soup.select('header.wpthemeControlHeader a[aria-label="Display content menu"]'):
        return 'header.wpthemeControlHeader a[aria-label="Display content menu"]', "control de menú principal detectado"

    if kind == "card" and "tasas" in ubicacion and soup.select(".nav-tabs-wrapper .tab-item"):
        return ".nav-tabs-wrapper .tab-item", "tabs de tasas detectados"

    if kind == "button" and "tasas" in ubicacion and soup.select(".contenedor-boton-general a"):
        return ".contenedor-boton-general a", "botón principal de tasas detectado"

    if kind == "link" and "tasas" in ubicacion and soup.select(".lista-tasas-condiciones a"):
        return ".lista-tasas-condiciones a", "lista de tasas/condiciones detectada"

    if kind == "link" and "documentos" in ubicacion and soup.select(".accordion-content .lista-bullets a"):
        return ".accordion-content .lista-bullets a", "links de documentos detectados"

    if kind == "link" and "seguros" in ubicacion and soup.select(".accordion-group p a"):
        return ".accordion-group p a", "links de seguros detectados"

    if kind == "button" and "inscribir" in ubicacion and soup.select('.contenedor-buttons-tabs .swiper .swiper-wrapper .swiper-slide'):
        return '.contenedor-buttons-tabs .swiper .swiper-wrapper .swiper-slide', "grupo de tabs de inscripción detectado"

    if kind == "card" and soup.select('.card-razon-beneficio-vivienda .contenido-card-razon-beneficio-vivienda'):
        return '.card-razon-beneficio-vivienda .contenido-card-razon-beneficio-vivienda', "grupo de cards de beneficios detectado"

    if kind == "tap" and soup.select('.contenido-preguntas-frecuentes .acordeon-pregunta-frecuente'):
        return '.contenido-preguntas-frecuentes .acordeon-pregunta-frecuente', "grupo de preguntas frecuentes detectado"

    if kind == "link" and soup.select('a[href*=".pdf"]'):
        return 'a[href*=".pdf"]', "link PDF estable detectado"

    return None, None


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
    candidates: list[Tag]

    if kind == "link":
        candidates = list(soup.select("a[href]"))
    elif kind == "tap":
        candidates = list(soup.select("button, summary, [role='button']"))
    elif kind == "card":
        candidates = list(soup.select("[class*='card'], article, [role='button']"))
    else:
        candidates = list(soup.select("button, a[href], [role='button']"))

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
