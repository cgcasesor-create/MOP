"""Consultor legal sobre Claude: responde consultas con el formato obligatorio."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from pydantic import BaseModel

from .. import motor
from ..modelos import Contrato, Riesgo, TipoAccion
from ..normativa import CATALOGO
from .prompt_maestro import PROMPT_MAESTRO

MODELO = "claude-opus-5-5"


class PlanAccionInmediato(BaseModel):
    tipo: TipoAccion
    descripcion: str
    borrador: str


class RespuestaConsulta(BaseModel):
    sintesis_ejecutiva: str
    riesgo_legal_asignado: Riesgo
    articulo_rcop: str
    ley_especial_cruzada: str
    analisis_juridico: str
    analisis_reputacional: str
    plan_accion_inmediato: PlanAccionInmediato
    advertencias_verificacion: list[str]


ESQUEMA_RESPUESTA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": list(RespuestaConsulta.model_fields),
    "properties": {
        "sintesis_ejecutiva": {"type": "string"},
        "riesgo_legal_asignado": {"type": "string", "enum": [r.value for r in Riesgo]},
        "articulo_rcop": {"type": "string"},
        "ley_especial_cruzada": {"type": "string"},
        "analisis_juridico": {"type": "string"},
        "analisis_reputacional": {"type": "string"},
        "plan_accion_inmediato": {
            "type": "object",
            "additionalProperties": False,
            "required": ["tipo", "descripcion", "borrador"],
            "properties": {
                "tipo": {"type": "string", "enum": [t.value for t in TipoAccion]},
                "descripcion": {"type": "string"},
                "borrador": {"type": "string"},
            },
        },
        "advertencias_verificacion": {"type": "array", "items": {"type": "string"}},
    },
}


class ConsultaRechazada(Exception):
    pass


def estado_motor(c: Contrato, hoy: date) -> str:
    """Fotografía del Gemelo Digital para el modelo (sin el expediente documental)."""
    snapshot = motor.resumen(c, hoy)
    snapshot["fecha_evaluacion"] = hoy
    snapshot["contrato"] = c.model_dump(exclude={"expediente", "sello"})
    snapshot["catalogo_normativo"] = {k: v.model_dump() for k, v in CATALOGO.items()}
    return json.dumps(snapshot, default=lambda o: o.model_dump() if hasattr(o, "model_dump") else str(o),
                      ensure_ascii=False, indent=1)


class Consultor:
    def __init__(self, client: Any = None, modelo: str = MODELO):
        self._client = client
        self.modelo = modelo

    @property
    def client(self) -> Any:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()
        return self._client

    def consultar(self, c: Contrato, pregunta: str, hoy: date) -> RespuestaConsulta:
        response = self.client.beta.messages.create(
            model=self.modelo,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            thinking={"type": "adaptive"},
            output_config={
                "effort": "high",
                "format": {"type": "json_schema", "schema": ESQUEMA_RESPUESTA},
            },
            system=[{"type": "text", "text": PROMPT_MAESTRO, "cache_control": {"type": "ephemeral"}}],
            messages=[
                {
                    "role": "user",
                    "content": f"<estado_motor>\n{estado_motor(c, hoy)}\n</estado_motor>\n\n"
                    f"<consulta>\n{pregunta}\n</consulta>",
                }
            ],
        )
        if response.stop_reason == "refusal":
            raise ConsultaRechazada("El modelo declinó responder la consulta.")
        if response.stop_reason == "max_tokens":
            raise ConsultaRechazada("La respuesta excedió el máximo de tokens.")
        texto = "".join(b.text for b in response.content if b.type == "text")
        return RespuestaConsulta.model_validate_json(texto)
