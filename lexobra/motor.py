"""Motor del Gemelo Digital Legal: fase, alertas y operaciones con bloqueo.

Las alertas y bloqueos son deterministas: los calcula este motor a partir de
reglas parametrizadas, nunca el modelo de lenguaje. La capa de IA
(``lexobra.ia``) sólo redacta y explica sobre la base del estado que entrega
el motor.
"""

from __future__ import annotations

from datetime import date

from . import calculos
from .modelos import (
    Alerta,
    Contrato,
    EstadoPago,
    Fase,
    Modificacion,
    PagoSubcontrato,
    PropositoGarantia,
    Riesgo,
    Subcontrato,
    TipoModificacion,
    TipoCertificadoLaboral,
)
from .reglas import fase1, fase2, fase3, fase4, fase5

REGLAS = fase1.REGLAS + fase2.REGLAS + fase3.REGLAS + fase4.REGLAS + fase5.REGLAS

_ORDEN_RIESGO = {Riesgo.ALTO: 0, Riesgo.MEDIO: 1, Riesgo.BAJO: 2}


class BloqueoLegal(Exception):
    """Operación rechazada por una regla de cumplimiento."""

    def __init__(self, motivo: str, alertas: list[Alerta] | None = None):
        super().__init__(motivo)
        self.motivo = motivo
        self.alertas = alertas or []


def fase_actual(c: Contrato) -> Fase:
    h = c.hitos
    if c.sello:
        return Fase.CERRADO
    if h.fecha_recepcion_definitiva:
        return Fase.LIQUIDACION
    if h.fecha_solicitud_termino:
        return Fase.RECEPCION
    tiene_garantia = any(g.proposito == PropositoGarantia.FIEL_CUMPLIMIENTO for g in c.garantias)
    if h.fecha_protocolizacion and tiene_garantia and h.fecha_entrega_terreno_real:
        return Fase.EJECUCION
    return Fase.PERFECCIONAMIENTO


def evaluar(c: Contrato, hoy: date) -> list[Alerta]:
    if c.sello:
        return []
    alertas = [a for regla in REGLAS for a in regla(c, hoy)]
    return sorted(alertas, key=lambda a: (_ORDEN_RIESGO[a.riesgo], a.fecha_limite or date.max))


def resumen(c: Contrato, hoy: date) -> dict:
    alertas = evaluar(c, hoy)
    return {
        "contrato_id": c.id,
        "codigo": c.codigo,
        "fase": fase_actual(c),
        "valor_vigente": calculos.valor_vigente(c),
        "modificaciones_netas_pct": calculos.pct(calculos.modificaciones_netas(c), c.monto_inicial),
        "subcontratacion_pct": calculos.pct(calculos.total_subcontratado(c), calculos.valor_vigente(c)),
        "retenciones_acumuladas": calculos.retenciones_acumuladas(c),
        "avance_financiero_pct": calculos.avance_financiero_pct(c),
        "alertas_por_riesgo": {r.value: sum(1 for a in alertas if a.riesgo == r) for r in Riesgo},
        "bloqueos_activos": sum(1 for a in alertas if a.bloqueo),
        "alertas": alertas,
    }


# --------------------------------------------------------------------------- #
# Operaciones con control preventivo
# --------------------------------------------------------------------------- #


def registrar_subcontrato(c: Contrato, s: Subcontrato, hoy: date) -> list[Alerta]:
    p = c.parametros
    nuevo_total = calculos.total_subcontratado(c) + s.monto
    porcentaje = calculos.pct(nuevo_total, calculos.valor_vigente(c))
    if porcentaje > p.tope_subcontratacion_pct:
        raise BloqueoLegal(
            f"El subcontrato elevaría la subcontratación a {porcentaje}% del contrato "
            f"(tope {p.tope_subcontratacion_pct}%). Requiere excepción fundada del Director y "
            "actualizar el parámetro del contrato."
        )
    c.subcontratos.append(s)
    return fase2.regla_tope_subcontratacion(c, hoy) + fase2.regla_subcontratos_no_autorizados(c, hoy)


def registrar_modificacion(c: Contrato, m: Modificacion, hoy: date) -> list[Alerta]:
    if m.tipo in calculos.AUMENTOS:
        p = c.parametros
        porcentaje = calculos.pct(calculos.modificaciones_netas(c) + m.monto, c.monto_inicial)
        if porcentaje > p.tope_modificaciones_pct:
            raise BloqueoLegal(
                f"La modificación llevaría el total neto a {porcentaje}% del monto inicial "
                f"(tope {p.tope_modificaciones_pct}%). Corresponde liquidar y contratar lo pendiente "
                "como obra nueva."
            )
    if m.tipo == TipoModificacion.AUMENTO_PARTIDA and not m.es_pro_forma and not m.partida:
        raise BloqueoLegal("Un aumento de cantidades debe identificar la partida y su monto original.")
    c.modificaciones.append(m)
    return fase3.regla_tope_modificaciones(c, hoy) + fase3.regla_aumento_partidas(c, hoy) + fase3.regla_pro_forma(c, hoy)


def _f30_1_al_dia(c: Contrato, empresa_rut: str, periodo: str) -> bool:
    return any(
        cert.empresa_rut == empresa_rut
        and cert.tipo == TipoCertificadoLaboral.F30_1
        and cert.periodo == periodo
        and cert.sin_deudas
        for cert in c.certificados_laborales
    )


def registrar_estado_pago(
    c: Contrato,
    numero: int,
    periodo: str,
    monto_obra: int,
    fecha: date,
    pagos_subcontratos: list[PagoSubcontrato],
) -> EstadoPago:
    if any(ep.numero == numero for ep in c.estados_pago):
        raise BloqueoLegal(f"El estado de pago N°{numero} ya existe.")
    subcontratos = {s.id: s for s in c.subcontratos}
    pagos = []
    for pago in pagos_subcontratos:
        s = subcontratos.get(pago.subcontrato_id)
        if s is None:
            raise BloqueoLegal(f"Subcontrato {pago.subcontrato_id} no registrado.")
        motivos = []
        if not s.autorizado_por_direccion:
            motivos.append("Subcontrato sin autorización de la Dirección")
        if not _f30_1_al_dia(c, s.empresa_rut, periodo):
            motivos.append(f"Sin F30-1 sin deudas del periodo {periodo}")
        pagos.append(
            PagoSubcontrato(
                subcontrato_id=s.id,
                monto=pago.monto,
                liberado=not motivos,
                motivo_bloqueo="; ".join(motivos) + "." if motivos else None,
            )
        )
    retencion = calculos.calcular_retencion(c, monto_obra)
    ep = EstadoPago(
        numero=numero,
        periodo=periodo,
        monto_obra=monto_obra,
        fecha=fecha,
        retencion=retencion,
        monto_liquido=monto_obra - retencion,
        pagos_subcontratos=pagos,
    )
    c.estados_pago.append(ep)
    return ep


def habilitar_trabajador(c: Contrato, rut: str) -> None:
    t = next((t for t in c.trabajadores if t.rut == rut), None)
    if t is None:
        raise BloqueoLegal(f"Trabajador {rut} no registrado.")
    motivos = fase1.motivos_inhabilitacion(c, t)
    if motivos:
        raise BloqueoLegal("Ingreso a faena bloqueado: " + "; ".join(motivos) + ".")
    t.habilitado_faena = True
