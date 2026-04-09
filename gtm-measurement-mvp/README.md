# gtm-measurement-mvp

MVP para convertir un caso de plan de medición (imágenes + metadata) en artefactos iniciales para GTM.

## Requisitos
- Python 3.11+
- Dependencias:

```bash
pip install -r requirements.txt
```

## Ejecutar caso localmente
Desde la raíz del proyecto (`gtm-measurement-mvp/`):

```bash
python -m src.cli.run_case --case-id case_001 --repo-root .
```

## Output esperado (fase actual)
Se crea `outputs/case_001/` con:
- `measurement_case.json` (interacciones detectadas desde imágenes)
- `tag_template.js` (stub)
- `trigger_selector.txt` (stub)
- `report.md` (evidencia textual, warnings y campos incompletos)

> Nota: no incluye scraping complejo del DOM ni generación final de GTM todavía.
