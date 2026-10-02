from datetime import date

import pytest

from lexobra.modelos import (
    CertificadoLaboral,
    Contrato,
    Garantia,
    Hitos,
    PropositoGarantia,
    TipoCertificadoLaboral,
    TipoGarantia,
)

CONTRATISTA = "76.123.456-7"


@pytest.fixture
def contrato() -> Contrato:
    return Contrato(
        codigo="VIA-2026-001",
        nombre="Reposición Ruta 5 Sur, tramo km 100-120",
        contratista_rut=CONTRATISTA,
        contratista_razon_social="Constructora Vial SpA",
        monto_inicial=10_000_000_000,
        plazo_dias=540,
        gastos_generales=1_080_000_000,
    )


@pytest.fixture
def contrato_en_ejecucion(contrato: Contrato) -> Contrato:
    contrato.hitos = Hitos(
        fecha_toma_razon=date(2026, 1, 5),
        fecha_ingreso_oficina_partes=date(2026, 1, 6),
        fecha_protocolizacion=date(2026, 1, 15),
        fecha_entrega_terreno_programada=date(2026, 1, 20),
        fecha_entrega_terreno_real=date(2026, 1, 20),
    )
    contrato.garantias.append(
        Garantia(
            tipo=TipoGarantia.BOLETA,
            proposito=PropositoGarantia.FIEL_CUMPLIMIENTO,
            monto=500_000_000,
            emisor="Banco Estado",
            fecha_entrega=date(2026, 1, 14),
            vencimiento=date(2028, 12, 31),
        )
    )
    for tipo in TipoCertificadoLaboral:
        contrato.certificados_laborales.append(
            CertificadoLaboral(empresa_rut=CONTRATISTA, tipo=tipo, periodo="2026-01", fecha_emision=date(2026, 2, 5))
        )
    return contrato
