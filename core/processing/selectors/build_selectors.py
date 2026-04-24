"""Selector proposal logic with strict grounding and explicit provenance."""

from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup
from bs4.element import Tag

from core.processing.selectors.safety import (
    container_match_limit,
    group_match_limit,
    is_unsafe_group_selector,
    selector_safety_blockers,
    useful_visible_text,
)

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
STATEFUL_CLASS_TOKENS = (
    "active",
    "current",
    "selected",
    "open",
    "show",
    "next",
    "prev",
)


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
        "Ã¡": "a",
        "Ã©": "e",
        "Ã­": "i",
        "Ã³": "o",
        "Ãº": "u",
        "Ã¼": "u",
        "Ã±": "n",
        "Â¿": "",
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


def _normalized_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]


def _interaction_tokens(interaction: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    for field in ("texto_referencia", "elemento", "ubicacion", "flujo", "tipo_evento", "group_context", "zone_hint"):
        tokens.extend(_tokenize(interaction.get(field)))
    for value in _normalized_list(interaction.get("element_variants")):
        tokens.extend(_tokenize(value))
    for value in _normalized_list(interaction.get("title_variants")):
        tokens.extend(_tokenize(value))
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


def _expected_group_variants(interaction: dict[str, Any]) -> list[str]:
    return list(
        dict.fromkeys(
            [
                *_normalized_list(interaction.get("element_variants")),
                *_normalized_list(interaction.get("title_variants")),
            ]
        )
    )


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


def _stable_classes(classes: list[str] | None) -> list[str]:
    stable: list[str] = []
    for value in classes or []:
        if not value or len(value) <= 2:
            continue
        normalized = value.lower()
        if any(token in normalized for token in STATEFUL_CLASS_TOKENS):
            continue
        stable.append(value)
    return stable


def _item_direct_haystack(item: dict[str, Any]) -> str:
    return _normalize(
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


def _item_context_haystack(item: dict[str, Any]) -> str:
    return _normalize(
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


def _variant_matches(variants: list[str], direct_haystack: str, context_haystack: str) -> tuple[list[str], list[str]]:
    direct_matches: list[str] = []
    context_matches: list[str] = []
    for variant in variants:
        normalized = _normalize(variant)
        if not normalized:
            continue
        if normalized in direct_haystack:
            direct_matches.append(variant)
        elif normalized in context_haystack:
            context_matches.append(variant)
    return direct_matches, context_matches


def _zone_alignment_score(interaction: dict[str, Any], item: dict[str, Any]) -> int:
    zone_hint = _normalize(interaction.get("zone_hint"))
    group_context = _normalize(interaction.get("group_context"))
    haystack = _item_context_haystack(item)
    score = 0

    if zone_hint == "header-menu" and ("header-menu" in haystack or "menu-" in haystack):
        score += 4
    if zone_hint == "shortcut-tabs" and ("desktop-submenu" in haystack or "submenu" in haystack):
        score += 4
    if zone_hint == "faq-list" and ("lista-preguntas" in haystack or "preguntas-frecuentes" in haystack):
        score += 4
    if zone_hint == "card-grid" and any(token in haystack for token in ("card-footer", "btn-products", "swiper", " card ")):
        score += 4

    if group_context == "card_collection" and any(token in haystack for token in ("card", "swiper", "btn-products")):
        score += 2
    if group_context == "faq_collection" and any(token in haystack for token in ("preguntas", "faq")):
        score += 2
    if group_context == "top_navigation" and "header-menu" in haystack:
        score += 2
    if group_context == "shortcut_collection" and "submenu" in haystack:
        score += 2

    for token in _tokenize(interaction.get("ubicacion")):
        if token and token in haystack:
            score += 1

    return score


def _group_item_alignment(interaction: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    direct_haystack = _item_direct_haystack(item)
    context_haystack = _item_context_haystack(item)
    element_variants = _normalized_list(interaction.get("element_variants"))
    title_variants = _normalized_list(interaction.get("title_variants"))
    matched_element_direct, matched_element_context = _variant_matches(element_variants, direct_haystack, context_haystack)
    matched_title_direct, matched_title_context = _variant_matches(title_variants, direct_haystack, context_haystack)
    zone_score = _zone_alignment_score(interaction, item)

    matched_variants = list(
        dict.fromkeys(
            [*matched_element_direct, *matched_element_context, *matched_title_direct, *matched_title_context]
        )
    )
    score = (
        len(matched_element_direct) * 45
        + len(matched_element_context) * 20
        + len(matched_title_direct) * 30
        + len(matched_title_context) * 15
        + zone_score * 12
        + (5 if item.get("is_visible") else 0)
    )
    qualifies = bool(matched_variants)

    return {
        "matched_variants": matched_variants,
        "matched_element_direct": matched_element_direct,
        "matched_element_context": matched_element_context,
        "matched_title_direct": matched_title_direct,
        "matched_title_context": matched_title_context,
        "zone_score": zone_score,
        "score": score,
        "qualifies": qualifies,
    }


def _item_role(item: dict[str, Any]) -> str:
    outer_html = str(item.get("outer_html_excerpt") or "")
    match = re.search(r"\brole=[\"']([^\"']+)[\"']", outer_html, flags=re.IGNORECASE)
    return _normalize(match.group(1)) if match else ""


def _allowed_group_click_target(interaction: dict[str, Any], item: dict[str, Any]) -> bool:
    tag = str(item.get("tag") or "").strip().lower()
    role = _item_role(item)
    group_context = _normalize(interaction.get("group_context"))
    if group_context in {"top_navigation", "menu"}:
        return tag in {"a", "button"}
    if group_context == "shortcut_collection":
        return tag in {"a", "button"} or role == "tab"
    if group_context == "faq_collection":
        return tag == "a"
    if group_context == "card_collection":
        return tag in {"a", "button"}
    return tag in {"a", "button"} or role in {"button", "tab"}


def _alignment_allowed_for_group_context(interaction: dict[str, Any], item: dict[str, Any], alignment: dict[str, Any]) -> bool:
    group_context = _normalize(interaction.get("group_context"))
    if group_context in {"top_navigation", "menu", "shortcut_collection"}:
        return bool(alignment.get("matched_element_direct"))
    if group_context == "faq_collection":
        return bool(alignment.get("matched_element_direct")) and "/preguntas-frecuentes" in str(item.get("href") or "")
    if group_context == "card_collection":
        return bool(
            alignment.get("matched_element_direct")
            or alignment.get("matched_title_direct")
            or alignment.get("matched_title_context")
        )
    return bool(alignment.get("matched_variants"))


def _minimum_group_variant_coverage(interaction: dict[str, Any]) -> int:
    group_context = _normalize(interaction.get("group_context"))
    variants = _expected_group_variants(interaction)
    if not variants:
        return 1
    if group_context in {"top_navigation", "menu"}:
        return min(2, len(_normalized_list(interaction.get("element_variants"))) or len(variants))
    if group_context == "shortcut_collection":
        return min(2, len(_normalized_list(interaction.get("element_variants"))) or len(variants))
    if group_context == "faq_collection":
        return min(2, len(_normalized_list(interaction.get("element_variants"))) or len(variants))
    if group_context == "card_collection":
        return 1
    return 1


def _href_group_selector(interaction: dict[str, Any], items: list[dict[str, Any]]) -> str | None:
    tag_values = {str(item.get("tag") or "").strip().lower() for item in items}
    if tag_values != {"a"}:
        return None
    hrefs = [str(item.get("href") or "").strip() for item in items if str(item.get("href") or "").strip()]
    if len(hrefs) < 2:
        return None

    group_context = _normalize(interaction.get("group_context"))
    if group_context == "faq_collection" and all("/centro-de-ayuda/preguntas-frecuentes/" in href for href in hrefs):
        return 'a[href*="/centro-de-ayuda/preguntas-frecuentes/"]'

    common_prefix = hrefs[0]
    for href in hrefs[1:]:
        while common_prefix and not href.startswith(common_prefix):
            common_prefix = common_prefix[:-1]
    common_prefix = common_prefix.rstrip("-_/")
    if len(common_prefix) >= 16 and common_prefix not in {"/personas", "https://www.bancolombia.com"}:
        return f'a[href^="{common_prefix}"]'
    return None


def _dedupe_items_by_node_id(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for item in items:
        node_id = str(item.get("node_id") or "")
        if not node_id:
            continue
        current = unique.get(node_id)
        if current is None:
            unique[node_id] = item
            continue
        current_visible = bool(current.get("is_visible"))
        next_visible = bool(item.get("is_visible"))
        if next_visible and not current_visible:
            unique[node_id] = item
    return list(unique.values())


def _ancestor_selector_candidates(item: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for depth, ancestor in enumerate(item.get("ancestors") or [], start=1):
        tag = str(ancestor.get("tag") or "").strip().lower()
        if not tag:
            continue
        selector_options: list[tuple[str, int]] = []
        ancestor_id = ancestor.get("id")
        if ancestor_id:
            selector_options.append((f"#{ancestor_id}", 100))
        stable_classes = _stable_classes(ancestor.get("classes") or [])
        if stable_classes:
            selector_options.append((f"{tag}.{stable_classes[0]}", 35))
            if len(stable_classes) > 1:
                selector_options.append((f"{tag}.{stable_classes[0]}.{stable_classes[1]}", 45))

        for selector, specificity in selector_options:
            if selector in seen:
                continue
            seen.add(selector)
            candidates.append(
                {
                    "selector": selector,
                    "depth": depth,
                    "specificity_score": specificity,
                }
            )
    return candidates


def _common_ancestor_selectors(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidate_maps = []
    for item in items:
        item_map = {candidate["selector"]: candidate for candidate in _ancestor_selector_candidates(item)}
        if item_map:
            candidate_maps.append(item_map)
    if not candidate_maps:
        return []

    common = set(candidate_maps[0].keys())
    for item_map in candidate_maps[1:]:
        common &= set(item_map.keys())

    results: list[dict[str, Any]] = []
    for selector in common:
        specificity_score = max(item_map[selector]["specificity_score"] for item_map in candidate_maps)
        depth = min(item_map[selector]["depth"] for item_map in candidate_maps)
        results.append(
            {
                "selector": selector,
                "depth": depth,
                "specificity_score": specificity_score,
            }
        )
    return results


def _group_item_selector_candidates(
    container_selector: str,
    items: list[dict[str, Any]],
    interaction: dict[str, Any],
) -> list[str]:
    tags = {str(item.get("tag") or "").strip().lower() for item in items if item.get("tag")}
    tag = next(iter(tags), "")
    if not tag:
        return []

    class_sets = []
    for item in items:
        stable_classes = set(_stable_classes(item.get("class_list") or []))
        class_sets.append(stable_classes)
    common_classes = set.intersection(*class_sets) if class_sets else set()

    selectors: list[str] = []
    href_selector = _href_group_selector(interaction, items)
    if href_selector:
        selectors.append(f"{container_selector} {href_selector}")

    common_selector_candidates: set[str] | None = None
    for item in items:
        item_selectors = {str(selector).strip() for selector in (item.get("selector_candidates") or []) if selector}
        common_selector_candidates = item_selectors if common_selector_candidates is None else common_selector_candidates & item_selectors
    for selector in sorted(common_selector_candidates or []):
        if is_unsafe_group_selector(selector):
            continue
        selectors.append(f"{container_selector} {selector}")

    ordered_common = sorted(common_classes)
    if ordered_common:
        selectors.append(f"{container_selector} {tag}.{ordered_common[0]}")
        if len(ordered_common) > 1:
            selectors.append(f"{container_selector} {tag}.{ordered_common[0]}.{ordered_common[1]}")

    unique: list[str] = []
    seen: set[str] = set()
    for selector in selectors:
        if is_unsafe_group_selector(selector):
            continue
        if selector in seen:
            continue
        seen.add(selector)
        unique.append(selector)
    return unique


def _group_origin(items: list[dict[str, Any]], dom_snapshot: dict[str, Any]) -> str:
    origins = {_candidate_origin(item, dom_snapshot) for item in items}
    if origins == {SELECTOR_ORIGIN_RENDERED}:
        return SELECTOR_ORIGIN_RENDERED
    if SELECTOR_ORIGIN_FALLBACK in origins:
        return SELECTOR_ORIGIN_FALLBACK
    return SELECTOR_ORIGIN_REJECTED


def _group_candidate_evidence(
    *,
    interaction: dict[str, Any],
    matched_items: list[dict[str, Any]],
    container_selector: str,
    item_selector: str,
    soups: dict[str, BeautifulSoup],
    dom_snapshot: dict[str, Any],
) -> dict[str, Any]:
    unique_items = _dedupe_items_by_node_id(matched_items)
    origin = _group_origin(unique_items, dom_snapshot)
    item_selector_type = _selector_type(item_selector)
    container_match_count, container_state = _selector_match_count(container_selector, soups)
    item_match_count, item_state = _selector_match_count(item_selector, soups)
    observed_state = item_state or container_state
    soup = soups.get(observed_state) if observed_state else None

    item_matches: list[Tag] = []
    container_matches: list[Tag] = []
    if soup is not None:
        try:
            item_matches = soup.select(item_selector)
        except Exception:
            item_matches = []
        try:
            container_matches = soup.select(container_selector)
        except Exception:
            container_matches = []

    matched_node_ids = {
        str(match.get(NODE_ID_ATTR))
        for match in item_matches
        if isinstance(match, Tag) and match.get(NODE_ID_ATTR)
    }
    covered_items = [item for item in unique_items if str(item.get("node_id")) in matched_node_ids]
    matched_variants = list(
        dict.fromkeys(
            variant
            for item in covered_items
            for variant in (item.get("__group_alignment__") or {}).get("matched_variants", [])
        )
    )
    average_zone_score = round(
        (
            sum(int((item.get("__group_alignment__") or {}).get("zone_score") or 0) for item in unique_items)
            / len(unique_items)
        ),
        2,
    ) if unique_items else 0.0

    expected_variants = _expected_group_variants(interaction)
    minimum_variant_coverage = _minimum_group_variant_coverage(interaction)
    item_match_limit = group_match_limit(len(expected_variants), len(unique_items))
    group_context = _normalize(interaction.get("group_context"))
    promotion_blockers: list[str] = []
    promotion_blockers.extend(selector_safety_blockers(item_selector, role="item"))
    promotion_blockers.extend(selector_safety_blockers(container_selector, role="contenedor"))
    if origin != SELECTOR_ORIGIN_RENDERED:
        promotion_blockers.append("grupo no proviene de DOM renderizado verificado")
    if container_match_count == 0:
        promotion_blockers.append("selector de contenedor no existe en DOM observado")
    if container_match_count > container_match_limit():
        promotion_blockers.append(f"container_match_count excesivo ({container_match_count})")
    if item_match_count == 0:
        promotion_blockers.append("selector de item no existe en DOM observado")
    if item_match_count > item_match_limit:
        promotion_blockers.append(f"match_count global excesivo para grupo ({item_match_count})")
    if item_match_count < 2:
        promotion_blockers.append("selector de item colapsa el grupo a menos de 2 matches")
    if len(covered_items) < 2:
        promotion_blockers.append("selector de item no cubre suficientes nodos candidatos del grupo")
    if not covered_items:
        promotion_blockers.append("selector de item no demuestra soporte real para event.target.closest")
    if len(matched_variants) < minimum_variant_coverage:
        promotion_blockers.append(
            f"variant_coverage insuficiente ({len(matched_variants)} < {minimum_variant_coverage})"
        )
    if not useful_visible_text([item.get("text") for item in covered_items]):
        promotion_blockers.append("visible_text vacío o sin señales útiles")
    outside_matches = max(0, item_match_count - len(covered_items))
    if outside_matches > max(2, len(covered_items)):
        promotion_blockers.append(
            f"selector_item cubre nodos fuera del bloque esperado ({outside_matches} matches externos)"
        )
    if group_context == "faq_collection" and "href" not in item_selector.lower():
        promotion_blockers.append("faq_collection requiere selector_item con href discriminante")
    title_variants = set(_normalized_list(interaction.get("title_variants")))
    if group_context == "card_collection" and title_variants and not (set(matched_variants) & title_variants):
        promotion_blockers.append("card_collection sin título de card resuelto con confianza")

    can_promote = not promotion_blockers
    score = (
        len(matched_variants) * 60
        + len(covered_items) * 25
        + SELECTOR_TYPE_WEIGHTS.get(_selector_type(container_selector), 0)
        + SELECTOR_TYPE_WEIGHTS.get(item_selector_type, 0)
        + int(average_zone_score * 10)
        + (10 if container_match_count >= 1 else 0)
    )

    return {
        "selector": item_selector,
        "selector_type": item_selector_type,
        "selector_origin": origin,
        "state": observed_state,
        "match_count": item_match_count,
        "container_match_count": container_match_count,
        "selector_contenedor": container_selector,
        "selector_item": item_selector,
        "group_item_count": len(covered_items),
        "candidate_group_item_count": len(unique_items),
        "matched_variants": matched_variants,
        "variant_coverage": len(matched_variants),
        "minimum_variant_coverage": minimum_variant_coverage,
        "group_match_limit": item_match_limit,
        "outside_match_count": outside_matches,
        "average_zone_score": average_zone_score,
        "visible_text": [item.get("text") for item in covered_items[:5]],
        "context_text": [item.get("context_text") for item in covered_items[:3]],
        "attributes": {
            "tag": next((item.get("tag") for item in covered_items if item.get("tag")), None),
            "node_ids": [item.get("node_id") for item in covered_items[:10]],
        },
        "alignment_score": len(matched_variants) * 50 + int(average_zone_score * 10),
        "specificity_score": SELECTOR_TYPE_WEIGHTS.get(item_selector_type, 0),
        "score": score,
        "exists_in_dom": bool(item_matches),
        "matches_candidate_node": len(covered_items) >= 2,
        "closest_runtime_supported": len(covered_items) >= 2,
        "click_grounded": len(covered_items) >= 2 and origin == SELECTOR_ORIGIN_RENDERED,
        "promotion_blockers": promotion_blockers,
        "can_promote": can_promote,
        "outer_html_excerpt": [item.get("outer_html_excerpt") for item in covered_items[:3]],
        "uniqueness_explanation": (
            f"selector grupal con {item_match_count} matches"
            if item_match_count
            else "selector grupal sin matches"
        ),
    }


def _select_single_interaction(
    *,
    interaction: dict[str, Any],
    inventory: list[dict[str, Any]],
    soups: dict[str, BeautifulSoup],
    dom_snapshot: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
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
    return (traces[0] if traces else None), traces


def _select_group_interaction(
    *,
    interaction: dict[str, Any],
    inventory: list[dict[str, Any]],
    soups: dict[str, BeautifulSoup],
    dom_snapshot: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    aligned_items: list[dict[str, Any]] = []
    for item in inventory:
        if not _allowed_group_click_target(interaction, item):
            continue
        alignment = _group_item_alignment(interaction, item)
        if not alignment["qualifies"]:
            continue
        if not _alignment_allowed_for_group_context(interaction, item, alignment):
            continue
        enriched = dict(item)
        enriched["__group_alignment__"] = alignment
        aligned_items.append(enriched)

    unique_items = _dedupe_items_by_node_id(aligned_items)
    if len(unique_items) < 2:
        return None, []

    ancestor_candidates = _common_ancestor_selectors(unique_items)
    traces: list[dict[str, Any]] = []
    for ancestor in ancestor_candidates:
        container_selector = ancestor["selector"]
        if is_unsafe_group_selector(container_selector):
            continue
        for item_selector in _group_item_selector_candidates(container_selector, unique_items, interaction):
            traces.append(
                _group_candidate_evidence(
                    interaction=interaction,
                    matched_items=unique_items,
                    container_selector=container_selector,
                    item_selector=item_selector,
                    soups=soups,
                    dom_snapshot=dom_snapshot,
                )
            )

    traces.sort(
        key=lambda trace: (
            int(bool(trace.get("can_promote"))),
            int(trace.get("variant_coverage", 0)),
            int(trace.get("group_item_count", 0)),
            int(trace.get("specificity_score", 0)),
            int(trace.get("score", 0)),
        ),
        reverse=True,
    )
    return (traces[0] if traces else None), traces


def propose_selectors(measurement_case: dict[str, Any], dom_snapshot: dict[str, Any]) -> dict[str, Any]:
    state_html = dom_snapshot.get("state_html") or {}
    soups = {state: BeautifulSoup(html, "lxml") for state, html in state_html.items()}
    inventory = [item for item in (dom_snapshot.get("clickable_inventory") or []) if item.get("is_clickable")]
    render_engine = str(dom_snapshot.get("render_engine") or "none")

    if not state_html or not inventory:
        selector_evidence = []
        for idx, interaction in enumerate(measurement_case.get("interacciones", []), start=1):
            interaction["selector_candidato"] = None
            interaction["selector_contenedor"] = None
            interaction["selector_item"] = None
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
        interaction_mode = str(interaction.get("interaction_mode") or "single").lower()

        if interaction_mode == "group":
            chosen, traces = _select_group_interaction(
                interaction=interaction,
                inventory=inventory,
                soups=soups,
                dom_snapshot=dom_snapshot,
            )
        else:
            chosen, traces = _select_single_interaction(
                interaction=interaction,
                inventory=inventory,
                soups=soups,
                dom_snapshot=dom_snapshot,
            )

        if not chosen:
            interaction["selector_candidato"] = None
            interaction["selector_contenedor"] = None
            interaction["selector_item"] = None
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
                    "rejection_reason": "no hay candidatos con existencia en DOM y alineación suficiente",
                    "candidates_considered": len(traces),
                    "candidates": traces[:10],
                }
            )
            if interaction_mode == "group":
                interaction["warnings"].append(
                    "No se encontro selector grupal seguro variant-first; se rechazan selectores genericos, contenedores no discriminantes, variant_coverage insuficiente o match_count excesivo; human_review_required=true."
                )
            continue

        promoted = bool(chosen.get("can_promote"))
        interaction["match_count"] = int(chosen.get("match_count") or 0)
        if promoted:
            selector = str(chosen["selector"])
            interaction["selector_candidato"] = selector
            interaction["selector_contenedor"] = chosen.get("selector_contenedor")
            interaction["selector_item"] = chosen.get("selector_item") or selector
            interaction["selector_activador"] = f"{selector}, {selector} *"
        else:
            interaction["selector_candidato"] = None
            interaction["selector_contenedor"] = None
            interaction["selector_item"] = None
            interaction["selector_activador"] = None

        if chosen["selector_origin"] == SELECTOR_ORIGIN_FALLBACK:
            interaction["warnings"].append(
                "Selector observado solo en raw_html_fallback: no se autopromueve y requiere revisión humana."
            )
        if not chosen.get("has_minimum_alignment", True) and interaction_mode != "group":
            interaction["warnings"].append(
                "La evidencia textual/atributiva del nodo es insuficiente para autopromover selector."
            )
        if chosen.get("promotion_blockers"):
            interaction["warnings"].append(
                "Selector retenido por seguridad: " + "; ".join(chosen["promotion_blockers"])
            )
        if interaction_mode == "group" and promoted:
            interaction["warnings"].append(
                f"Interacción grupal modelada con selector_contenedor={chosen.get('selector_contenedor')} y selector_item={chosen.get('selector_item')}."
            )

        selector_evidence.append(
            {
                "index": index,
                "selector": chosen.get("selector") if promoted else None,
                "selector_origin": chosen.get("selector_origin") or SELECTOR_ORIGIN_REJECTED,
                "human_review_required": (not promoted) or (
                    interaction_mode == "single" and chosen.get("match_count") != 1
                ),
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
