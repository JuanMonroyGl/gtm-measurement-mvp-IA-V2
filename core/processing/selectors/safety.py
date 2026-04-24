"""Safety rules for selector promotion and output generation."""

from __future__ import annotations

import re
from typing import Any

BROAD_TAG_SELECTORS = {
    "*",
    "a",
    "body",
    "button",
    "div",
    "div a",
    "div div",
    "main",
    "section",
}

GROUP_ITEM_MATCH_HARD_LIMIT = 50
GROUP_CONTAINER_MATCH_HARD_LIMIT = 12


def _normalize_selector(selector: str | None) -> str:
    return re.sub(r"\s+", " ", str(selector or "").strip()).lower()


def _href_value(selector: str) -> str | None:
    match = re.search(r"\[href(?:[*^$|~]?=)([\"']?)(.*?)\1\]", selector, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(2).strip().lower()


def has_stable_discriminator(selector: str | None) -> bool:
    clean = _normalize_selector(selector)
    if not clean:
        return False
    if "#" in clean or "." in clean:
        return True
    if any(token in clean for token in ("[data-", "[aria-", "[role=")):
        return True
    href = _href_value(clean)
    if href is None:
        return False
    if href in {"", "#", "javascript:", "javascript:;", "/"}:
        return False
    return len(href) >= 4


def _last_compound_selector(selector: str | None) -> str:
    clean = _normalize_selector(selector)
    parts = [part for part in re.split(r"\s+|>|~|\+", clean) if part]
    return parts[-1] if parts else ""


def is_tag_only_selector(selector: str | None) -> bool:
    clean = _normalize_selector(selector)
    if not clean:
        return True
    if any(char in clean for char in "#.[]:"):
        return False
    parts = [part for part in re.split(r"\s+|>|~|\+", clean) if part]
    if not parts:
        return True
    return all(re.fullmatch(r"[a-z][a-z0-9-]*|\*", part) for part in parts)


def is_unsafe_group_selector(selector: str | None) -> bool:
    clean = _normalize_selector(selector)
    if not clean:
        return True
    if clean in BROAD_TAG_SELECTORS:
        return True
    if is_tag_only_selector(clean):
        return True
    if not has_stable_discriminator(_last_compound_selector(clean)):
        return True
    return not has_stable_discriminator(clean)


def selector_safety_blockers(selector: str | None, *, role: str) -> list[str]:
    clean = _normalize_selector(selector)
    if not clean:
        return [f"selector_{role} ausente"]
    blockers: list[str] = []
    if clean in BROAD_TAG_SELECTORS:
        blockers.append(f"selector_{role} genérico bloqueado: {clean}")
    if is_tag_only_selector(clean):
        blockers.append(f"selector_{role} compuesto solo por tags HTML: {clean}")
    if not has_stable_discriminator(_last_compound_selector(clean)):
        blockers.append(f"selector_{role} con nodo clickeable no discriminante: {clean}")
    if not has_stable_discriminator(clean):
        blockers.append(f"selector_{role} sin discriminador estable: {clean}")
    return list(dict.fromkeys(blockers))


def group_match_limit(expected_variants: int | None = None, candidate_count: int | None = None) -> int:
    expected = max(int(expected_variants or 0), int(candidate_count or 0), 1)
    return min(GROUP_ITEM_MATCH_HARD_LIMIT, max(12, expected * 3))


def container_match_limit() -> int:
    return GROUP_CONTAINER_MATCH_HARD_LIMIT


def useful_visible_text(values: Any) -> bool:
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        return False
    for value in values:
        normalized = re.sub(r"\s+", " ", str(value or "").strip())
        if len(normalized) >= 3:
            return True
    return False
