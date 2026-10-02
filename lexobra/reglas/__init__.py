"""Reglas de cruce normativo por fase.

Cada regla es una función pura ``(contrato, hoy) -> list[Alerta]`` que se
auto-protege según los datos disponibles; el motor ejecuta todas y así ninguna
obligación pendiente de una fase anterior queda sin alertar.
"""

from __future__ import annotations

from datetime import date

from ..modelos import Alerta, Fase, PlanAccion, Riesgo, TipoAccion
from ..normativa import norma


def alerta(
    codigo_regla: str,
    fase: Fase,
    codigo_norma: str,
    titulo: str,
    detalle: str,
    riesgo: Riesgo,
    accion: TipoAccion,
    descripcion_accion: str,
    *,
    ley_especial: str | None = None,
    borrador: str | None = None,
    bloqueo: bool = False,
    fecha_limite: date | None = None,
) -> Alerta:
    n = norma(codigo_norma)
    return Alerta(
        codigo_regla=codigo_regla,
        fase=fase,
        titulo=titulo,
        detalle=detalle,
        riesgo=riesgo,
        articulo_rcop=n.cita(),
        ley_especial_cruzada=ley_especial,
        plan_accion=PlanAccion(tipo=accion, descripcion=descripcion_accion, borrador=borrador),
        bloqueo=bloqueo,
        fecha_limite=fecha_limite,
        verificacion_normativa=n.estado_verificacion,
    )


def riesgo_por_plazo(hoy: date, vence: date, alerta_previa_dias: int) -> Riesgo:
    if hoy > vence or (vence - hoy).days <= alerta_previa_dias:
        return Riesgo.ALTO
    return Riesgo.MEDIO
