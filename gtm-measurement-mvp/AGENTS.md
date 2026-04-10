# AGENTS.md

## Objetivo
Construir un MVP que convierta imágenes de planes de medición de Bancolombia en:
1. JSON normalizado del caso
2. propuesta de selectores CSS
3. código de etiqueta GTM
4. selector consolidado del activador
5. reporte de supuestos, validaciones y alertas

## Alcance actual
- Entrada principal: imágenes PNG/JPG en `inputs/<case_id>/images/`
- Entrada adicional: `inputs/<case_id>/metadata.json`
- No publicar en GTM
- No hacer cambios automáticos externos
- No asumir que el selector propuesto es correcto sin validarlo contra el DOM
- La salida es una propuesta técnica lista para revisión humana, no un entregable final de producción

## Convenciones
- Lenguaje principal: Python
- Mantener módulos pequeños y claros
- No hardcodear Apple Pay ni casos específicos
- Soportar tipos de evento:
  - Clic Boton
  - Clic Card
  - Clic Link
  - Clic Tap
- Salidas en `outputs/<case_id>/`

## JSON objetivo
Cada interacción debe incluir:
- tipo_evento
- activo
- seccion
- flujo
- elemento
- ubicacion
- plan_url
- target_url
- page_path_regex
- texto_referencia
- selector_candidato
- selector_activador
- match_count
- confidence
- warnings

## Reglas de extracción
- No inventar valores faltantes.
- Si un campo no puede inferirse con suficiente confianza, usar `null` y registrarlo en `report.md`.
- Si existe conflicto entre imágenes y metadata, priorizar la metadata y reportar el conflicto.
- Conservar evidencia textual útil extraída de las imágenes cuando ayude a justificar una interacción.

## Reglas de URL
- El material de entrada puede contener una URL distinta a la real de ejecución.
- `plan_url` es la URL que aparece en imágenes o documentos del plan.
- `target_url` es la URL real que debe usar el agente para scraping y validación.
- Si existen ambas y no coinciden, usar `target_url` como fuente principal.
- Conservar `plan_url` en el JSON de salida como referencia.
- Derivar `page_path_regex` desde `target_url` cuando esté disponible.
- No fallar si las imágenes contienen una URL QA, placeholder o desactualizada.

## Reglas de selectores
- Priorizar selectores estables y legibles.
- Preferir, en este orden:
  1. `id`
  2. atributos `data-*`
  3. atributos `aria-*`
  4. clases estables
- Evitar selectores excesivamente largos, frágiles o dependientes de estructura profunda del DOM.
- Validar cuántos matches devuelve cada selector.
- Si hay múltiples matches ambiguos, reportarlo en `report.md`.

## Reglas de generación GTM
- Generar una sola etiqueta por caso, con if / else if por interacción
- Usar `e.closest(...)`
- Generar un selector consolidado para el activador incluyendo `selector` y `selector *`
- Mantener separados:
  - parsing del plan
  - scraping/render del DOM
  - construcción de selectores
  - generación de JS
- Patrón GTM estándar del proyecto: `eventData` + `setDataEvent(...)` + guard `document.location.href.search('appspot.com') == -1` antes de `analytics.track(...)`.

- En GTM, las variables de helper (click text / text close / clean) pueden llegar como función o como valor ya resuelto; el generador debe soportar ambos casos.

## Reglas de entrada del caso
- Las imágenes del plan estarán en `inputs/<case_id>/images/`
- La metadata del caso estará en `inputs/<case_id>/metadata.json`
- El parser debe construir el caso aunque algunas imágenes no incluyan URL legible
- Si falta información en las imágenes, completar desde `metadata.json` y reportarlo en `report.md`

## Convención de benchmark manual por caso
- Para casos con implementación manual previa, usar `examples/case_XXX_expected_tag.js`, `examples/case_XXX_expected_trigger.txt` y `examples/case_XXX_notes.md` como benchmark de comparación.
- Estos archivos son referencia útil para detectar diferencias, posibles errores o mejoras del sistema.
- No reemplazan la fuente principal del caso: plan de medición, página real y `measurement_case` generado.

## Done when
- Existe `measurement_case.json`
- Existe `tag_template.js`
- Existe `trigger_selector.txt`
- Existe `report.md`
- El reporte indica matches encontrados por selector
- El código no tiene valores hardcodeados fuera de los datos del caso
- Los campos ambiguos o incompletos quedaron marcados explícitamente
