"""Fase 2: Ejecución, subcontratos y estados de pago."""

from __future__ import annotations

from datetime import date

from .. import borradores, calculos
from ..modelos import Alerta, Contrato, Fase, PropositoGarantia, Riesgo, TipoAccion
from . import alerta

F = Fase.EJECUCION


def regla_tope_subcontratacion(c: Contrato, hoy: date) -> list[Alerta]:
    p = c.parametros
    porcentaje = calculos.pct(calculos.total_subcontratado(c), calculos.valor_vigente(c))
    if porcentaje < p.alerta_subcontratacion_pct:
        return []
    excedido = porcentaje > p.tope_subcontratacion_pct
    return [
        alerta(
            "F2_TOPE_SUBCONTRATACION",
            F,
            "RCOP_SUBCONTRATOS",
            "Tope de subcontratación " + ("excedido" if excedido else "próximo"),
            f"Subcontratado: {porcentaje}% del valor vigente del contrato (tope {p.tope_subcontratacion_pct}%).",
            Riesgo.ALTO if excedido else Riesgo.MEDIO,
            TipoAccion.BLOQUEO if excedido else TipoAccion.NOTIFICACION,
            "Bloquear nuevos subcontratos y gestionar excepción fundada ante el Director."
            if excedido
            else "Revisar planificación antes de suscribir nuevos subcontratos.",
            bloqueo=excedido,
        )
    ]


def regla_subcontratos_no_autorizados(c: Contrato, hoy: date) -> list[Alerta]:
    return [
        alerta(
            "F2_SUBCONTRATO_NO_AUTORIZADO",
            F,
            "RCOP_SUBCONTRATOS",
            f"Subcontrato con {s.razon_social} sin autorización de la Dirección",
            "La subcontratación requiere autorización previa; la autorización no libera al contratista de "
            "sus obligaciones ni de las laborales impagas del subcontratista.",
            Riesgo.ALTO,
            TipoAccion.BLOQUEO,
            "Suspender ingreso del subcontratista y solicitar autorización a la Dirección.",
            ley_especial="Código del Trabajo, Art. 183-B (responsabilidad solidaria)",
            bloqueo=True,
        )
        for s in c.subcontratos
        if not s.autorizado_por_direccion
    ]


def regla_pagos_subcontratos_bloqueados(c: Contrato, hoy: date) -> list[Alerta]:
    nombres = {s.id: s.razon_social for s in c.subcontratos}
    return [
        alerta(
            "F2_PAGO_SUBCONTRATO_RETENIDO",
            F,
            "CT_SUBCONTRATACION",
            f"EP N°{ep.numero}: pago a {nombres.get(pago.subcontrato_id, pago.subcontrato_id)} retenido",
            pago.motivo_bloqueo or "Cumplimiento laboral no acreditado.",
            Riesgo.ALTO,
            TipoAccion.BLOQUEO,
            "Retener el pago (derecho de retención del Art. 183-C) hasta cargar F30-1 del periodo sin deudas.",
            ley_especial="Código del Trabajo, Arts. 183-C y 183-D (Ley 20.123)",
            bloqueo=True,
        )
        for ep in c.estados_pago
        for pago in ep.pagos_subcontratos
        if not pago.liberado
    ]


def regla_canje_retenciones(c: Contrato, hoy: date) -> list[Alerta]:
    alertas = []
    retenido = calculos.retenciones_acumuladas(c) - calculos.garantias_canje(c)
    minima = calculos.vigencia_minima_canje(c)
    if retenido > 0 and minima:
        alertas.append(
            alerta(
                "F2_OPORTUNIDAD_CANJE",
                F,
                "RCOP_RETENCIONES",
                "Oportunidad de canje de retenciones",
                f"Retenciones no canjeadas: ${retenido:,}".replace(",", ".") + ".",
                Riesgo.BAJO,
                TipoAccion.NOTIFICACION,
                "Notificar a Finanzas para evaluar el canje por garantía.",
                borrador=borradores.notificacion_canje(c, retenido, minima),
            )
        )
    for g in c.garantias:
        if g.proposito == PropositoGarantia.CANJE_RETENCIONES and minima and g.vencimiento < minima:
            alertas.append(
                alerta(
                    "F2_CANJE_VIGENCIA_INSUFICIENTE",
                    F,
                    "RCOP_RETENCIONES",
                    f"Garantía de canje {g.emisor} con vigencia insuficiente",
                    f"Vence el {g.vencimiento:%d-%m-%Y}; debe cubrir al menos hasta el {minima:%d-%m-%Y}.",
                    Riesgo.ALTO,
                    TipoAccion.BLOQUEO,
                    "Rechazar el documento y solicitar reemplazo o endoso de ampliación de vigencia.",
                    bloqueo=True,
                )
            )
    return alertas


def regla_movimiento_tierra_rca(c: Contrato, hoy: date) -> list[Alerta]:
    return [
        alerta(
            "F2_MOVIMIENTO_TIERRA_SIN_RCA",
            F,
            "LEY_DELITOS_ECONOMICOS",
            f"Movimiento de tierras/áridos sin respaldo ambiental: {m.descripcion}",
            "No consta RCA ni pronunciamiento de pertinencia de no ingreso al SEIA. La extracción o "
            "intervención sin autorización ambiental expone a la empresa y sus directivos a imputación "
            "por delitos ambientales y a la responsabilidad penal de la persona jurídica.",
            Riesgo.ALTO,
            TipoAccion.BLOQUEO,
            "Suspender la faena hasta cargar la RCA o la carta de pertinencia del SEA.",
            ley_especial="Ley 21.595 (Delitos Económicos); Ley 19.300, Art. 8 y 10",
            bloqueo=True,
        )
        for m in c.movimientos_tierra
        if not m.rca_numero
    ]


REGLAS = [
    regla_tope_subcontratacion,
    regla_subcontratos_no_autorizados,
    regla_pagos_subcontratos_bloqueados,
    regla_canje_retenciones,
    regla_movimiento_tierra_rca,
]
