# GTM Measurement MVP

## Resumen
Este repositorio transforma un caso de medición (imágenes del plan + metadata) en artefactos base para implementación en GTM: `measurement_case.json`, propuesta de selectores, `trigger_selector.txt`, `tag_template.js` y `report.md`.

No es un publicador automático en GTM ni una herramienta autoservicio final: es un **MVP funcional de uso interno** que acelera trabajo técnico y mantiene revisión humana obligatoria.

> **Confidencialidad:** este repositorio es privado y de uso interno.

## Estado actual del MVP
- ✅ Estructura del repo aplanada en la **raíz** (sin carpeta anidada adicional).
- ✅ Pipeline ejecutable por caso desde `src/cli/run_case.py`.
- ✅ OCR operativo cuando el entorno está listo.
- ✅ Fallback por `image_evidence.json` cuando OCR no está disponible y existe evidencia previa.
- ✅ Generación de artefactos clave (`measurement_case.json`, selectores, trigger, tag y reporte).
- ✅ Checks mínimos anti-regresión.
- ✅ `case_001` validado manualmente como **golden case** en GTM Preview.
- ✅ `case_002` disponible como segundo caso real para demostrar que el flujo no depende de un único caso.

## Qué problema resuelve
Reduce el trabajo manual repetitivo de pasar planes de medición en imágenes a una primera implementación técnica en GTM.

En vez de “adivinar” una solución final, el MVP:
1. extrae y normaliza información,
2. propone selectores,
3. genera código base,
4. deja trazabilidad de supuestos/alertas,
5. prepara una revisión técnica y funcional más rápida.

## Qué hace hoy
Para un `case_id` en `inputs/`:
- lee imágenes del plan,
- usa OCR (o fallback con evidencia),
- cruza con `metadata.json`,
- construye `measurement_case.json`,
- propone y valida selectores contra el DOM snapshot,
- genera `trigger_selector.txt` consolidado,
- genera `tag_template.js` funcional (patrón del proyecto),
- genera `report.md` con evidencia, conflictos y warnings.

## Flujo general del proyecto
1. **Entrada del caso**: `inputs/<case_id>/images/` + `inputs/<case_id>/metadata.json`.
2. **Extracción del plan**: OCR como camino principal.
3. **Fallback opcional**: si OCR falla/no está disponible, usar `inputs/<case_id>/image_evidence.json` (si existe).
4. **Normalización**: construcción de `measurement_case.json`.
5. **Scraping/DOM**: captura y análisis para proponer selectores.
6. **Generación**: `trigger_selector.txt` + `tag_template.js`.
7. **Reporte**: `report.md` con matches, supuestos y alertas.
8. **Validación humana**: revisión técnica + GTM Preview antes de producción.

## Estructura del repositorio
```text
.
├── README.md
├── requirements.txt
├── src/
│   ├── cli/run_case.py
│   ├── plan_parser/
│   ├── scraper/
│   ├── selectors/
│   └── generator/
├── inputs/
│   ├── case_001/
│   └── case_002/
├── outputs/                  # se crea/actualiza al ejecutar casos
├── checks/
├── examples/
└── schemas/
```

## Requisitos
- Python 3.11+
- Dependencias de `requirements.txt`
- Entorno con soporte OCR si se quiere usar el camino principal (ver sección de preflight)

## Instalación
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Cómo ejecutar un caso
Ejemplo con `case_001`:
```bash
python -m src.cli.run_case --case-id case_001 --repo-root .
```

El mismo flujo aplica para otros casos reales, por ejemplo `case_002`:
```bash
python -m src.cli.run_case --case-id case_002 --repo-root .
```

## Preflight OCR
Antes de correr el pipeline completo, puedes validar entorno y fallback:
```bash
python -m src.cli.run_case --case-id case_001 --repo-root . --inspect-only
```

Este comando reporta, entre otros:
- `ocr_available`
- `ocr_diagnostic`
- `fallback_available`

## Qué hacer cuando OCR no funciona
1. Ejecuta `--inspect-only` para confirmar diagnóstico.
2. Si existe `inputs/<case_id>/image_evidence.json`, úsalo como fallback para no bloquear el caso.
3. Si no existe fallback, corrige entorno OCR y reintenta.

Problema común (`libGL.so.1` / conflicto OpenCV):
```bash
python -m pip uninstall -y opencv-python
python -m pip install --upgrade opencv-python-headless rapidocr-onnxruntime
```

## Outputs generados
Después de ejecutar un caso, se espera:
- `outputs/<case_id>/measurement_case.json`
- `outputs/<case_id>/trigger_selector.txt`
- `outputs/<case_id>/tag_template.js`
- `outputs/<case_id>/report.md`

## Casos validados
- **case_001**: golden case validado manualmente en GTM Preview.
- **case_002**: segundo caso real disponible para validar robustez del flujo multi-caso.

## Benchmarks manuales por caso
Cuando existen implementaciones/manuales de referencia, usar:
- `examples/case_XXX_expected_tag.js`
- `examples/case_XXX_expected_trigger.txt`
- `examples/case_XXX_notes.md`

Estos archivos sirven para comparar resultados, detectar desviaciones y acelerar debugging. Son **referencia útil**, no fuente absoluta por encima del plan/metadata/DOM real.

## Checks mínimos
Check base anti-regresión por caso:
```bash
python checks/check_case_output.py --case-id case_001 --repo-root .
```

Comparación contra benchmark manual (`examples/`):
```bash
python checks/compare_case_outputs_against_examples.py --case-id case_001 --repo-root .
```

## Troubleshooting (rápido)
- **Falla OCR al importar librerías**: corre preflight con `--inspect-only` y revisa `ocr_diagnostic`.
- **Sin OCR y sin fallback**: el pipeline debe fallar temprano; agrega/corrige `image_evidence.json` o habilita OCR.
- **Selectores ambiguos**: revisar `report.md` y ajustar estrategia de selector en validación humana.
- **Diferencias contra implementación previa**: comparar con `examples/` y documentar decisión en reporte.

## Qué sigue a futuro (realista)
- Mejorar cobertura de casos y diversidad de layouts.
- Endurecer validaciones automáticas de selectores y confidence.
- Robustecer extracción OCR para entornos heterogéneos.
- Ampliar checks automáticos por tipo de evento.
- Estandarizar criterios de aceptación previos a producción.

---

### Nota importante de uso
Este MVP **no reemplaza** revisión humana. Todo resultado debe pasar por validación técnica y funcional, incluyendo prueba en **GTM Preview**, antes de considerarse para producción.
