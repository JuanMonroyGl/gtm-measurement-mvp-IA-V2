# GTM Measurement MVP

## Uso recomendado (sin fricción)
1. Crear `inputs/<case_id>/`.
2. Poner **solo una fuente del plan** (archivo o carpeta de imágenes).
3. Ejecutar `python main.py inspect --case-path inputs/<case_id>`.
4. Ejecutar `python main.py run --case-path inputs/<case_id>`.

No debes declarar el tipo de input manualmente.

## Inputs soportados (autodetección)
El sistema detecta automáticamente cualquiera de estos formatos:

A)
```text
inputs/<case_id>/images/
  01.png
  02.png
```

B)
```text
inputs/<case_id>/plan.pdf
```

C)
```text
inputs/<case_id>/plan.pptx
```

D)
```text
inputs/<case_id>/source/plan.pdf
```

E)
```text
inputs/<case_id>/source/plan.pptx
```

También puede detectar un único PDF/PPTX con otro nombre razonable (no requiere `plan.pdf` exacto).

## Reglas de autodetección
- `images/` + imágenes válidas => flujo imágenes.
- un único PDF en raíz o `source/` => flujo PDF.
- un único PPTX en raíz o `source/` => flujo PPTX.
- múltiples fuentes incompatibles => error amigable.
- múltiples PDFs o múltiples PPTX => error amigable.
- `.ppt` legacy => no soportado, sugerencia de convertir a `.pptx`.

## Comportamiento por tipo
### Images
- OCR / `image_evidence.json` como hoy.

### PDF
- extrae texto nativo por página,
- renderiza páginas a imágenes,
- guarda ambos artefactos en `prepared_assets/`,
- prioriza texto nativo para inferir metadata.

### PPTX
- extrae texto nativo por slide,
- usa ese texto como fuente principal de inferencia,
- intenta renderizar slides a imágenes con LibreOffice,
- si no hay LibreOffice, continúa con texto nativo (no bloquea por eso).

## DOM acquisition (web)
- Estrategia principal: Playwright (DOM renderizado).
- Fallback: fetch de HTML crudo cuando Playwright no está disponible o falla.
- El pipeline deja warnings claros cuando cae a fallback.
- `raw_html_fallback` no se trata como `observed_rendered_dom`: no autopromueve selector final.

## Salida estandarizada de intake
```text
outputs/<case_id>/prepared_assets/
  asset_manifest.json
  native_text.json          # cuando aplica (PDF/PPTX)
  image_evidence.json       # soporte textual para parser
  images/
    001.png
    002.png
```

## Dependencias
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

Nuevas dependencias clave:
- `pypdf` para texto nativo de PDF.
- `python-pptx` para texto nativo de PPTX.
- `pypdfium2` para render de PDF a imágenes.
- `playwright` para adquisición real de DOM renderizado.
- LibreOffice opcional para render de PPTX a imágenes.

## Límites honestos (fase sin IA)
- No hay IA en intake ni scraping.
- `.ppt` no soportado.
- Si no hay `target_url` resoluble desde metadata o evidencia textual, el caso falla con error claro.
- Si Playwright o el navegador Chromium no están instalados, el scraping degrada a `raw_html_fallback` y el gate estricto puede rechazar el caso.
- Render visual de PPTX depende de LibreOffice; sin LibreOffice se continúa solo con texto nativo.


## Endurecimiento de selectores (DOM real)
- El pipeline solo autopromueve selectores `observed_rendered_dom`.
- `raw_html_fallback` queda degradado: warning explícito, revisión humana obligatoria y sin autopromoción final.
- Si no hay evidencia DOM suficiente, el selector queda en `null` y se marca revisión humana en trazas/reporte.
- Se genera `outputs/<case_id>/clickable_inventory.json` con inventario de nodos accionables por estado.
- Se genera `outputs/<case_id>/selector_trace.json` con evidencia de selección/rechazo por interacción.
- `report.md` y `run_summary.json` incluyen estados verificados, origen del selector, métricas de rechazo y resultado del gate final.

Checks recomendados:
```bash
python core/checks/check_selector_grounding.py --case-id case_001 --repo-root .
python core/checks/check_case_output.py --case-id case_001 --repo-root .
```
