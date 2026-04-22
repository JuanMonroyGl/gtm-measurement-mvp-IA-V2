"""GTM tag template generation."""

from __future__ import annotations

from typing import Any


def _escape_js(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _build_selector_rules(measurement_case: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    rules: list[tuple[str, str, str, str]] = []
    for interaction in measurement_case.get("interacciones", []):
        selector = interaction.get("selector_candidato") or interaction.get("selector_activador")
        if not selector:
            continue
        rules.append(
            (
                str(selector),
                str(interaction.get("tipo_evento") or "Clic Boton"),
                str(interaction.get("flujo") or ""),
                str(interaction.get("ubicacion") or ""),
            )
        )
    return rules


def _assert_no_conflicting_duplicate_selectors(selector_rules: list[tuple[str, str, str, str]]) -> None:
    grouped: dict[str, set[tuple[str, str, str]]] = {}
    for selector, event_name, flujo, ubicacion in selector_rules:
        grouped.setdefault(selector, set()).add((event_name, flujo, ubicacion))

    conflicts = {selector: payloads for selector, payloads in grouped.items() if len(payloads) > 1}
    if not conflicts:
        return

    details = []
    for selector, payloads in conflicts.items():
        payload_list = ", ".join(f"{event}/{flujo}/{ubicacion}" for event, flujo, ubicacion in sorted(payloads))
        details.append(f"{selector} -> [{payload_list}]")
    detail_text = "; ".join(details)
    raise ValueError(
        "Conflicto de selectores en generación de tag: múltiples interacciones comparten el mismo selector "
        "con payload distinto, lo que produciría ramas muertas en if/else if. "
        f"Detalles: {detail_text}"
    )


def build_tag_template(measurement_case: dict[str, Any]) -> str:
    activo = _escape_js(str(measurement_case.get("activo") or "bancolombia"))
    seccion = _escape_js(str(measurement_case.get("seccion") or "pagos"))

    lines = [
        "<script>",
        "  var element = {{Click Element}};",
        "  var getClean = {{JS - Function - Format LowerCase}};",
        "  var getClickText = {{JS - Click Text - Btn and A}};",
        "  var getTextClose = {{JS - Function - Get Text Close}};",
        "",
        f"  var eventData = {{ activo: \"{activo}\", seccion: \"{seccion}\" }}",
        "",
        "  function setDataEvent(data, e, cText, clean, getText) {",
        "    var value = cText;",
        "    if (typeof value === 'function') { value = value(e); }",
        "    if (!value) {",
        "      value = (typeof getText === 'function') ? getText(e) : getText;",
        "    }",
        "    value = (typeof clean === 'function') ? clean(value || '') : (value || '');",
    ]

    selector_rules = _build_selector_rules(measurement_case)
    _assert_no_conflicting_duplicate_selectors(selector_rules)

    for idx, (selector, event_name, flujo, ubicacion) in enumerate(selector_rules):
        prefix = "if" if idx == 0 else "else if"
        lines.extend(
            [
                f"    {prefix}(e.closest('{selector}')) {{",
                "        data['elemento'] = value;",
                f"        data['flujo'] = \"{_escape_js(flujo)}\";",
                f"        data['ubicacion'] = \"{_escape_js(ubicacion)}\";",
                "",
                f"        if (document.location.href.search('appspot.com') == -1) {{analytics.track('{_escape_js(event_name)}', data)}};",
                "        return;",
                "    }",
            ]
        )

    if not selector_rules:
        lines.extend(
            [
                "    // No interaction rules available for this case.",
            ]
        )

    lines.extend(
        [
            "  }",
            "",
            "  setDataEvent(eventData, element, getClickText, getClean, getTextClose);",
            "</script>",
            "",
        ]
    )

    return "\n".join(lines)
