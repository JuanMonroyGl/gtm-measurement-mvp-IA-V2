"""GTM tag template generation."""

from __future__ import annotations

import json
from typing import Any


def _to_js(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _selector_priority(selector: str) -> int:
    if selector.startswith("#"):
        return 100
    if "[data-" in selector:
        return 80
    if "[aria-" in selector:
        return 70
    if "[href=" in selector:
        return 60
    if "." in selector:
        return 40
    return 10


def _build_selector_rules(measurement_case: dict[str, Any]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    for interaction in measurement_case.get("interacciones", []):
        interaction_mode = str(interaction.get("interaction_mode") or "single").lower()
        selector = interaction.get("selector_item") or interaction.get("selector_candidato") or interaction.get("selector_activador")
        if not selector:
            continue
        rules.append(
            {
                "mode": interaction_mode,
                "selector": str(selector),
                "container_selector": interaction.get("selector_contenedor"),
                "event_name": str(interaction.get("tipo_evento") or "Clic Boton"),
                "flujo": str(interaction.get("flujo") or ""),
                "ubicacion": str(interaction.get("ubicacion") or ""),
                "value_extraction_strategy": str(interaction.get("value_extraction_strategy") or "click_text"),
                "element_variants": list(interaction.get("element_variants") or []),
                "title_variants": list(interaction.get("title_variants") or []),
            }
        )
    rules.sort(key=lambda item: (_selector_priority(item["selector"]), len(item["selector"])), reverse=True)
    return rules


def _assert_no_conflicting_duplicate_selectors(selector_rules: list[dict[str, Any]]) -> None:
    grouped: dict[tuple[str, str, str | None], set[tuple[str, str, str]]] = {}
    for rule in selector_rules:
        key = (rule["mode"], rule["selector"], rule.get("container_selector"))
        grouped.setdefault(key, set()).add((rule["event_name"], rule["flujo"], rule["ubicacion"]))

    conflicts = {selector: payloads for selector, payloads in grouped.items() if len(payloads) > 1}
    if not conflicts:
        return

    details = []
    for selector, payloads in conflicts.items():
        payload_list = ", ".join(f"{event}/{flujo}/{ubicacion}" for event, flujo, ubicacion in sorted(payloads))
        details.append(f"{selector} -> [{payload_list}]")
    detail_text = "; ".join(details)
    raise ValueError(
        "Conflicto de selectores en generación de tag: múltiples interacciones comparten la misma "
        "regla de disparo con payload distinto, lo que produciría ramas muertas en if/else if. "
        f"Detalles: {detail_text}"
    )


def build_tag_template(measurement_case: dict[str, Any]) -> str:
    activo = str(measurement_case.get("activo") or "bancolombia")
    seccion = str(measurement_case.get("seccion") or "pagos")
    selector_rules = _build_selector_rules(measurement_case)
    _assert_no_conflicting_duplicate_selectors(selector_rules)

    lines = [
        "<script>",
        "  var element = {{Click Element}};",
        "  var getClean = {{JS - Function - Format LowerCase}};",
        "  var getClickText = {{JS - Click Text - Btn and A}};",
        "  var getTextClose = {{JS - Function - Get Text Close}};",
        "",
        f"  var eventData = {{ activo: {_to_js(activo)}, seccion: {_to_js(seccion)} }};",
        "",
        "  function resolveHelperValue(helper, node) {",
        "    var value = helper;",
        "    if (typeof value === 'function') {",
        "      try { value = value(node); } catch (err) { value = ''; }",
        "    }",
        "    return value || '';",
        "  }",
        "",
        "  function normalizeValue(value, clean) {",
        "    var result = String(value || '').replace(/\\s+/g, ' ').trim();",
        "    if (typeof clean === 'function') {",
        "      result = clean(result || '');",
        "    }",
        "    return result || '';",
        "  }",
        "",
        "  function fallbackText(node) {",
        "    if (!node) { return ''; }",
        "    return String(node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();",
        "  }",
        "",
        "  function resolveNodeText(node, clean, clickHelper, closeHelper) {",
        "    var value = resolveHelperValue(clickHelper, node);",
        "    if (!value) { value = resolveHelperValue(closeHelper, node); }",
        "    if (!value) { value = fallbackText(node); }",
        "    return normalizeValue(value, clean);",
        "  }",
        "",
        "  function matchKnownVariant(rawValue, variants, clean) {",
        "    var normalized = normalizeValue(rawValue, clean);",
        "    if (!normalized) { return ''; }",
        "    if (!variants || !variants.length) { return normalized; }",
        "    for (var i = 0; i < variants.length; i += 1) {",
        "      var candidate = normalizeValue(variants[i], clean);",
        "      if (!candidate) { continue; }",
        "      if (normalized === candidate || normalized.indexOf(candidate) !== -1 || candidate.indexOf(normalized) !== -1) {",
        "        return candidate;",
        "      }",
        "    }",
        "    return normalized;",
        "  }",
        "",
        "  function collectContextRoots(itemNode, containerNode) {",
        "    var roots = [];",
        "    var current = itemNode;",
        "    while (current && current !== document && roots.length < 6) {",
        "      roots.push(current);",
        "      if (containerNode && current === containerNode) { break; }",
        "      current = current.parentElement;",
        "    }",
        "    if (containerNode && roots.indexOf(containerNode) === -1) {",
        "      roots.push(containerNode);",
        "    }",
        "    return roots;",
        "  }",
        "",
        "  function resolveVariantFromContext(itemNode, containerNode, variants, clean) {",
        "    if (!variants || !variants.length) { return ''; }",
        "    var roots = collectContextRoots(itemNode, containerNode);",
        "    for (var i = 0; i < roots.length; i += 1) {",
        "      var text = normalizeValue(fallbackText(roots[i]), clean);",
        "      if (!text) { continue; }",
        "      for (var j = 0; j < variants.length; j += 1) {",
        "        var candidate = normalizeValue(variants[j], clean);",
        "        if (candidate && (text === candidate || text.indexOf(candidate) !== -1)) {",
        "          return candidate;",
        "        }",
        "      }",
        "    }",
        "    return '';",
        "  }",
        "",
        "  function resolveCardTitle(itemNode, containerNode, clean) {",
        "    var selectors = ['[data-card-title]', '.card-title', '.title', '.titulo', 'h1', 'h2', 'h3', 'h4', 'h5', 'strong', 'p'];",
        "    var clickedText = normalizeValue(fallbackText(itemNode), clean);",
        "    var roots = collectContextRoots(itemNode, containerNode);",
        "    for (var i = 0; i < roots.length; i += 1) {",
        "      var root = roots[i];",
        "      if (!root || !root.querySelectorAll) { continue; }",
        "      for (var j = 0; j < selectors.length; j += 1) {",
        "        var candidates = root.querySelectorAll(selectors[j]);",
        "        for (var k = 0; k < candidates.length; k += 1) {",
        "          var text = normalizeValue(fallbackText(candidates[k]), clean);",
        "          if (text && text !== clickedText && text.length > 3) {",
        "            return text;",
        "          }",
        "        }",
        "      }",
        "    }",
        "    return '';",
        "  }",
        "",
        "  function resolveGroupNode(node, itemSelector, containerSelector) {",
        "    if (!node || typeof node.closest !== 'function') { return { item: null, container: null }; }",
        "    var itemNode = node.closest(itemSelector);",
        "    if (!itemNode) { return { item: null, container: null }; }",
        "    if (!containerSelector) { return { item: itemNode, container: null }; }",
        "    var containerNode = itemNode.closest(containerSelector);",
        "    if (!containerNode) { return { item: null, container: null }; }",
        "    return { item: itemNode, container: containerNode };",
        "  }",
        "",
        "  function resolveGroupValue(rule, itemNode, containerNode, clean, clickHelper, closeHelper) {",
        "    var clickedText = resolveNodeText(itemNode, clean, clickHelper, closeHelper);",
        "    var normalizedElement = matchKnownVariant(clickedText, rule.element_variants || [], clean);",
        "    var titleFromVariants = resolveVariantFromContext(itemNode, containerNode, rule.title_variants || [], clean);",
        "    var titleFromDom = resolveCardTitle(itemNode, containerNode, clean);",
        "    var titleValue = titleFromVariants || titleFromDom;",
        "    var elemento = normalizedElement || clickedText;",
        "    if (rule.value_extraction_strategy === 'prefer_title_variant_then_click_text' && titleValue) {",
        "      elemento = titleValue;",
        "    }",
        "    return {",
        "      elemento: elemento || clickedText,",
        "      titulo_card: titleValue || ''",
        "    };",
        "  }",
        "",
        "  function setDataEvent(data, e, clean, clickHelper, closeHelper) {",
    ]

    for idx, rule in enumerate(selector_rules):
        prefix = "if" if idx == 0 else "else if"
        if rule["mode"] == "group":
            lines.extend(
                [
                    f"    {prefix}(resolveGroupNode(e, {_to_js(rule['selector'])}, {_to_js(rule.get('container_selector'))}).item) {{",
                    f"      var groupRule = {_to_js(rule)};",
                    "      var groupMatch = resolveGroupNode(e, groupRule.selector, groupRule.container_selector);",
                    "      var groupValue = resolveGroupValue(groupRule, groupMatch.item, groupMatch.container, clean, clickHelper, closeHelper);",
                    "      data['elemento'] = groupValue.elemento;",
                    "      if (groupValue.titulo_card) {",
                    "        data['titulo_card'] = groupValue.titulo_card;",
                    "      } else if (data['titulo_card']) {",
                    "        delete data['titulo_card'];",
                    "      }",
                    f"      data['flujo'] = {_to_js(rule['flujo'])};",
                    f"      data['ubicacion'] = {_to_js(rule['ubicacion'])};",
                    "",
                    f"      if (document.location.href.search('appspot.com') == -1) {{analytics.track({_to_js(rule['event_name'])}, data)}};",
                    "      return;",
                    "    }",
                ]
            )
            continue

        lines.extend(
            [
                f"    {prefix}(e.closest({_to_js(rule['selector'])})) {{",
                f"      var matchedNode = e.closest({_to_js(rule['selector'])});",
                "      data['elemento'] = resolveNodeText(matchedNode, clean, clickHelper, closeHelper);",
                "      if (data['titulo_card']) { delete data['titulo_card']; }",
                f"      data['flujo'] = {_to_js(rule['flujo'])};",
                f"      data['ubicacion'] = {_to_js(rule['ubicacion'])};",
                "",
                f"      if (document.location.href.search('appspot.com') == -1) {{analytics.track({_to_js(rule['event_name'])}, data)}};",
                "      return;",
                "    }",
            ]
        )

    if not selector_rules:
        lines.append("    // No interaction rules available for this case.")

    lines.extend(
        [
            "  }",
            "",
            "  setDataEvent(eventData, element, getClean, getClickText, getTextClose);",
            "</script>",
            "",
        ]
    )

    return "\n".join(lines)
