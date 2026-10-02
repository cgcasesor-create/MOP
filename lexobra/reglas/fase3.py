"""Fase 3: Modificaciones, claims y valores pro forma."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from .. import borradores, calculos
from ..modelos import Alerta, Contrato, Fase, Riesgo, TipoAccion, TipoModificacion
from . import alerta

F = Fase.EJECUCION


def regla_tope_modificaciones(c: Contrato, hoy: date) -> list[Alerta]:
    p = c.parametros
    porcentaje = calculos.pct(calculos.modificaciones_netas(c), c.monto_inicial)
    if porcentaje < p.alerta_modificaciones_pct:
        return []
    alcanzado = porcentaje >= p.tope_modificaciones_pct
    return [
        alerta(
            "F3_TOPE_MODIFICACIONES",
            F,
            "RCOP_TOPE_MODIFICACIONES",
            "Tope conjunto de modificaciones " + ("alcanzado" if alcanzado else "próximo"),
            f"Aumentos, obras nuevas/extraordinarias y materiales no considerados, netos de disminuciones: "
            f"{porcentaje}% del monto inicial (tope {p.tope_modificaciones_pct}%). "
            + (
                "Alcanzado el tope corresponde liquidar el contrato y contratar lo pendiente como obra nueva."
                if alcanzado
                else "Evaluar si las próximas modificaciones caben en el margen disponible."
            ),
            Riesgo.ALTO if alcanzado else Riesgo.MEDIO,
            TipoAccion.BLOQUEO if alcanzado else TipoAccion.NOTIFICACION,
            "Bloquear nuevas modificaciones e iniciar liquidación anticipada."
            if alcanzado
            else "Informar a Gerencia Legal y a la Inspección Fiscal el margen remanente.",
            bloqueo=alcanzado,
        )
    ]


def regla_aumento_partidas(c: Contrato, hoy: date) -> list[Alerta]:
    p = c.parametros
    alertas = []
    por_partida: dict[str, int] = defaultdict(int)
    originales: dict[str, int] = {}
    for m in c.modificaciones:
        if m.tipo == TipoModificacion.AUMENTO_PARTIDA and not m.es_pro_forma and m.partida:
            por_partida[m.partida] += m.monto
            if m.monto_partida_original:
                originales[m.partida] = m.monto_partida_original
    for partida, aumento in por_partida.items():
        original = originales.get(partida)
        if original and calculos.pct(aumento, original) > p.tope_aumento_partida_pct:
            alertas.append(
                alerta(
                    "F3_TOPE_PARTIDA",
                    F,
                    "RCOP_AUMENTO_PARTIDAS",
                    f"Partida {partida}: aumento de cantidades sobre el tope",
                    f"Aumento de {calculos.pct(aumento, original)}% sobre la partida original "
                    f"(tope {p.tope_aumento_partida_pct}%). El exceso no puede pagarse a precios unitarios "
                    "del contrato; requiere convenio como obra extraordinaria.",
                    Riesgo.ALTO,
                    TipoAccion.BLOQUEO,
                    "Tramitar el exceso como obra extraordinaria con nuevo precio convenido.",
                    bloqueo=True,
                )
            )
    total = sum(por_partida.values())
    if calculos.pct(total, c.monto_inicial) > p.tope_aumento_partida_pct:
        alertas.append(
            alerta(
                "F3_TOPE_AUMENTO_CANTIDADES",
                F,
                "RCOP_AUMENTO_PARTIDAS",
                "Aumentos de cantidades sobre el 30% del valor inicial",
                f"Total aumentos de cantidades (sin pro forma): {calculos.pct(total, c.monto_inicial)}%.",
                Riesgo.ALTO,
                TipoAccion.BLOQUEO,
                "Detener nuevos aumentos de cantidades a precios unitarios.",
                bloqueo=True,
            )
        )
    return alertas


def regla_pro_forma(c: Contrato, hoy: date) -> list[Alerta]:
    pro_forma = [m for m in c.modificaciones if m.es_pro_forma]
    if not pro_forma:
        return []
    monto = sum(m.monto for m in pro_forma)
    return [
        alerta(
            "F3_VALORES_PRO_FORMA",
            F,
            "RCOP_PRO_FORMA",
            f"{len(pro_forma)} partidas pro forma segregadas",
            f"Monto pro forma: ${monto:,}".replace(",", ".")
            + ". Se pagan a costo real comprobado y no computan en el tope del 30% de aumento de cantidades.",
            Riesgo.BAJO,
            TipoAccion.CARGA_DOCUMENTO,
            "Exigir facturas y respaldos de costo real antes de incluirlas en un estado de pago.",
        )
    ]


def regla_paralizaciones(c: Contrato, hoy: date) -> list[Alerta]:
    alertas = []
    gg_diario = c.gastos_generales // c.plazo_dias if c.gastos_generales and c.plazo_dias else None
    for p in c.paralizaciones:
        if not p.evidencia_fotografica:
            alertas.append(
                alerta(
                    "F3_PARALIZACION_SIN_EVIDENCIA",
                    F,
                    "RCOP_PARALIZACION",
                    f"Paralización del {p.fecha_inicio:%d-%m-%Y} sin evidencia fotográfica",
                    "Sin registro fotográfico fechado el claim por aumento de plazo y gastos generales "
                    "carece de prueba.",
                    Riesgo.ALTO,
                    TipoAccion.CARGA_DOCUMENTO,
                    "Cargar fotografías fechadas y georreferenciadas antes de presentar el claim.",
                    ley_especial="Código Civil, Art. 45 (caso fortuito o fuerza mayor)",
                )
            )
        if not p.asiento_libro_registrado:
            alertas.append(
                alerta(
                    "F3_PARALIZACION_SIN_ASIENTO",
                    F,
                    "RCOP_PARALIZACION",
                    f"Paralización del {p.fecha_inicio:%d-%m-%Y} sin asiento en Libro de Obras",
                    "La constancia oportuna en el Libro de Obras es la base probatoria del claim.",
                    Riesgo.MEDIO,
                    TipoAccion.ANOTACION_LIBRO,
                    "Registrar el asiento sugerido en el Libro de Obras.",
                    ley_especial="Código Civil, Art. 45 (caso fortuito o fuerza mayor)",
                    borrador=borradores.asiento_paralizacion(c, p, gg_diario, hoy),
                )
            )
    return alertas


REGLAS = [regla_tope_modificaciones, regla_aumento_partidas, regla_pro_forma, regla_paralizaciones]
