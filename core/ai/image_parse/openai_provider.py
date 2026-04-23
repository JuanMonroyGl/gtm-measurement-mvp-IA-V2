"""OpenAI provider for image_parse.

This module is intentionally bounded: it only extracts structured hints from plan images.
It does not propose selectors and does not alter final grounding rules.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from core.ai.cache import AICache
from core.ai.config import AIConfig
from core.ai.contracts import PlanExtraction
from core.ai.openai_client import get_openai_client


def _to_data_url(path: Path) -> str:
    mime = "image/png"
    if path.suffix.lower() in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif path.suffix.lower() == ".webp":
        mime = "image/webp"
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


class OpenAIImageParseProvider:
    def __init__(self, config: AIConfig) -> None:
        self.config = config
        self.client = get_openai_client()
        self.cache = AICache(config.cache_dir)

    def _build_messages(self, image_paths: list[Path]) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [
            {
                "type": "input_text",
                "text": (
                    "Extrae SOLO JSON válido con esta forma: "
                    "{activo, seccion, interactions:[{tipo_evento, flujo, ubicacion, texto_referencia, interaction_mode, group_context, zone_hint, confidence, warning}]}. "
                    "Reglas: no inventar campos faltantes; usar null cuando falte evidencia; "
                    "tipo_evento permitido: Clic Boton|Clic Card|Clic Link|Clic Tap. "
                    "interaction_mode solo puede ser single o group. "
                    "La IA puede clasificar interaction_mode, group_context y zone_hint, pero NO proponer selectores."
                ),
            }
        ]

        for image_path in image_paths:
            content.append(
                {
                    "type": "input_image",
                    "image_url": _to_data_url(image_path),
                    "detail": self.config.image_detail,
                }
            )

        return [{"role": "user", "content": content}]

    def parse(self, *, case_id: str, image_paths: list[Path]) -> dict:
        request_fingerprint = {
            "provider": "openai",
            "model": self.config.model_image,
            "image_detail": self.config.image_detail,
            "paths": [str(p) for p in image_paths],
            "sizes": [p.stat().st_size for p in image_paths],
        }
        cache_key = self.cache.build_key(request_fingerprint)
        cached = self.cache.read("image_parse", cache_key)
        if cached:
            cached["cache_hit"] = True
            return cached

        messages = self._build_messages(image_paths)
        response = self.client.responses.create(
            model=self.config.model_image,
            input=messages,
            max_output_tokens=self.config.max_tokens_image,
        )

        raw_text = response.output_text or "{}"
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            parsed = {"activo": None, "seccion": None, "interactions": [], "warnings": ["JSON inválido"]}

        contract = PlanExtraction.model_validate(parsed)
        payload = {
            "provider": "openai",
            "enabled": True,
            "cache_hit": False,
            "case_id": case_id,
            "model": self.config.model_image,
            "image_count": len(image_paths),
            "parsed": contract.model_dump(),
            "raw_text": raw_text,
        }
        self.cache.write("image_parse", cache_key, payload)
        return payload
