"""Fase 1: Perfeccionamiento y arranque (día 0 a 30)."""

from __future__ import annotations

from datetime import date

from .. import borradores
from ..calendario import sumar_dias_corridos
from ..modelos import (
    Alerta,
    Contrato,
    Fase,
    PropositoGarantia,
    Riesgo,
    TipoAccion,
    TipoCertificadoLaboral,
    Trabajador,
)
from . import alerta, riesgo_por_plazo

F = Fase.PERFECCIONAMIENTO


def _cuenta_regresiva(hoy: date, vence: date) -> str:
    dias = (vence - hoy).days
    return f"vencido hace {-dias} días" if dias < 0 else f"quedan {dias} días"


def regla_protocolizacion(c: Contrato, hoy: date) -> list[Alerta]:
    h = c.hitos
    if not h.fecha_ingreso_oficina_partes or h.fecha_protocolizacion:
        return []
    vence = sumar_dias_corridos(h.fecha_ingreso_oficina_partes, c.parametros.plazo_protocolizacion_dias)
    vencido = hoy > vence
    return [
        alerta(
            "F1_PROTOCOLIZACION",
            F,
            "RCOP_PERFECCIONAMIENTO",
            "Protocolización de la resolución de adjudicación pendiente",
            f"Vence el {vence:%d-%m-%Y} ({_cuenta_regresiva(hoy, vence)}). Sin suscripción ante notario de las "
            "tres transcripciones y protocolización de una, la adjudicación puede quedar sin efecto con "
            "cobro de la garantía de seriedad de la oferta.",
            riesgo_por_plazo(hoy, vence, c.parametros.alerta_previa_dias),
            TipoAccion.BLOQUEO if vencido else TipoAccion.NOTIFICACION,
            "Agendar notaría y protocolizar de inmediato; bloquear avance a ejecución hasta acreditarlo.",
            ley_especial="DFL 850/1997 MOP, Art. 89",
            bloqueo=vencido,
            fecha_limite=vence,
        )
    ]


def regla_garantia_fiel_cumplimiento(c: Contrato, hoy: date) -> list[Alerta]:
    h = c.hitos
    if not h.fecha_ingreso_oficina_partes:
        return []
    if any(g.proposito == PropositoGarantia.FIEL_CUMPLIMIENTO for g in c.garantias):
        return []
    vence = sumar_dias_corridos(h.fecha_ingreso_oficina_partes, c.parametros.plazo_garantia_fiel_cumplimiento_dias)
    vencido = hoy > vence
    return [
        alerta(
            "F1_GARANTIA_FIEL_CUMPLIMIENTO",
            F,
            "RCOP_GARANTIAS",
            "Garantía de fiel cumplimiento no entregada",
            f"Vence el {vence:%d-%m-%Y} ({_cuenta_regresiva(hoy, vence)}). Riesgo de caducidad del contrato "
            "y pérdida de la garantía de seriedad.",
            riesgo_por_plazo(hoy, vence, c.parametros.alerta_previa_dias),
            TipoAccion.CARGA_DOCUMENTO,
            "Cargar boleta bancaria o póliza (DFL 850 Art. 109) por el monto y vigencia exigidos en las Bases.",
            ley_especial="DFL 850/1997 MOP, Art. 109",
            bloqueo=vencido,
            fecha_limite=vence,
        )
    ]


def regla_entrega_terreno(c: Contrato, hoy: date) -> list[Alerta]:
    h = c.hitos
    if not h.fecha_ingreso_oficina_partes:
        return []
    programada = h.fecha_entrega_terreno_programada or sumar_dias_corridos(
        h.fecha_ingreso_oficina_partes, c.parametros.plazo_entrega_terreno_dias
    )
    real = h.fecha_entrega_terreno_real
    if real and real <= programada:
        return []
    if not real and hoy <= programada:
        return []
    corte = real or hoy
    dias = (corte - programada).days
    return [
        alerta(
            "F1_ATRASO_ENTREGA_TERRENO",
            F,
            "RCOP_ENTREGA_TERRENO",
            "Atraso del MOP en la entrega de terreno",
            f"Entrega programada el {programada:%d-%m-%Y}; {dias} días de atraso no imputable al contratista. "
            "Debe dejarse constancia formal para sustentar la futura prórroga y compensación.",
            Riesgo.MEDIO if dias <= 15 else Riesgo.ALTO,
            TipoAccion.BORRADOR_CARTA,
            "Enviar carta al Inspector Fiscal y anotar en Libro de Obras.",
            borrador=borradores.carta_atraso_entrega_terreno(c, programada, corte),
            fecha_limite=programada,
        )
    ]


def _empresas_con_faena(c: Contrato) -> dict[str, str]:
    empresas = {c.contratista_rut: c.contratista_razon_social}
    empresas.update({s.empresa_rut: s.razon_social for s in c.subcontratos})
    return empresas


def certificados_faltantes(c: Contrato, empresa_rut: str) -> list[str]:
    tipos = {cert.tipo for cert in c.certificados_laborales if cert.empresa_rut == empresa_rut and cert.sin_deudas}
    return [t.value for t in TipoCertificadoLaboral if t not in tipos]


def motivos_inhabilitacion(c: Contrato, t: Trabajador) -> list[str]:
    motivos = []
    if not t.firma_protocolo_ley_karin:
        motivos.append("Falta firma del protocolo de prevención Ley 21.643 (Ley Karin)")
    if not t.recepcion_riohs:
        motivos.append("Falta recepción firmada del Reglamento Interno de Orden, Higiene y Seguridad")
    faltan = certificados_faltantes(c, t.empresa_rut)
    if faltan:
        motivos.append(f"Empleador sin certificados {', '.join(faltan)} vigentes y sin deudas")
    return motivos


def regla_compliance_laboral(c: Contrato, hoy: date) -> list[Alerta]:
    alertas = []
    for rut, nombre in _empresas_con_faena(c).items():
        faltan = certificados_faltantes(c, rut)
        if faltan:
            alertas.append(
                alerta(
                    "F1_CERTIFICADOS_LABORALES",
                    F,
                    "CT_SUBCONTRATACION",
                    f"{nombre}: faltan certificados {', '.join(faltan)}",
                    "Sin certificado de antecedentes (F30) y de cumplimiento de obligaciones laborales y "
                    "previsionales (F30-1) no se acredita la cadena laboral; el mandante responde solidariamente.",
                    Riesgo.ALTO,
                    TipoAccion.BLOQUEO,
                    "Bloquear ingreso a faena del personal de la empresa hasta cargar los certificados.",
                    ley_especial="Código del Trabajo, Arts. 183-C y 183-D (Ley 20.123)",
                    bloqueo=True,
                )
            )
    for t in c.trabajadores:
        motivos = [m for m in motivos_inhabilitacion(c, t) if not m.startswith("Empleador")]
        if motivos:
            alertas.append(
                alerta(
                    "F1_TRABAJADOR_NO_HABILITADO",
                    F,
                    "LEY_KARIN",
                    f"{t.rol.value.capitalize()} {t.nombre} ({t.rut}) no habilitado para faena",
                    "; ".join(motivos) + ".",
                    Riesgo.ALTO,
                    TipoAccion.BLOQUEO,
                    "Impedir el ingreso a faena hasta completar firmas.",
                    ley_especial="Ley 21.643 (Ley Karin); Código del Trabajo, Art. 153 (RIOHS)",
                    bloqueo=True,
                )
            )
    return alertas


REGLAS = [regla_protocolizacion, regla_garantia_fiel_cumplimiento, regla_entrega_terreno, regla_compliance_laboral]
