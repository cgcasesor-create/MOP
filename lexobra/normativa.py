"""Catálogo normativo y parámetros legales del motor LexObra 360.

Cada regla del motor cita una entrada de este catálogo. Las entradas llevan un
``estado_verificacion`` explícito porque la plataforma emite alertas con
consecuencias jurídicas: una cifra o un número de artículo no contrastado con
el texto consolidado vigente en LeyChile (DS 75/2004 MOP y sus modificaciones,
incluidos DS 156/2024 y Decreto 150/2026) debe revisarse por la gerencia legal
antes de pasar a producción.

Los umbrales numéricos viven en ``ParametrosLegales`` y pueden sobrescribirse
por contrato, porque las Bases Administrativas pueden fijar valores distintos
(p. ej. una retención mayor o un tope de subcontratación menor).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EstadoVerificacion(str, Enum):
    VERIFICADO = "verificado"
    """Contrastado con extractos del texto oficial (LeyChile/BCN)."""

    PENDIENTE = "pendiente_verificacion"
    """Tomado del diseño funcional; requiere cotejo con el texto consolidado."""

    DISCREPANTE = "discrepante"
    """Las fuentes consultadas contradicen el valor del diseño funcional."""


class Norma(BaseModel):
    codigo: str
    cuerpo: str
    articulo: str
    materia: str
    estado_verificacion: EstadoVerificacion
    nota: str = ""

    def cita(self) -> str:
        return f"{self.cuerpo}, {self.articulo}"


RCOP = "DS 75/2004 MOP (RCOP)"

CATALOGO: dict[str, Norma] = {
    n.codigo: n
    for n in [
        Norma(
            codigo="RCOP_PERFECCIONAMIENTO",
            cuerpo=RCOP,
            articulo="Art. 90",
            materia="Suscripción ante notario de tres transcripciones de la resolución y protocolización de una",
            estado_verificacion=EstadoVerificacion.VERIFICADO,
            nota="El plazo en días debe confirmarse con el texto consolidado; se parametriza.",
        ),
        Norma(
            codigo="DFL850_TRANSCRIPCIONES",
            cuerpo="DFL 850/1997 MOP",
            articulo="Art. 89",
            materia="Suscripción notarial y protocolización de decretos o resoluciones que aprueban contratos",
            estado_verificacion=EstadoVerificacion.VERIFICADO,
        ),
        Norma(
            codigo="RCOP_GARANTIAS",
            cuerpo=RCOP,
            articulo="Art. 96",
            materia="Garantías de fiel cumplimiento",
            estado_verificacion=EstadoVerificacion.PENDIENTE,
        ),
        Norma(
            codigo="DFL850_CAUCION",
            cuerpo="DFL 850/1997 MOP",
            articulo="Art. 109",
            materia="Caución de fiel cumplimiento: boleta bancaria o póliza de seguro",
            estado_verificacion=EstadoVerificacion.VERIFICADO,
        ),
        Norma(
            codigo="RCOP_ENTREGA_TERRENO",
            cuerpo=RCOP,
            articulo="Art. 137",
            materia="Entrega de terreno",
            estado_verificacion=EstadoVerificacion.PENDIENTE,
        ),
        Norma(
            codigo="RCOP_SUBCONTRATOS",
            cuerpo=RCOP,
            articulo="Art. 101",
            materia="Subcontratación: autorización de la Dirección, responsabilidad del contratista y tope",
            estado_verificacion=EstadoVerificacion.DISCREPANTE,
            nota=(
                "El diseño funcional indica un tope del 50% (DS 156). El extracto de "
                "LeyChile consultado indica 30% del valor total del contrato, salvo "
                "excepción justificada por el Director. Se usa 30% por defecto (criterio "
                "conservador) y es parametrizable por contrato."
            ),
        ),
        Norma(
            codigo="RCOP_RETENCIONES",
            cuerpo=RCOP,
            articulo="Art. 158",
            materia="Retención del 10% de cada estado de pago hasta completar el 5% del contrato con sus aumentos",
            estado_verificacion=EstadoVerificacion.VERIFICADO,
            nota="Las Bases pueden fijar un porcentaje superior.",
        ),
        Norma(
            codigo="RCOP_PRO_FORMA",
            cuerpo=RCOP,
            articulo="Art. 102",
            materia="Valores pro forma pagados a costo real comprobado",
            estado_verificacion=EstadoVerificacion.PENDIENTE,
        ),
        Norma(
            codigo="RCOP_AUMENTO_PARTIDAS",
            cuerpo=RCOP,
            articulo="Aumento de cantidades (serie de precios unitarios)",
            materia="Aumento de cantidades hasta 30% por partida y 30% del valor inicial del contrato",
            estado_verificacion=EstadoVerificacion.VERIFICADO,
            nota="Número de artículo por confirmar.",
        ),
        Norma(
            codigo="RCOP_TOPE_MODIFICACIONES",
            cuerpo=RCOP,
            articulo="Art. 106",
            materia="Tope conjunto del 35% del monto inicial reajustado para aumentos, obras nuevas y extraordinarias",
            estado_verificacion=EstadoVerificacion.VERIFICADO,
            nota=(
                "Alcanzado el 35% corresponde liquidar el contrato y licitar lo pendiente "
                "como obra nueva. El 'hasta 50% con fundamentación especial' del diseño "
                "funcional no aparece en el extracto consultado y NO se implementa."
            ),
        ),
        Norma(
            codigo="RCOP_PARALIZACION",
            cuerpo=RCOP,
            articulo="Paralización y aumento de plazo",
            materia="Paralización por causa no imputable, aumento de plazo y gastos generales",
            estado_verificacion=EstadoVerificacion.PENDIENTE,
        ),
        Norma(
            codigo="RCOP_RECEPCION_PROVISORIA",
            cuerpo=RCOP,
            articulo="Recepción provisoria",
            materia="Designación de comisión receptora e informe",
            estado_verificacion=EstadoVerificacion.PENDIENTE,
        ),
        Norma(
            codigo="RCOP_RECEPCION_DEFINITIVA",
            cuerpo=RCOP,
            articulo="Recepción definitiva",
            materia="Recepción definitiva al vencer el plazo de garantía",
            estado_verificacion=EstadoVerificacion.PENDIENTE,
        ),
        Norma(
            codigo="RCOP_LIQUIDACION",
            cuerpo=RCOP,
            articulo="Liquidación del contrato",
            materia="Liquidación, suscripción y protocolización de la resolución",
            estado_verificacion=EstadoVerificacion.PENDIENTE,
        ),
        Norma(
            codigo="DTO150_DEVOLUCION_GARANTIA",
            cuerpo="Decreto 150/2026 MOP",
            articulo="Devolución garantía de fiel cumplimiento",
            materia="Devolución ligada a la resolución totalmente tramitada que aprueba la liquidación",
            estado_verificacion=EstadoVerificacion.VERIFICADO,
        ),
        Norma(
            codigo="CT_SUBCONTRATACION",
            cuerpo="Código del Trabajo (Ley 20.123)",
            articulo="Arts. 183-A a 183-E",
            materia="Responsabilidad solidaria/subsidiaria y derecho de retención del mandante",
            estado_verificacion=EstadoVerificacion.PENDIENTE,
        ),
        Norma(
            codigo="LEY_KARIN",
            cuerpo="Ley 21.643",
            articulo="Protocolo de prevención",
            materia="Prevención del acoso laboral, sexual y violencia en el trabajo",
            estado_verificacion=EstadoVerificacion.VERIFICADO,
        ),
        Norma(
            codigo="LEY_DELITOS_ECONOMICOS",
            cuerpo="Ley 21.595",
            articulo="Delitos económicos y ambientales",
            materia="Responsabilidad penal y de personas jurídicas por delitos ambientales",
            estado_verificacion=EstadoVerificacion.VERIFICADO,
        ),
    ]
}


def norma(codigo: str) -> Norma:
    return CATALOGO[codigo]


class ParametrosLegales(BaseModel):
    """Umbrales del motor. Sobrescribibles por contrato según sus Bases."""

    plazo_protocolizacion_dias: int = Field(15, description="Días corridos (verificar Art. 90)")
    plazo_garantia_fiel_cumplimiento_dias: int = Field(15, description="Días corridos (verificar Art. 96)")
    plazo_entrega_terreno_dias: int = Field(15, description="Días corridos desde perfeccionamiento, según Bases")
    tope_subcontratacion_pct: float = 30.0
    alerta_subcontratacion_pct: float = 25.0
    retencion_pct_por_estado_pago: float = 10.0
    retencion_tope_pct_contrato: float = 5.0
    canje_vigencia_extra_meses: int = 12
    tope_aumento_partida_pct: float = 30.0
    tope_modificaciones_pct: float = 35.0
    alerta_modificaciones_pct: float = 30.0
    plazo_designacion_comision_dias_habiles: int = 20
    plazo_informe_comision_dias_habiles: int = 20
    plazo_garantia_obra_meses: int = 12
    plazo_propuesta_liquidacion_dias: int = 30
    alerta_previa_dias: int = 5
