# GTM Measurement MVP

## Resumen
Este repositorio transforma un caso de medición (imágenes del plan + metadata) en artefactos base para implementación en GTM: `measurement_case.json`, propuesta de selectores, `trigger_selector.txt`, `tag_template.js` y `report.md`.

No es un publicador automático en GTM ni una herramienta autoservicio final: es un **MVP funcional de uso interno** que acelera trabajo técnico y mantiene revisión humana obligatoria.

> **Confidencialidad:** este repositorio es privado y de uso interno.

## Estado actual del MVP
- ✅ Estructura del repo aplanada en la **raíz** (sin carpeta anidada adicional).
- ✅ CLI aterrizado para usuario sin contexto: `inspect` y `run` desde `main.py`.
- ✅ OCR operativo cuando el entorno está listo.
- ✅ Fallback por `image_evidence.json` cuando OCR no está disponible y existe evidencia previa.
- ✅ Generación de artefactos clave (`measurement_case.json`, selectores, trigger, tag y reporte).
- ✅ Resumen de ejecución por caso en `run_summary.json`.
- ✅ Validación activa de `measurement_case.json` contra `assets/schemas/measurement_case.schema.json`.
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
- valida contrato de entrada (`images/` + `metadata.json`),
- usa OCR (o fallback con evidencia),
- cruza con `metadata.json`,
- construye `measurement_case.json`,
- propone y valida selectores contra el DOM snapshot,
- genera `trigger_selector.txt` consolidado,
- genera `tag_template.js` funcional (patrón del proyecto),
- genera `report.md` con evidencia, conflictos, warnings y métricas agregadas del caso,
- genera `run_summary.json` para lectura rápida de estado/alertas.

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
├── .gitignore
├── inputs/
├── core/
│   ├── ai/
│   ├── checks/
│   ├── cli/run_case.py       # wrapper temporal de compatibilidad
│   ├── output_generation/
│   ├── plan_reader/
│   ├── processing/
│   │   ├── selectors/
│   │   └── validation/
│   └── web_scraping/
├── assets/
│   ├── examples/
│   ├── schemas/
│   └── templates/            # incluye plantilla copiables de caso
└── outputs/                  # se crea/actualiza al ejecutar casos
```

## Contrato simple de entrada (caso)
Estructura esperada:

```text
inputs/<case_id>/
  images/
    01.png
    02.png
    ...
  metadata.json   # opcional
```

Campos mínimos de `metadata.json`:
- `case_id` (opcional, se toma de carpeta si falta)
- `target_url` (opcional en modo images-only)
- `plan_url` (opcional)
- `activo` (opcional)
- `seccion` (opcional)

### Modo images-only (regla de negocio)
Si no existe `metadata.json`, el sistema:
- infiere `target_url` desde imágenes,
- construye metadata resuelta interna,
- y continúa el pipeline automáticamente.

Si detecta múltiples URLs candidatas o ninguna URL clara, falla con mensaje amigable.

Plantilla lista para copiar:
- `assets/templates/example_case/`

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

## Cómo ejecutar un caso (nuevo CLI)
1) Inspeccionar el caso (sin correr pipeline):
```bash
python main.py inspect --case-path inputs/case_001
```

2) Ejecutar el pipeline:
```bash
python main.py run --case-path inputs/case_001
```

Compatibilidad temporal (legacy, aún soportada):
```bash
python main.py --case-id case_001 --inspect-only
python main.py --case-id case_001
```

`inspect` reporta de forma amigable:
- estructura detectada
- errores esperables de usuario
- diagnóstico OCR
- disponibilidad de fallback (`image_evidence.json`)
- metadata inferida y ejecutabilidad del caso (images-only o con metadata)

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
- `outputs/<case_id>/run_summary.json`
- `outputs/<case_id>/resolved_case_input.json`

`run_summary.json` incluye como mínimo:
- `case_id`
- `status` (`success` / `warning`)
- inputs detectados
- cantidad de imágenes
- `target_url`
- uso de OCR/fallback/IA disponible
- interacciones detectadas
- ambigüedad detectada
- outputs generados
- warnings relevantes

`resolved_case_input.json` deja trazabilidad de:
- metadata explícita (si existe),
- metadata inferida desde imágenes,
- metadata final resuelta usada por el pipeline.

## Casos validados
- **case_001**: golden case validado manualmente en GTM Preview.
- **case_002**: segundo caso real disponible para validar robustez del flujo multi-caso.

## Benchmarks manuales por caso
Cuando existen implementaciones/manuales de referencia, usar:
- `assets/examples/case_XXX_expected_tag.js`
- `assets/examples/case_XXX_expected_trigger.txt`
- `assets/examples/case_XXX_notes.md`

Estos archivos sirven para comparar resultados, detectar desviaciones y acelerar debugging. Son **referencia útil**, no fuente absoluta por encima del plan/metadata/DOM real.

## Checks mínimos
Check base anti-regresión por caso:
```bash
python core/checks/check_case_output.py --case-id case_001 --repo-root .
```

Comparación contra benchmark manual (`assets/examples/`):
```bash
python core/checks/compare_case_outputs_against_examples.py --case-id case_001 --repo-root .
```

## Troubleshooting (rápido)
- **Falta metadata.json**: crea `inputs/<case_id>/metadata.json` con `case_id` y `target_url`.
- **Falta metadata.json**: en modo images-only no bloquea; el sistema intentará inferir metadata desde imágenes.
- **No existe images/**: crea `inputs/<case_id>/images/`.
- **No hay imágenes**: agrega al menos un `.png/.jpg/.jpeg/.webp`.
- **JSON mal formado**: valida sintaxis en `metadata.json`.
- **No se pudo inferir URL**: revisa calidad/texto de imágenes o agrega `metadata.json` con `target_url`.
- **Falla OCR al importar librerías**: corre `inspect` y revisa `ocr_diagnostic`.
- **Sin OCR y sin fallback**: el pipeline debe fallar temprano; agrega/corrige `image_evidence.json` o habilita OCR.
- **Selectores ambiguos**: revisar `report.md` y ajustar estrategia de selector en validación humana.
- **Diferencias contra implementación previa**: comparar con `assets/examples/` y documentar decisión en reporte.

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
