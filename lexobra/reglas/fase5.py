"""Fase 5: Liquidación del contrato, más controles transversales de garantías."""

from __future__ import annotations

from datetime import date

from ..calendario import sumar_dias_corridos
from ..modelos import Alerta, Contrato, Fase, PropositoGarantia, Riesgo, TipoAccion
from . import alerta, riesgo_por_plazo

F = Fase.LIQUIDACION


def regla_propuesta_liquidacion(c: Contrato, hoy: date) -> list[Alerta]:
    h, p = c.hitos, c.parametros
    if not h.fecha_recepcion_definitiva or h.fecha_propuesta_liquidacion:
        return []
    vence = sumar_dias_corridos(h.fecha_recepcion_definitiva, p.plazo_propuesta_liquidacion_dias)
    return [
        alerta(
            "F5_PROPUESTA_LIQUIDACION",
            F,
            "RCOP_LIQUIDACION",
            "Cargar propuesta de liquidación",
            f"Vence el {vence:%d-%m-%Y}. Vencido el plazo, la Dirección puede liquidar de oficio y el "
            "contratista pierde la iniciativa sobre saldos, reajustes y gastos generales reclamados.",
            riesgo_por_plazo(hoy, vence, p.alerta_previa_dias),
            TipoAccion.CARGA_DOCUMENTO,
            "Preparar y presentar la propuesta de liquidación con todos los saldos y claims.",
            fecha_limite=vence,
        )
    ]


def regla_restitucion_financiera(c: Contrato, hoy: date) -> list[Alerta]:
    liq = c.liquidacion
    if not liq:
        return []
    hallazgos = []
    if not liq.incluye_devolucion_garantia_fiel_cumplimiento:
        hallazgos.append("no incluye la devolución íntegra de la garantía de fiel cumplimiento")
    if not liq.incluye_saldo_retenciones:
        hallazgos.append("no incluye la devolución del saldo de retenciones")
    if liq.litigios_pendientes:
        hallazgos.append("existen litigios pendientes")
    if liq.multas_impagas:
        hallazgos.append(f"existen multas impagas por ${liq.multas_impagas:,}".replace(",", "."))
    if liq.saldo_en_contra_fisco:
        hallazgos.append(f"existe saldo en contra del Fisco por ${liq.saldo_en_contra_fisco:,}".replace(",", "."))
    if not hallazgos:
        return []
    return [
        alerta(
            "F5_RESTITUCION_FINANCIERA",
            F,
            "DTO150_DEVOLUCION_GARANTIA",
            "Estado de liquidación con observaciones",
            "La liquidación " + "; ".join(hallazgos) + ".",
            Riesgo.ALTO,
            TipoAccion.BORRADOR_CARTA,
            "Formular observaciones a la liquidación antes de suscribirla; no protocolizar sin reserva de derechos.",
        )
    ]


def regla_cierre_boveda(c: Contrato, hoy: date) -> list[Alerta]:
    if not c.hitos.fecha_protocolizacion_liquidacion or c.sello:
        return []
    return [
        alerta(
            "F5_SELLAR_BOVEDA",
            F,
            "RCOP_LIQUIDACION",
            "Liquidación protocolizada: sellar expediente",
            "Sellar criptográficamente el expediente (Libro de Obras, anexos, claims y pagos) como resguardo "
            "probatorio ante la Contraloría General de la República.",
            Riesgo.MEDIO,
            TipoAccion.NOTIFICACION,
            "Ejecutar el cierre de bóveda.",
        )
    ]


def regla_vigencia_garantias(c: Contrato, hoy: date) -> list[Alerta]:
    if c.hitos.fecha_resolucion_liquidacion:
        return []
    return [
        alerta(
            "TX_GARANTIA_POR_VENCER",
            Fase.EJECUCION,
            "RCOP_GARANTIAS",
            f"Garantía {g.proposito.value} de {g.emisor} " + ("vencida" if hoy > g.vencimiento else "por vencer"),
            f"Vence el {g.vencimiento:%d-%m-%Y} y el contrato no está liquidado. Una garantía vencida habilita "
            "la retención de pagos y puede gatillar el término anticipado.",
            Riesgo.ALTO,
            TipoAccion.NOTIFICACION,
            "Renovar o endosar ampliación de vigencia antes del vencimiento.",
            fecha_limite=g.vencimiento,
        )
        for g in c.garantias
        if g.proposito == PropositoGarantia.FIEL_CUMPLIMIENTO and (g.vencimiento - hoy).days <= 30
    ]


REGLAS = [regla_propuesta_liquidacion, regla_restitucion_financiera, regla_cierre_boveda, regla_vigencia_garantias]
