"""Pydantic contracts for AI module outputs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Interaction(BaseModel):
    tipo_evento: str | None = None
    flujo: str | None = None
    ubicacion: str | None = None
    texto_referencia: str | None = None
    interaction_mode: Literal["single", "group"] | None = None
    group_context: str | None = None
    zone_hint: str | None = None
    confidence: float = 0.0
    warning: str | None = None


class PlanExtraction(BaseModel):
    activo: str | None = None
    seccion: str | None = None
    interactions: list[Interaction] = Field(default_factory=list)


class DomActionSuggestion(BaseModel):
    action: Literal["none", "scroll", "open_nav", "expand_tab", "expand_accordion", "advance_carousel"]
    target_text: str | None = None
    reason: str
    confidence: float


class SelectorDecision(BaseModel):
    selected_selector: str | None
    confidence: float
    reason: str
    rejects: list[str] = Field(default_factory=list)
    requires_human_review: bool = False
