from datetime import date

import pytest

from lexobra import calculos, motor
from lexobra.modelos import (
    CausaParalizacion,
    CertificadoLaboral,
    Fase,
    Hitos,
    Liquidacion,
    Modificacion,
    MovimientoTierra,
    PagoSubcontrato,
    Paralizacion,
    Riesgo,
    Subcontrato,
    TipoAccion,
    TipoCertificadoLaboral,
    TipoModificacion,
    Trabajador,
)
from lexobra.normativa import EstadoVerificacion


def codigos(alertas):
    return {a.codigo_regla for a in alertas}


def por_codigo(alertas, codigo):
    return next(a for a in alertas if a.codigo_regla == codigo)


# ----------------------------- Fase 1 ------------------------------------- #


def test_protocolizacion_cuenta_regresiva_y_bloqueo(contrato):
    contrato.hitos = Hitos(fecha_ingreso_oficina_partes=date(2026, 1, 6))
    a = por_codigo(motor.evaluar(contrato, date(2026, 1, 8)), "F1_PROTOCOLIZACION")
    assert a.riesgo == Riesgo.MEDIO and not a.bloqueo
    assert a.fecha_limite == date(2026, 1, 21)

    a = por_codigo(motor.evaluar(contrato, date(2026, 1, 22)), "F1_PROTOCOLIZACION")
    assert a.riesgo == Riesgo.ALTO and a.bloqueo
    assert a.articulo_rcop.endswith("Art. 90")


def test_atraso_entrega_terreno_genera_carta(contrato):
    contrato.hitos = Hitos(
        fecha_ingreso_oficina_partes=date(2026, 1, 6),
        fecha_entrega_terreno_programada=date(2026, 1, 20),
    )
    a = por_codigo(motor.evaluar(contrato, date(2026, 1, 30)), "F1_ATRASO_ENTREGA_TERRENO")
    assert a.plan_accion.tipo == TipoAccion.BORRADOR_CARTA
    assert "10 días de atraso" in a.plan_accion.borrador
    assert a.verificacion_normativa == EstadoVerificacion.PENDIENTE


def test_trabajador_sin_ley_karin_queda_bloqueado(contrato_en_ejecucion):
    c = contrato_en_ejecucion
    c.trabajadores.append(Trabajador(rut="11.111.111-1", nombre="Ana Pérez", empresa_rut=c.contratista_rut, recepcion_riohs=True))
    with pytest.raises(motor.BloqueoLegal, match="Ley 21.643"):
        motor.habilitar_trabajador(c, "11.111.111-1")
    c.trabajadores[0].firma_protocolo_ley_karin = True
    motor.habilitar_trabajador(c, "11.111.111-1")
    assert c.trabajadores[0].habilitado_faena


def test_fase_ejecucion_requiere_hitos_completos(contrato, contrato_en_ejecucion):
    assert motor.fase_actual(contrato_en_ejecucion) == Fase.EJECUCION
    contrato_en_ejecucion.hitos.fecha_entrega_terreno_real = None
    assert motor.fase_actual(contrato_en_ejecucion) == Fase.PERFECCIONAMIENTO


# ----------------------------- Fase 2 ------------------------------------- #


def test_retencion_10_por_ciento_hasta_tope_5(contrato_en_ejecucion):
    c = contrato_en_ejecucion  # tope 5% de 10.000 MM = 500 MM
    ep1 = motor.registrar_estado_pago(c, 1, "2026-01", 3_000_000_000, date(2026, 2, 10), [])
    assert ep1.retencion == 300_000_000
    ep2 = motor.registrar_estado_pago(c, 2, "2026-02", 3_000_000_000, date(2026, 3, 10), [])
    assert ep2.retencion == 200_000_000
    ep3 = motor.registrar_estado_pago(c, 3, "2026-03", 1_000_000_000, date(2026, 4, 10), [])
    assert ep3.retencion == 0 and ep3.monto_liquido == 1_000_000_000


def test_tope_retencion_crece_con_aumentos(contrato_en_ejecucion):
    c = contrato_en_ejecucion
    c.modificaciones.append(Modificacion(tipo=TipoModificacion.AUMENTO_OBRA, descripcion="x", monto=2_000_000_000, fecha=date(2026, 3, 1)))
    assert calculos.calcular_retencion(c, 10_000_000_000) == 600_000_000


