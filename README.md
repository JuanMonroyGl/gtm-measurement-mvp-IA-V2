# GTM Measurement MVP

## Resumen
Este repositorio transforma un caso de medición (imágenes del plan + metadata) en artefactos base para implementación en GTM: `measurement_case.json`, propuesta de selectores, `trigger_selector.txt`, `tag_template.js` y `report.md`.

No es un publicador automático en GTM ni una herramienta autoservicio final: es un **MVP funcional de uso interno** que acelera trabajo técnico y mantiene revisión humana obligatoria.

> **Confidencialidad:** este repositorio es privado y de uso interno.

## Estado actual del MVP
- ✅ Estructura del repo aplanada en la **raíz** (sin carpeta anidada adicional).
- ✅ Pipeline ejecutable por caso desde `main.py` (con wrapper temporal en `src/cli/run_case.py`).
- ✅ OCR operativo cuando el entorno está listo.
- ✅ Fallback por `image_evidence.json` cuando OCR no está disponible y existe evidencia previa.
- ✅ Generación de artefactos clave (`measurement_case.json`, selectores, trigger, tag y reporte).
- ✅ Validación activa de `measurement_case.json` contra `schemas/measurement_case.schema.json`.
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
- genera `report.md` con evidencia, conflictos, warnings y métricas agregadas del caso.

## Flujo general del proyecto
1. **Entrada del caso**: `inputs/<case_id>/images/` + `inputs/<case_id>/metadata.json`.
2. **Extracción del plan**: OCR como camino principal.
3. **Fallback opcional**: si OCR falla/no está disponible, usar `inputs/<case_id>/image_evidence.json` (si existe).
4. **Normalización**: construcción de `measurement_case.json`.
5. **Scraping/DOM**: captura y análisis para proponer selectores.
6. **Validación de contrato**: `measurement_case.json` debe cumplir schema JSON.
7. **Generación**: `trigger_selector.txt` + `tag_template.js`.
8. **Reporte**: `report.md` con matches, supuestos y alertas.
9. **Validación humana**: revisión técnica + GTM Preview antes de producción.

## Estructura del repositorio
```text
.
├── main.py
├── README.md
├── requirements.txt
├── inputs/
├── outputs/                  # se crea/actualiza al ejecutar casos
├── plan_reader/
├── web_scraping/
├── processing/
│   ├── selectors/
│   └── validation/
├── output_generation/
├── templates/
├── examples/
├── ai/
├── checks/
├── schemas/
└── src/cli/run_case.py       # wrapper temporal de compatibilidad
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
### En caso de que no funcione el requirements.txt
```bash
python -m pip install rapidocr-onnxruntime==1.2.3 onnxruntime==1.24.4 opencv-python==4.13.0.92 beautifulsoup4==4.12.3 lxml==5.2.2
```
### Luego validar asi
```bash
python -c "import rapidocr_onnxruntime, onnxruntime, cv2; print('OCR OK'); print(cv2.__version__)"
```

## Cómo ejecutar un caso
Ejemplo con `case_001`:
```bash
python main.py --case-id case_001 --repo-root .
```

Compatibilidad temporal (legacy):
```bash
python -m src.cli.run_case --case-id case_001 --repo-root .
```

El mismo flujo aplica para otros casos reales, por ejemplo `case_002`:
```bash
python main.py --case-id case_002 --repo-root .
```

## Preflight OCR
Antes de correr el pipeline completo, puedes validar entorno y fallback:
```bash
python main.py --case-id case_001 --repo-root . --inspect-only
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

## Qué sigue a futuro
- Mejorar cobertura de casos y diversidad de layouts.
- Endurecer validaciones automáticas de selectores y confidence.
- Robustecer extracción OCR para entornos heterogéneos.
- Ampliar checks automáticos por tipo de evento.
- Estandarizar criterios de aceptación previos a producción.
- Incorporar una capa **asistida por IA** para resolver casos ambiguos en la selección de elementos del DOM.

### Evolución asistida por IA
La idea no es reemplazar el pipeline actual, sino complementarlo.

Hoy el flujo usa:
- OCR o fallback para extraer información del plan
- reglas y heurísticas para proponer selectores
- validación humana en GTM Preview

La siguiente evolución lógica sería usar IA solo cuando haya ambigüedad, por ejemplo:
- varios elementos parecidos en la página
- textos similares en distintos bloques
- componentes complejos donde un selector heurístico puede ser demasiado amplio o frágil

En ese escenario, la IA ayudaría a:
- priorizar el candidato correcto dentro del DOM
- reducir ambigüedad en casos complejos
- mejorar la calidad de los selectores propuestos

El objetivo sería mantener un enfoque híbrido:
- **reglas determinísticas** para los casos claros
- **asistencia de IA** para los casos ambiguos

Esto permitiría que el proyecto sea más robusto sin perder control técnico ni trazabilidad.

---

### Nota importante de uso
Este MVP **no reemplaza** revisión humana. Todo resultado debe pasar por validación técnica y funcional, incluyendo prueba en **GTM Preview**, antes de considerarse para producción.
