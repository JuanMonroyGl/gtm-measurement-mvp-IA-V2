# GTM Measurement MVP

## Resumen
Este MVP procesa planes de medición y genera artefactos técnicos para GTM (`measurement_case.json`, `tag_template.js`, `trigger_selector.txt`, `report.md`).

## Formatos de entrada soportados (fase actual, sin IA)
El caso puede llegar en **uno** de estos formatos:

### A) Carpeta de imágenes
```text
inputs/<case_id>/images/
  01.png
  02.jpg
```

### B) PDF
```text
inputs/<case_id>/source/
  plan.pdf
```

### C) PPTX
```text
inputs/<case_id>/source/
  plan.pptx
```

Metadata opcional en todos los casos:
```text
inputs/<case_id>/metadata.json
```

## Flujo nuevo de intake/preparación
Antes de OCR/lectura del plan, el backend ejecuta una capa de intake:

1. Detecta el tipo de input del caso.
2. Prepara assets en estructura estándar.
3. Convierte PDF/PPTX a imágenes cuando aplica.
4. Deja trazabilidad en manifiesto.
5. Continúa el pipeline usando siempre `prepared_assets/images/`.

Estructura interna generada:
```text
outputs/<case_id>/prepared_assets/
  asset_manifest.json
  images/
    001.png
    002.png
```

## Comandos
### Inspección (no ejecuta pipeline completo)
```bash
python main.py inspect --case-path inputs/<case_id>
```

`inspect` reporta:
- tipo detectado,
- archivos encontrados,
- imágenes preparadas,
- warnings/errores,
- si el caso quedó listo para ejecutar.

### Ejecución completa
```bash
python main.py run --case-path inputs/<case_id>
```

`run` toma siempre como base `outputs/<case_id>/prepared_assets/images/`.

## Dependencias
Instalación base:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Dependencias relevantes para intake:
- `pypdfium2`: conversión PDF -> imágenes.
- LibreOffice (`soffice` o `libreoffice` en PATH): conversión PPTX -> PDF.

## Errores amigables esperados
El intake falla temprano y explica causa cuando:
- no se encontró input válido,
- hay múltiples fuentes incompatibles,
- formato no soportado,
- no se pudo convertir PDF/PPTX,
- `.ppt` legacy detectado (sugerencia: convertir a `.pptx`).

## Outputs esperados por `run`
- `outputs/<case_id>/prepared_assets/asset_manifest.json`
- `outputs/<case_id>/prepared_assets/images/*`
- `outputs/<case_id>/measurement_case.json`
- `outputs/<case_id>/tag_template.js`
- `outputs/<case_id>/trigger_selector.txt`
- `outputs/<case_id>/report.md`
- `outputs/<case_id>/run_summary.json`
- `outputs/<case_id>/resolved_case_input.json`

## Pruebas rápidas recomendadas
Caso con imágenes:
```bash
python main.py inspect --case-path inputs/case_001
python main.py run --case-path inputs/case_001
```

Caso con PDF:
```bash
mkdir -p inputs/case_pdf/source
cp /ruta/plan.pdf inputs/case_pdf/source/plan.pdf
python main.py inspect --case-path inputs/case_pdf
python main.py run --case-path inputs/case_pdf
```

Caso con PPTX:
```bash
mkdir -p inputs/case_pptx/source
cp /ruta/plan.pptx inputs/case_pptx/source/plan.pptx
python main.py inspect --case-path inputs/case_pptx
python main.py run --case-path inputs/case_pptx
```

## Límites honestos de esta fase
- No hay IA en intake.
- `.ppt` legacy no está soportado.
- Conversión PPTX depende de LibreOffice instalado en sistema.
- Si OCR no está disponible y no existe `image_evidence.json`, el pipeline se detiene.