def test_tope_subcontratacion_bloquea(contrato_en_ejecucion):
    c = contrato_en_ejecucion
    alertas = motor.registrar_subcontrato(c, Subcontrato(empresa_rut="77.1", razon_social="Asfaltos Ltda", monto=2_600_000_000, autorizado_por_direccion=True), date(2026, 3, 1))
    assert por_codigo(alertas, "F2_TOPE_SUBCONTRATACION").riesgo == Riesgo.MEDIO
    with pytest.raises(motor.BloqueoLegal, match="tope 30.0%"):
        motor.registrar_subcontrato(c, Subcontrato(empresa_rut="77.2", razon_social="Señalética SpA", monto=500_000_000), date(2026, 3, 1))


def test_tope_subcontratacion_parametrizable(contrato_en_ejecucion):
    c = contrato_en_ejecucion
    c.parametros.tope_subcontratacion_pct = 50
    motor.registrar_subcontrato(c, Subcontrato(empresa_rut="77.1", razon_social="A", monto=4_000_000_000), date(2026, 3, 1))


def test_pago_subcontratista_sin_f30_1_se_retiene(contrato_en_ejecucion):
    c = contrato_en_ejecucion
    s = Subcontrato(empresa_rut="77.1", razon_social="Asfaltos Ltda", monto=1_000_000_000, autorizado_por_direccion=True)
    motor.registrar_subcontrato(c, s, date(2026, 2, 1))
    ep = motor.registrar_estado_pago(c, 1, "2026-02", 1_000_000_000, date(2026, 3, 10), [PagoSubcontrato(subcontrato_id=s.id, monto=100_000_000)])
    assert not ep.pagos_subcontratos[0].liberado
    assert "F30-1" in ep.pagos_subcontratos[0].motivo_bloqueo
    assert "F2_PAGO_SUBCONTRATO_RETENIDO" in codigos(motor.evaluar(c, date(2026, 3, 10)))

    c.certificados_laborales.append(CertificadoLaboral(empresa_rut="77.1", tipo=TipoCertificadoLaboral.F30_1, periodo="2026-03", fecha_emision=date(2026, 4, 5)))
    ep2 = motor.registrar_estado_pago(c, 2, "2026-03", 1_000_000_000, date(2026, 4, 10), [PagoSubcontrato(subcontrato_id=s.id, monto=100_000_000)])
    assert ep2.pagos_subcontratos[0].liberado


def test_canje_retenciones_notifica_vigencia_minima(contrato_en_ejecucion):
    c = contrato_en_ejecucion
    motor.registrar_estado_pago(c, 1, "2026-01", 1_000_000_000, date(2026, 2, 10), [])
    a = por_codigo(motor.evaluar(c, date(2026, 2, 10)), "F2_OPORTUNIDAD_CANJE")
    # Entrega de terreno 20-01-2026 + 540 días = 14-07-2027, + 12 meses.
    assert "14-07-2028" in a.plan_accion.borrador


def test_movimiento_tierra_sin_rca_bloquea(contrato_en_ejecucion):
    c = contrato_en_ejecucion
    c.movimientos_tierra.append(MovimientoTierra(descripcion="Extracción de áridos en pozo lateral", fecha=date(2026, 3, 1)))
    a = por_codigo(motor.evaluar(c, date(2026, 3, 2)), "F2_MOVIMIENTO_TIERRA_SIN_RCA")
    assert a.bloqueo and "21.595" in a.ley_especial_cruzada


# ----------------------------- Fase 3 ------------------------------------- #


def test_tope_35_por_ciento_bloquea_modificacion(contrato_en_ejecucion):
    c = contrato_en_ejecucion
    hoy = date(2026, 5, 1)
    alertas = motor.registrar_modificacion(c, Modificacion(tipo=TipoModificacion.OBRA_EXTRAORDINARIA, descripcion="Muro", monto=3_200_000_000, fecha=hoy), hoy)
    assert por_codigo(alertas, "F3_TOPE_MODIFICACIONES").riesgo == Riesgo.MEDIO
    with pytest.raises(motor.BloqueoLegal, match="obra nueva"):
        motor.registrar_modificacion(c, Modificacion(tipo=TipoModificacion.AUMENTO_OBRA, descripcion="x", monto=400_000_000, fecha=hoy), hoy)


def test_disminuciones_liberan_margen(contrato_en_ejecucion):
    c = contrato_en_ejecucion
    hoy = date(2026, 5, 1)
    motor.registrar_modificacion(c, Modificacion(tipo=TipoModificacion.AUMENTO_OBRA, descripcion="a", monto=3_400_000_000, fecha=hoy), hoy)
    motor.registrar_modificacion(c, Modificacion(tipo=TipoModificacion.DISMINUCION_OBRA, descripcion="d", monto=1_000_000_000, fecha=hoy), hoy)
    motor.registrar_modificacion(c, Modificacion(tipo=TipoModificacion.AUMENTO_OBRA, descripcion="b", monto=900_000_000, fecha=hoy), hoy)
    assert calculos.pct(calculos.modificaciones_netas(c), c.monto_inicial) == 33.0


