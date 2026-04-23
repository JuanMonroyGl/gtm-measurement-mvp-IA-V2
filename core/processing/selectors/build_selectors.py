"""Selector proposal logic with strict grounding and explicit provenance."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup
from bs4.element import Tag

NODE_ID_ATTR = "data-gtm-mvp-node-id"
SELECTOR_ORIGIN_RENDERED = "observed_rendered_dom"
SELECTOR_ORIGIN_FALLBACK = "raw_html_fallback"
SELECTOR_ORIGIN_REJECTED = "rejected"
SELECTOR_TYPE_WEIGHTS = {
    "id": 100,
    "data": 80,
    "aria": 70,
    "href": 60,
    "class": 35,
    "tag": 5,
}


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    cleaned = text.lower().strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "ü": "u",
        "ñ": "n",
        "¿": "",
        "?": "",
    }
    for src, dst in replacements.items():
        cleaned = cleaned.replace(src, dst)
    return cleaned


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
        "una",
        "uno",
        "unos",
        "unas",
        "al",
    }
    return [token for token in re.split(r"[^a-z0-9]+", normalized) if len(token) >= 3 and token not in stopwords]


def _interaction_tokens(interaction: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    for field in ("texto_referencia", "elemento", "ubicacion", "flujo", "tipo_evento"):
        tokens.extend(_tokenize(interaction.get(field)))
    return list(dict.fromkeys(tokens))


def _selector_type(selector: str) -> str:
    if selector.startswith("#"):
        return "id"
    if "[data-" in selector:
        return "data"
    if "[aria-" in selector:
        return "aria"
    if "[href=" in selector:
        return "href"
    if "." in selector:
        return "class"
    return "tag"


def _selector_match_count(selector: str, soups: dict[str, BeautifulSoup]) -> tuple[int, str | None]:
    best_count = 0
    best_state: str | None = None
    for state, soup in soups.items():
        try:
            count = len(soup.select(selector))
        except Exception:
            count = 0
        if count > best_count:
            best_count = count
            best_state = state
    return best_count, best_state


def _runtime_flags(
    selector: str,
    item: dict[str, Any],
    soups: dict[str, BeautifulSoup],
    observed_state: str | None,
) -> dict[str, Any]:
    state = observed_state or item.get("state") or next(iter(soups.keys()), None)
    node_id = item.get("node_id")
    if not state or not node_id or state not in soups:
        return {
            "exists_in_dom": False,
            "matches_candidate_node": False,
            "closest_runtime_supported": False,
            "click_grounded": False,
        }

    soup = soups[state]
    try:
        matches = soup.select(selector)
    except Exception:
        matches = []
    exists_in_dom = bool(matches)

    candidate_node = soup.select_one(f'[{NODE_ID_ATTR}="{node_id}"]')
    matches_candidate_node = candidate_node in matches if candidate_node else False

    closest_runtime_supported = False
    if candidate_node:
        if matches_candidate_node:
            closest_runtime_supported = True
        else:
            parent = candidate_node.parent
            while isinstance(parent, Tag):
                if parent in matches:
                    closest_runtime_supported = True
                    break
                parent = parent.parent

    click_grounded = bool(
        exists_in_dom
        and matches_candidate_node
        and closest_runtime_supported
        and item.get("is_clickable")
    )
    return {
        "exists_in_dom": exists_in_dom,
        "matches_candidate_node": matches_candidate_node,
        "closest_runtime_supported": closest_runtime_supported,
        "click_grounded": click_grounded,
    }


def _candidate_alignment(interaction: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    tokens = _interaction_tokens(interaction)
    direct_haystack = _normalize(
        " ".join(
            [
                str(item.get("text") or ""),
                str(item.get("aria_label") or ""),
                str(item.get("title") or ""),
                str(item.get("href") or ""),
                str(item.get("id") or ""),
            ]
        )
    )
    context_haystack = _normalize(
        " ".join(
            [
                str(item.get("context_text") or ""),
                " ".join(
                    " ".join(
                        [
                            str(ancestor.get("tag") or ""),
                            str(ancestor.get("id") or ""),
                            " ".join(ancestor.get("classes") or []),
                        ]
                    )
                    for ancestor in (item.get("ancestors") or [])
                ),
            ]
        )
    )
    matched_direct_tokens = [token for token in tokens if token in direct_haystack]
    matched_context_tokens = [token for token in tokens if token not in matched_direct_tokens and token in context_haystack]

    exact_phrase_match = False
    for field in ("texto_referencia", "elemento"):
        normalized = _normalize(interaction.get(field))
        if normalized and len(normalized) >= 4:
            if normalized in direct_haystack or normalized in context_haystack:
                exact_phrase_match = True
                break

    alignment_score = len(matched_direct_tokens) * 35 + len(matched_context_tokens) * 10 + (30 if exact_phrase_match else 0)
    has_minimum_alignment = bool(matched_direct_tokens or exact_phrase_match)

    return {
        "tokens": tokens,
        "matched_tokens": list(dict.fromkeys([*matched_direct_tokens, *matched_context_tokens])),
        "matched_direct_tokens": matched_direct_tokens,
        "matched_context_tokens": matched_context_tokens,
        "exact_phrase_match": exact_phrase_match,
        "alignment_score": alignment_score,
        "has_minimum_alignment": has_minimum_alignment,
    }


def _candidate_origin(item: dict[str, Any], dom_snapshot: dict[str, Any]) -> str:
    source = str(item.get("source") or "")
    if source == SELECTOR_ORIGIN_FALLBACK or dom_snapshot.get("render_engine") == "raw_html_fallback":
        return SELECTOR_ORIGIN_FALLBACK
    if source == SELECTOR_ORIGIN_RENDERED or dom_snapshot.get("render_engine") == "playwright_multi_state":
        return SELECTOR_ORIGIN_RENDERED
    return SELECTOR_ORIGIN_REJECTED


def _candidate_evidence(
    *,
    interaction: dict[str, Any],
    item: dict[str, Any],
    selector: str,
    soups: dict[str, BeautifulSoup],
    dom_snapshot: dict[str, Any],
) -> dict[str, Any]:
    origin = _candidate_origin(item, dom_snapshot)
    selector_type = _selector_type(selector)
    match_count, observed_state = _selector_match_count(selector, soups)
    runtime_flags = _runtime_flags(selector, item, soups, observed_state)
    alignment = _candidate_alignment(interaction, item)
    generic_penalty = 90 if selector_type == "tag" else 0
    ambiguity_penalty = 25 if match_count > 1 else 0
    origin_penalty = 120 if origin == SELECTOR_ORIGIN_FALLBACK else 0
    score = (
        alignment["alignment_score"]
        + SELECTOR_TYPE_WEIGHTS.get(selector_type, 0)
        + (10 if runtime_flags["click_grounded"] else 0)
        + (15 if match_count == 1 else 0)
        - generic_penalty
        - ambiguity_penalty
        - origin_penalty
    )
    promotion_blockers: list[str] = []

    if origin != SELECTOR_ORIGIN_RENDERED:
        promotion_blockers.append("selector no proviene de DOM renderizado verificado")
    if match_count == 0:
        promotion_blockers.append("selector no existe en DOM observado")
    if match_count != 1:
        promotion_blockers.append(f"selector ambiguo ({match_count} matches)")
    if selector_type == "tag":
        promotion_blockers.append("selector genérico de tag no se autopromueve")
    if not alignment["has_minimum_alignment"]:
        promotion_blockers.append("sin evidencia mínima de alineación interacción-nodo")
    if not runtime_flags["matches_candidate_node"]:
        promotion_blockers.append("selector no apunta al nodo candidato observado")
    if not runtime_flags["closest_runtime_supported"]:
        promotion_blockers.append("selector no demuestra soporte real para event.target.closest")
    if not runtime_flags["click_grounded"]:
        promotion_blockers.append("selector no queda click_grounded")

    can_promote = not promotion_blockers

    return {
        "selector": selector,
        "selector_type": selector_type,
        "selector_origin": origin,
        "state": observed_state or item.get("state"),
        "match_count": match_count,
        "is_unique": match_count == 1,
        "uniqueness_explanation": "selector único" if match_count == 1 else f"selector con {match_count} matches",
        "outer_html_excerpt": item.get("outer_html_excerpt"),
        "visible_text": item.get("text"),
        "context_text": item.get("context_text"),
        "attributes": {
            "id": item.get("id"),
            "class_list": item.get("class_list"),
            "href": item.get("href"),
            "aria_label": item.get("aria_label"),
            "title": item.get("title"),
            "tag": item.get("tag"),
            "node_id": item.get("node_id"),
        },
        "matched_tokens": alignment["matched_tokens"],
        "matched_direct_tokens": alignment["matched_direct_tokens"],
        "matched_context_tokens": alignment["matched_context_tokens"],
        "has_minimum_alignment": alignment["has_minimum_alignment"],
        "alignment_score": alignment["alignment_score"],
        "specificity_score": SELECTOR_TYPE_WEIGHTS.get(selector_type, 0),
        "score": score,
        "exists_in_dom": runtime_flags["exists_in_dom"],
        "matches_candidate_node": runtime_flags["matches_candidate_node"],
        "closest_runtime_supported": runtime_flags["closest_runtime_supported"],
        "click_grounded": runtime_flags["click_grounded"],
        "promotion_blockers": promotion_blockers,
        "can_promote": can_promote,
    }


def _selector_trace_summary(selector_evidence: list[dict[str, Any]]) -> dict[str, Any]:
    summary = {
        "total_interactions": len(selector_evidence),
        "promoted_selectors": 0,
        "human_review_required": 0,
        "origins": {
            SELECTOR_ORIGIN_RENDERED: 0,
            SELECTOR_ORIGIN_FALLBACK: 0,
            SELECTOR_ORIGIN_REJECTED: 0,
        },
    }
    for evidence in selector_evidence:
        origin = evidence.get("selector_origin") or SELECTOR_ORIGIN_REJECTED
        summary["origins"][origin] = summary["origins"].get(origin, 0) + 1
        if evidence.get("promoted"):
            summary["promoted_selectors"] += 1
        if evidence.get("human_review_required"):
            summary["human_review_required"] += 1
    return summary


def propose_selectors(measurement_case: dict[str, Any], dom_snapshot: dict[str, Any]) -> dict[str, Any]:
    state_html = dom_snapshot.get("state_html") or {}
    soups = {state: BeautifulSoup(html, "lxml") for state, html in state_html.items()}
    inventory = [item for item in (dom_snapshot.get("clickable_inventory") or []) if item.get("is_clickable")]
    render_engine = str(dom_snapshot.get("render_engine") or "none")

    if not state_html or not inventory:
        selector_evidence = []
        for idx, interaction in enumerate(measurement_case.get("interacciones", []), start=1):
            interaction["selector_candidato"] = None
            interaction["selector_activador"] = None
            interaction["match_count"] = 0
            interaction.setdefault("warnings", []).append(
                "Sin inventario de clickables observado en DOM; selector en null y human_review_required=true."
            )
            selector_evidence.append(
                {
                    "index": idx,
                    "selector": None,
                    "selector_origin": SELECTOR_ORIGIN_REJECTED,
                    "human_review_required": True,
                    "promoted": False,
                    "rejection_reason": "no hay inventario renderizado utilizable",
                    "candidates_considered": 0,
                    "candidates": [],
                }
            )
        return {
            "status": "no_inventory",
            "measurement_case": measurement_case,
            "warnings": ["No hay inventario de clickables del DOM renderizado."],
            "clickable_inventory": inventory,
            "selector_evidence": selector_evidence,
            "selector_summary": _selector_trace_summary(selector_evidence),
            "state_metadata": dom_snapshot.get("state_metadata") or [],
        }

    selector_evidence: list[dict[str, Any]] = []

    for index, interaction in enumerate(measurement_case.get("interacciones", []), start=1):
        interaction.setdefault("warnings", [])
        traces: list[dict[str, Any]] = []

        for item in inventory:
            seen: set[str] = set()
            for selector in item.get("selector_candidates") or []:
                selector_text = str(selector)
                if selector_text in seen:
                    continue
                seen.add(selector_text)
                traces.append(
                    _candidate_evidence(
                        interaction=interaction,
                        item=item,
                        selector=selector_text,
                        soups=soups,
                        dom_snapshot=dom_snapshot,
                    )
                )

        traces = [trace for trace in traces if trace.get("exists_in_dom")]
        traces.sort(
            key=lambda trace: (
                int(bool(trace.get("can_promote"))),
                int(trace.get("alignment_score", 0)),
                int(trace.get("specificity_score", 0)),
                int(bool(trace.get("click_grounded"))),
                -int(trace.get("match_count", 0)),
            ),
            reverse=True,
        )

        chosen = traces[0] if traces else None
        if not chosen:
            interaction["selector_candidato"] = None
            interaction["selector_activador"] = None
            interaction["match_count"] = 0
            interaction["warnings"].append(
                "No se encontró selector con grounding suficiente para esta interacción; human_review_required=true."
            )
            selector_evidence.append(
                {
                    "index": index,
                    "selector": None,
                    "selector_origin": SELECTOR_ORIGIN_REJECTED,
                    "human_review_required": True,
                    "promoted": False,
                    "rejection_reason": "no hay candidatos con existencia en DOM y alineación mínima",
                    "candidates_considered": len(traces),
                    "candidates": [],
                }
            )
            continue

        promoted = bool(chosen.get("can_promote"))
        interaction["match_count"] = int(chosen.get("match_count") or 0)
        if promoted:
            selector = str(chosen["selector"])
            interaction["selector_candidato"] = selector
            interaction["selector_activador"] = f"{selector}, {selector} *"
        else:
            interaction["selector_candidato"] = None
            interaction["selector_activador"] = None

        if chosen["selector_origin"] == SELECTOR_ORIGIN_FALLBACK:
            interaction["warnings"].append(
                "Selector observado solo en raw_html_fallback: no se autopromueve y requiere revisión humana."
            )
        if not chosen.get("has_minimum_alignment", False):
            interaction["warnings"].append(
                "La evidencia textual/atributiva del nodo es insuficiente para autopromover selector."
            )
        if chosen.get("promotion_blockers"):
            interaction["warnings"].append(
                "Selector retenido por seguridad: " + "; ".join(chosen["promotion_blockers"])
            )

        selector_evidence.append(
            {
                "index": index,
                "selector": chosen.get("selector") if promoted else None,
                "selector_origin": chosen.get("selector_origin") or SELECTOR_ORIGIN_REJECTED,
                "human_review_required": (not promoted) or chosen.get("match_count") != 1,
                "promoted": promoted,
                "rejection_reason": None if promoted else "; ".join(chosen.get("promotion_blockers") or []),
                "chosen": chosen,
                "candidates_considered": len(traces),
                "candidates": traces[:10],
            }
        )

    warnings: list[str] = []
    if render_engine == "raw_html_fallback":
        warnings.append("DOM renderizado no disponible: cualquier candidato de raw_html_fallback queda degradado.")

    return {
        "status": "ok",
        "measurement_case": measurement_case,
        "warnings": warnings,
        "clickable_inventory": inventory,
        "selector_evidence": selector_evidence,
        "selector_summary": _selector_trace_summary(selector_evidence),
        "state_metadata": dom_snapshot.get("state_metadata") or [],
    }
