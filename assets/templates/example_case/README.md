# Plantilla de caso

1. Copia esta carpeta dentro de `inputs/`.
2. Renombra la carpeta al `case_id` real (por ejemplo `case_003`).
3. Reemplaza `metadata.json` con los datos reales del caso.
4. Agrega imágenes del plan en `images/`.

Estructura mínima:

```text
inputs/<case_id>/
  images/
    01.png
    02.png
  metadata.json
```

Comandos:

```bash
python main.py inspect --case-path inputs/<case_id>
python main.py run --case-path inputs/<case_id>
```