def test_pro_forma_no_computa_en_tope_de_partida(contrato_en_ejecucion):
    c = contrato_en_ejecucion
    hoy = date(2026, 5, 1)
    alertas = motor.registrar_modificacion(c, Modificacion(tipo=TipoModificacion.AUMENTO_PARTIDA, descripcion="Traslado de servicios", monto=500_000_000, partida="7.101", monto_partida_original=1_000_000_000, es_pro_forma=True, fecha=hoy), hoy)
    assert "F3_TOPE_PARTIDA" not in codigos(alertas)
    assert "F3_VALORES_PRO_FORMA" in codigos(alertas)
    alertas = motor.registrar_modificacion(c, Modificacion(tipo=TipoModificacion.AUMENTO_PARTIDA, descripcion="Carpeta asfáltica", monto=400_000_000, partida="5.408", monto_partida_original=1_000_000_000, fecha=hoy), hoy)
    assert por_codigo(alertas, "F3_TOPE_PARTIDA").bloqueo


def test_paralizacion_genera_asiento_con_gastos_generales(contrato_en_ejecucion):
    c = contrato_en_ejecucion
    c.paralizaciones.append(Paralizacion(causa=CausaParalizacion.HALLAZGO_ARQUEOLOGICO, descripcion="Hallazgo en km 112.", fecha_inicio=date(2026, 6, 1), fecha_fin=date(2026, 6, 10)))
    alertas = motor.evaluar(c, date(2026, 6, 11))
    assert por_codigo(alertas, "F3_PARALIZACION_SIN_EVIDENCIA").riesgo == Riesgo.ALTO
    asiento = por_codigo(alertas, "F3_PARALIZACION_SIN_ASIENTO").plan_accion.borrador
    # GG 1.080 MM / 540 días = 2 MM diarios x 10 días.
    assert "$2.000.000 diarios" in asiento and "$20.000.000" in asiento


# ----------------------------- Fase 4 ------------------------------------- #


def test_comision_no_designada_en_plazo(contrato_en_ejecucion):
    c = contrato_en_ejecucion
    c.hitos.fecha_solicitud_termino = date(2027, 7, 1)
    assert motor.fase_actual(c) == Fase.RECEPCION
    a = por_codigo(motor.evaluar(c, date(2027, 8, 2)), "F4_DESIGNACION_COMISION")
    assert a.fecha_limite == date(2027, 7, 30)
    assert a.riesgo == Riesgo.ALTO and a.plan_accion.borrador


def test_recepcion_definitiva_al_vencer_garantia(contrato_en_ejecucion):
    c = contrato_en_ejecucion
    c.hitos.fecha_solicitud_termino = date(2027, 7, 1)
    c.hitos.fecha_recepcion_provisoria = date(2027, 8, 15)
    assert "F4_SOLICITAR_RECEPCION_DEFINITIVA" not in codigos(motor.evaluar(c, date(2028, 6, 1)))
    a = por_codigo(motor.evaluar(c, date(2028, 8, 1)), "F4_SOLICITAR_RECEPCION_DEFINITIVA")
    assert a.fecha_limite == date(2028, 8, 15)


# ----------------------------- Fase 5 ------------------------------------- #


def test_propuesta_liquidacion_y_restitucion(contrato_en_ejecucion):
    c = contrato_en_ejecucion
    c.hitos.fecha_solicitud_termino = date(2027, 7, 1)
    c.hitos.fecha_recepcion_definitiva = date(2028, 8, 20)
    assert motor.fase_actual(c) == Fase.LIQUIDACION
    a = por_codigo(motor.evaluar(c, date(2028, 9, 25)), "F5_PROPUESTA_LIQUIDACION")
    assert a.riesgo == Riesgo.ALTO and "de oficio" in a.detalle

    c.liquidacion = Liquidacion(incluye_devolucion_garantia_fiel_cumplimiento=True, multas_impagas=5_000_000)
    a = por_codigo(motor.evaluar(c, date(2028, 9, 25)), "F5_RESTITUCION_FINANCIERA")
    assert "saldo de retenciones" in a.detalle and "$5.000.000" in a.detalle


def test_garantia_por_vencer_sin_liquidar(contrato_en_ejecucion):
    c = contrato_en_ejecucion
    assert "TX_GARANTIA_POR_VENCER" in codigos(motor.evaluar(c, date(2028, 12, 15)))
