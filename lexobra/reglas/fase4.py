"""Fase 4: Recepción provisoria y definitiva."""

from __future__ import annotations

from datetime import date

from .. import borradores, calculos
from ..calendario import sumar_dias_habiles, sumar_meses
from ..modelos import Alerta, Contrato, Fase, Riesgo, TipoAccion
from . import alerta, riesgo_por_plazo

F = Fase.RECEPCION


def regla_plazos_comision(c: Contrato, hoy: date) -> list[Alerta]:
    h, p = c.hitos, c.parametros
    if not h.fecha_solicitud_termino or h.fecha_recepcion_provisoria:
        return []
    if not h.fecha_designacion_comision:
        vence = sumar_dias_habiles(h.fecha_solicitud_termino, p.plazo_designacion_comision_dias_habiles)
        vencido = hoy > vence
        return [
            alerta(
                "F4_DESIGNACION_COMISION",
                F,
                "RCOP_RECEPCION_PROVISORIA",
                "Comisión de recepción provisoria " + ("no designada en plazo" if vencido else "pendiente"),
                f"Plazo de {p.plazo_designacion_comision_dias_habiles} días hábiles vence el {vence:%d-%m-%Y}.",
                Riesgo.ALTO if vencido else riesgo_por_plazo(hoy, vence, p.alerta_previa_dias),
                TipoAccion.BORRADOR_CARTA if vencido else TipoAccion.NOTIFICACION,
                "Requerir por escrito la designación y dejar constancia de que el retraso no es imputable."
                if vencido
                else "Monitorear designación.",
                ley_especial="Ley 19.880, Art. 25 (cómputo en días hábiles)",
                borrador=borradores.carta_designacion_comision(c, h.fecha_solicitud_termino, vence)
                if vencido
                else None,
                fecha_limite=vence,
            )
        ]
    if not h.fecha_informe_comision:
        vence = sumar_dias_habiles(h.fecha_designacion_comision, p.plazo_informe_comision_dias_habiles)
        vencido = hoy > vence
        return [
            alerta(
                "F4_INFORME_COMISION",
                F,
                "RCOP_RECEPCION_PROVISORIA",
                "Informe de la comisión receptora " + ("fuera de plazo" if vencido else "pendiente"),
                f"Plazo de {p.plazo_informe_comision_dias_habiles} días hábiles vence el {vence:%d-%m-%Y}.",
                Riesgo.ALTO if vencido else Riesgo.MEDIO,
                TipoAccion.BORRADOR_CARTA if vencido else TipoAccion.NOTIFICACION,
                "Requerir el informe por escrito." if vencido else "Monitorear informe.",
                ley_especial="Ley 19.880, Art. 25 (cómputo en días hábiles)",
                borrador=borradores.carta_informe_comision(c, h.fecha_designacion_comision, vence)
                if vencido
                else None,
                fecha_limite=vence,
            )
        ]
    return []


def regla_recepciones_parciales(c: Contrato, hoy: date) -> list[Alerta]:
    h = c.hitos
    if h.fecha_solicitud_termino or c.recepciones_parciales:
        return []
    avance = calculos.avance_financiero_pct(c)
    if avance < 50:
        return []
    return [
        alerta(
            "F4_EVALUAR_RECEPCION_PARCIAL",
            F,
            "RCOP_RECEPCION_PROVISORIA",
            "Evaluar recepciones provisorias parciales por tramos",
            f"Avance financiero {avance}%. Una recepción parcial de un tramo vial útil detiene el cómputo de "
            "multas para ese tramo, pero NO libera retenciones ni garantías.",
            Riesgo.BAJO,
            TipoAccion.NOTIFICACION,
            "Identificar tramos terminados y habilitables al tránsito y evaluar solicitud parcial.",
        )
    ]


def regla_recepcion_definitiva(c: Contrato, hoy: date) -> list[Alerta]:
    h, p = c.hitos, c.parametros
    if not h.fecha_recepcion_provisoria or h.fecha_recepcion_definitiva:
        return []
    vence = sumar_meses(h.fecha_recepcion_provisoria, p.plazo_garantia_obra_meses)
    if (vence - hoy).days > 30:
        return []
    return [
        alerta(
            "F4_SOLICITAR_RECEPCION_DEFINITIVA",
            F,
            "RCOP_RECEPCION_DEFINITIVA",
            "Plazo de garantía de obra por vencer: preparar Recepción Definitiva",
            f"El plazo de garantía de {p.plazo_garantia_obra_meses} meses vence el {vence:%d-%m-%Y}.",
            Riesgo.ALTO if hoy > vence else Riesgo.MEDIO,
            TipoAccion.BORRADOR_CARTA,
            "Presentar la solicitud exactamente al vencimiento del plazo de garantía.",
            borrador=borradores.solicitud_recepcion_definitiva(c, h.fecha_recepcion_provisoria, vence),
            fecha_limite=vence,
        )
    ]


REGLAS = [regla_plazos_comision, regla_recepciones_parciales, regla_recepcion_definitiva]
