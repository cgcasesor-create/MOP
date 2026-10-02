"""Cálculos financieros y de plazo del contrato."""

from __future__ import annotations

from datetime import date, timedelta

from .calendario import sumar_meses
from .modelos import Contrato, PropositoGarantia, TipoModificacion

AUMENTOS = {
    TipoModificacion.AUMENTO_OBRA,
    TipoModificacion.AUMENTO_PARTIDA,
    TipoModificacion.OBRA_EXTRAORDINARIA,
    TipoModificacion.OBRA_NUEVA,
    TipoModificacion.MATERIALES_NO_CONSIDERADOS,
}


def total_aumentos(c: Contrato) -> int:
    return sum(m.monto for m in c.modificaciones if m.tipo in AUMENTOS)


def total_disminuciones(c: Contrato) -> int:
    return sum(m.monto for m in c.modificaciones if m.tipo == TipoModificacion.DISMINUCION_OBRA)


def modificaciones_netas(c: Contrato) -> int:
    """Base del tope conjunto del Art. 106: aumentos menos disminuciones convenidas."""
    return total_aumentos(c) - total_disminuciones(c)


def valor_vigente(c: Contrato) -> int:
    return c.monto_inicial + modificaciones_netas(c)


def pct(parte: int | float, total: int | float) -> float:
    return round(100.0 * parte / total, 2) if total else 0.0


def total_subcontratado(c: Contrato) -> int:
    return sum(s.monto for s in c.subcontratos)


def retenciones_acumuladas(c: Contrato) -> int:
    return sum(ep.retencion for ep in c.estados_pago)


def calcular_retencion(c: Contrato, monto_obra: int) -> int:
    """10% del estado de pago hasta completar el 5% del contrato incluidos sus aumentos (Art. 158)."""
    p = c.parametros
    tope = int(valor_vigente(c) * p.retencion_tope_pct_contrato / 100)
    saldo = max(0, tope - retenciones_acumuladas(c))
    return min(int(monto_obra * p.retencion_pct_por_estado_pago / 100), saldo)


def garantias_canje(c: Contrato) -> int:
    return sum(g.monto for g in c.garantias if g.proposito == PropositoGarantia.CANJE_RETENCIONES)


def fecha_inicio_plazo(c: Contrato) -> date | None:
    h = c.hitos
    return h.fecha_entrega_terreno_real or h.fecha_ingreso_oficina_partes


def fecha_termino_estimada(c: Contrato) -> date | None:
    inicio = fecha_inicio_plazo(c)
    return inicio + timedelta(days=c.plazo_dias) if inicio else None


def vigencia_minima_canje(c: Contrato) -> date | None:
    termino = fecha_termino_estimada(c)
    return sumar_meses(termino, c.parametros.canje_vigencia_extra_meses) if termino else None


def avance_financiero_pct(c: Contrato) -> float:
    return pct(sum(ep.monto_obra for ep in c.estados_pago), valor_vigente(c))
