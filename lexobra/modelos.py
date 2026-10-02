"""Modelo de datos del Gemelo Digital Legal de un contrato de obra pública.

Montos en pesos chilenos (enteros). Cuando el RCOP exige comparar contra el
valor inicial "reajustado", el usuario debe cargar los montos ya reajustados
(el motor no consulta índices de reajuste).
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, Field

from .normativa import EstadoVerificacion, ParametrosLegales


def _id() -> str:
    return uuid4().hex[:12]


# --------------------------------------------------------------------------- #
# Enumeraciones
# --------------------------------------------------------------------------- #


class Fase(str, Enum):
    PERFECCIONAMIENTO = "fase_1_perfeccionamiento"
    EJECUCION = "fase_2_3_ejecucion_y_modificaciones"
    RECEPCION = "fase_4_recepcion"
    LIQUIDACION = "fase_5_liquidacion"
    CERRADO = "cerrado"


class Riesgo(str, Enum):
    BAJO = "Bajo"
    MEDIO = "Medio"
    ALTO = "Alto"


class TipoAccion(str, Enum):
    BORRADOR_CARTA = "borrador_carta"
    ANOTACION_LIBRO = "anotacion_libro_obras"
    BLOQUEO = "bloqueo_sistema"
    NOTIFICACION = "notificacion_interna"
    CARGA_DOCUMENTO = "requerir_carga_documento"


class TipoCertificadoLaboral(str, Enum):
    F30 = "F30"
    F30_1 = "F30-1"


class RolTrabajador(str, Enum):
    TRABAJADOR = "trabajador"
    PREVENCIONISTA = "prevencionista"


class TipoModificacion(str, Enum):
    AUMENTO_OBRA = "aumento_obra"
    AUMENTO_PARTIDA = "aumento_cantidad_partida"
    DISMINUCION_OBRA = "disminucion_obra"
    OBRA_EXTRAORDINARIA = "obra_extraordinaria"
    OBRA_NUEVA = "obra_nueva"
    MATERIALES_NO_CONSIDERADOS = "materiales_no_considerados"


class CausaParalizacion(str, Enum):
    CLIMA = "clima"
    HALLAZGO_ARQUEOLOGICO = "hallazgo_arqueologico"
    FUERZA_MAYOR_OTRA = "fuerza_mayor_otra"
    ORDEN_INSPECCION = "orden_inspeccion_fiscal"


class TipoGarantia(str, Enum):
    BOLETA = "boleta_bancaria"
    POLIZA = "poliza_seguro"
    CERTIFICADO_FIANZA = "certificado_fianza"


class PropositoGarantia(str, Enum):
    FIEL_CUMPLIMIENTO = "fiel_cumplimiento"
    CANJE_RETENCIONES = "canje_retenciones"


# --------------------------------------------------------------------------- #
# Salida del motor
# --------------------------------------------------------------------------- #


class PlanAccion(BaseModel):
    tipo: TipoAccion
    descripcion: str
    borrador: str | None = None


class Alerta(BaseModel):
    """Formato de salida obligatorio del motor."""

    codigo_regla: str
    fase: Fase
    titulo: str
    detalle: str
    riesgo: Riesgo
    articulo_rcop: str
    ley_especial_cruzada: str | None = None
    plan_accion: PlanAccion
    bloqueo: bool = False
    fecha_limite: date | None = None
    verificacion_normativa: EstadoVerificacion


# --------------------------------------------------------------------------- #
# Componentes del contrato
# --------------------------------------------------------------------------- #


class Hitos(BaseModel):
    fecha_toma_razon: date | None = None
    fecha_ingreso_oficina_partes: date | None = None
    fecha_protocolizacion: date | None = None
    fecha_entrega_terreno_programada: date | None = None
    fecha_entrega_terreno_real: date | None = None
    fecha_solicitud_termino: date | None = None
    fecha_designacion_comision: date | None = None
    fecha_informe_comision: date | None = None
    fecha_recepcion_provisoria: date | None = None
    fecha_recepcion_definitiva: date | None = None
    fecha_propuesta_liquidacion: date | None = None
    fecha_resolucion_liquidacion: date | None = None
    fecha_protocolizacion_liquidacion: date | None = None


class CertificadoLaboral(BaseModel):
    id: str = Field(default_factory=_id)
    empresa_rut: str
    tipo: TipoCertificadoLaboral
    periodo: str = Field(description="Periodo AAAA-MM que acredita")
    fecha_emision: date
    sin_deudas: bool = True


class Trabajador(BaseModel):
    rut: str
    nombre: str
    empresa_rut: str
    rol: RolTrabajador = RolTrabajador.TRABAJADOR
    firma_protocolo_ley_karin: bool = False
    recepcion_riohs: bool = False
    habilitado_faena: bool = False


class Subcontrato(BaseModel):
    id: str = Field(default_factory=_id)
    empresa_rut: str
    razon_social: str
    monto: int
    autorizado_por_direccion: bool = False
    fecha: date | None = None


class PagoSubcontrato(BaseModel):
    subcontrato_id: str
    monto: int
    liberado: bool = False
    motivo_bloqueo: str | None = None


class EstadoPago(BaseModel):
    numero: int
    periodo: str = Field(description="Periodo AAAA-MM")
    monto_obra: int
    fecha: date
    retencion: int = 0
    monto_liquido: int = 0
    pagos_subcontratos: list[PagoSubcontrato] = Field(default_factory=list)


class Modificacion(BaseModel):
    id: str = Field(default_factory=_id)
    tipo: TipoModificacion
    descripcion: str
    monto: int = Field(description="Monto reajustado; positivo (las disminuciones también se cargan positivas)")
    fecha: date
    partida: str | None = None
    monto_partida_original: int | None = None
    es_pro_forma: bool = False
    resolucion: str | None = None


class Paralizacion(BaseModel):
    id: str = Field(default_factory=_id)
    causa: CausaParalizacion
    descripcion: str
    fecha_inicio: date
    fecha_fin: date | None = None
    evidencia_fotografica: list[str] = Field(default_factory=list)
    asiento_libro_registrado: bool = False


class MovimientoTierra(BaseModel):
    id: str = Field(default_factory=_id)
    descripcion: str
    fecha: date
    volumen_m3: float | None = None
    rca_numero: str | None = None


class Garantia(BaseModel):
    id: str = Field(default_factory=_id)
    tipo: TipoGarantia
    proposito: PropositoGarantia
    monto: int
    emisor: str
    fecha_entrega: date
    vencimiento: date


class RecepcionParcial(BaseModel):
    tramo: str
    fecha_solicitud: date
    fecha_recepcion: date | None = None


class Liquidacion(BaseModel):
    incluye_devolucion_garantia_fiel_cumplimiento: bool = False
    incluye_saldo_retenciones: bool = False
    litigios_pendientes: bool = False
    multas_impagas: int = 0
    saldo_en_contra_fisco: int = 0


class EntradaExpediente(BaseModel):
    """Documento incorporado al expediente (Libro de Obras, anexos, claims...)."""

    id: str = Field(default_factory=_id)
    categoria: str
    titulo: str
    fecha: date
    contenido_sha256: str = Field(description="Hash SHA-256 del archivo original")


class SelloBoveda(BaseModel):
    fecha: date
    algoritmo: str = "sha256-merkle"
    raiz_merkle: str
    cantidad_documentos: int
    hashes_hoja: list[str]


class Contrato(BaseModel):
    id: str = Field(default_factory=_id)
    codigo: str
    nombre: str
    mandante: str = "Dirección de Vialidad - MOP"
    contratista_rut: str
    contratista_razon_social: str
    monto_inicial: int
    plazo_dias: int
    gastos_generales: int | None = Field(None, description="Gastos generales totales ofertados")
    parametros: ParametrosLegales = Field(default_factory=ParametrosLegales)
    hitos: Hitos = Field(default_factory=Hitos)
    certificados_laborales: list[CertificadoLaboral] = Field(default_factory=list)
    trabajadores: list[Trabajador] = Field(default_factory=list)
    subcontratos: list[Subcontrato] = Field(default_factory=list)
    estados_pago: list[EstadoPago] = Field(default_factory=list)
    modificaciones: list[Modificacion] = Field(default_factory=list)
    paralizaciones: list[Paralizacion] = Field(default_factory=list)
    movimientos_tierra: list[MovimientoTierra] = Field(default_factory=list)
    garantias: list[Garantia] = Field(default_factory=list)
    recepciones_parciales: list[RecepcionParcial] = Field(default_factory=list)
    liquidacion: Liquidacion | None = None
    expediente: list[EntradaExpediente] = Field(default_factory=list)
    sello: SelloBoveda | None = None
