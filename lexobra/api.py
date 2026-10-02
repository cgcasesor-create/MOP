"""API REST de LexObra 360.

Ejecutar: ``uvicorn lexobra.api:app --reload``. El parámetro ``hoy`` (fecha
de evaluación) es opcional y permite simular escenarios; por defecto es la
fecha del servidor. El repositorio es en memoria: sustituir ``Repositorio``
por una implementación persistente antes de producción.
"""

from __future__ import annotations

from datetime import date

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import boveda, motor
from .ia import Consultor, ConsultaRechazada, RespuestaConsulta
from .modelos import (
    Alerta,
    CertificadoLaboral,
    Contrato,
    EntradaExpediente,
    EstadoPago,
    Garantia,
    Hitos,
    Liquidacion,
    Modificacion,
    MovimientoTierra,
    PagoSubcontrato,
    Paralizacion,
    RecepcionParcial,
    Riesgo,
    SelloBoveda,
    Subcontrato,
    Trabajador,
)
from .normativa import CATALOGO, Norma, ParametrosLegales


class Repositorio:
    def __init__(self) -> None:
        self.contratos: dict[str, Contrato] = {}


repo = Repositorio()
consultor = Consultor()

app = FastAPI(
    title="LexObra 360",
    version="0.1.0",
    description="Gemelo Digital Legal de contratos de obras públicas (DS 75/2004 MOP).",
)


@app.exception_handler(motor.BloqueoLegal)
def _bloqueo(_, exc: motor.BloqueoLegal) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"bloqueo": True, "motivo": exc.motivo, "alertas": [a.model_dump(mode="json") for a in exc.alertas]},
    )


@app.exception_handler(boveda.ExpedienteSellado)
def _sellado(_, exc: boveda.ExpedienteSellado) -> JSONResponse:
    return JSONResponse(status_code=409, content={"bloqueo": True, "motivo": str(exc)})


def fecha_eval(hoy: date | None = None) -> date:
    return hoy or date.today()


def obtener(contrato_id: str) -> Contrato:
    c = repo.contratos.get(contrato_id)
    if c is None:
        raise HTTPException(404, "Contrato no encontrado")
    return c


def editable(c: Contrato = Depends(obtener)) -> Contrato:
    if c.sello:
        raise boveda.ExpedienteSellado("Contrato cerrado y sellado: no admite modificaciones.")
    return c


# --------------------------------------------------------------------------- #
# Contratos
# --------------------------------------------------------------------------- #


class ContratoCrear(BaseModel):
    codigo: str
    nombre: str
    contratista_rut: str
    contratista_razon_social: str
    monto_inicial: int
    plazo_dias: int
    gastos_generales: int | None = None
    mandante: str = "Dirección de Vialidad - MOP"
    parametros: ParametrosLegales | None = None
    hitos: Hitos | None = None


@app.post("/contratos", status_code=201)
def crear_contrato(datos: ContratoCrear) -> Contrato:
    campos = datos.model_dump(exclude_none=True)
    c = Contrato(**campos)
    repo.contratos[c.id] = c
    return c


@app.get("/contratos")
def listar_contratos(hoy: date = Depends(fecha_eval)) -> list[dict]:
    return [
        {k: v for k, v in motor.resumen(c, hoy).items() if k != "alertas"} | {"nombre": c.nombre}
        for c in repo.contratos.values()
    ]


@app.get("/contratos/{contrato_id}")
def ver_contrato(c: Contrato = Depends(obtener)) -> Contrato:
    return c


@app.get("/contratos/{contrato_id}/resumen")
def resumen(c: Contrato = Depends(obtener), hoy: date = Depends(fecha_eval)) -> dict:
    return motor.resumen(c, hoy)


@app.get("/contratos/{contrato_id}/alertas")
def alertas(
    c: Contrato = Depends(obtener),
    hoy: date = Depends(fecha_eval),
    riesgo: Riesgo | None = None,
    solo_bloqueos: bool = False,
) -> list[Alerta]:
    return [
        a for a in motor.evaluar(c, hoy) if (riesgo is None or a.riesgo == riesgo) and (not solo_bloqueos or a.bloqueo)
    ]


@app.patch("/contratos/{contrato_id}/hitos")
def actualizar_hitos(cambios: Hitos, c: Contrato = Depends(editable), hoy: date = Depends(fecha_eval)) -> dict:
    c.hitos = c.hitos.model_copy(update=cambios.model_dump(exclude_unset=True))
    return motor.resumen(c, hoy)


@app.patch("/contratos/{contrato_id}/parametros")
def actualizar_parametros(parametros: ParametrosLegales, c: Contrato = Depends(editable)) -> ParametrosLegales:
    c.parametros = c.parametros.model_copy(update=parametros.model_dump(exclude_unset=True))
    return c.parametros


# --------------------------------------------------------------------------- #
# Fase 1: compliance laboral
# --------------------------------------------------------------------------- #


@app.post("/contratos/{contrato_id}/certificados-laborales", status_code=201)
def cargar_certificado(cert: CertificadoLaboral, c: Contrato = Depends(editable)) -> CertificadoLaboral:
    c.certificados_laborales.append(cert)
    return cert


@app.post("/contratos/{contrato_id}/trabajadores", status_code=201)
def registrar_trabajador(t: Trabajador, c: Contrato = Depends(editable)) -> Trabajador:
    if any(x.rut == t.rut for x in c.trabajadores):
        raise HTTPException(409, "Trabajador ya registrado")
    t.habilitado_faena = False
    c.trabajadores.append(t)
    return t


@app.post("/contratos/{contrato_id}/trabajadores/{rut}/habilitar")
def habilitar_trabajador(rut: str, c: Contrato = Depends(editable)) -> Trabajador:
    motor.habilitar_trabajador(c, rut)
    return next(t for t in c.trabajadores if t.rut == rut)


# --------------------------------------------------------------------------- #
# Fase 2: ejecución
# --------------------------------------------------------------------------- #


@app.post("/contratos/{contrato_id}/subcontratos", status_code=201)
def registrar_subcontrato(s: Subcontrato, c: Contrato = Depends(editable), hoy: date = Depends(fecha_eval)) -> dict:
    alertas = motor.registrar_subcontrato(c, s, hoy)
    return {"subcontrato": s, "alertas": alertas}


class EstadoPagoCrear(BaseModel):
    numero: int
    periodo: str
    monto_obra: int
    fecha: date
    pagos_subcontratos: list[PagoSubcontrato] = []


@app.post("/contratos/{contrato_id}/estados-pago", status_code=201)
def registrar_estado_pago(datos: EstadoPagoCrear, c: Contrato = Depends(editable)) -> EstadoPago:
    return motor.registrar_estado_pago(c, datos.numero, datos.periodo, datos.monto_obra, datos.fecha, datos.pagos_subcontratos)


@app.post("/contratos/{contrato_id}/movimientos-tierra", status_code=201)
def registrar_movimiento(m: MovimientoTierra, c: Contrato = Depends(editable)) -> MovimientoTierra:
    c.movimientos_tierra.append(m)
    return m


@app.post("/contratos/{contrato_id}/garantias", status_code=201)
def registrar_garantia(g: Garantia, c: Contrato = Depends(editable)) -> Garantia:
    c.garantias.append(g)
    return g


# --------------------------------------------------------------------------- #
# Fase 3: modificaciones y claims
# --------------------------------------------------------------------------- #


@app.post("/contratos/{contrato_id}/modificaciones", status_code=201)
def registrar_modificacion(m: Modificacion, c: Contrato = Depends(editable), hoy: date = Depends(fecha_eval)) -> dict:
    alertas = motor.registrar_modificacion(c, m, hoy)
    return {"modificacion": m, "alertas": alertas}


@app.post("/contratos/{contrato_id}/paralizaciones", status_code=201)
def registrar_paralizacion(p: Paralizacion, c: Contrato = Depends(editable)) -> Paralizacion:
    c.paralizaciones.append(p)
    return p


# --------------------------------------------------------------------------- #
# Fases 4 y 5: recepción, liquidación y cierre
# --------------------------------------------------------------------------- #


@app.post("/contratos/{contrato_id}/recepciones-parciales", status_code=201)
def registrar_recepcion_parcial(r: RecepcionParcial, c: Contrato = Depends(editable)) -> RecepcionParcial:
    c.recepciones_parciales.append(r)
    return r


@app.put("/contratos/{contrato_id}/liquidacion")
def registrar_liquidacion(liq: Liquidacion, c: Contrato = Depends(editable), hoy: date = Depends(fecha_eval)) -> dict:
    c.liquidacion = liq
    return motor.resumen(c, hoy)


@app.post("/contratos/{contrato_id}/expediente", status_code=201)
def agregar_documento(e: EntradaExpediente, c: Contrato = Depends(obtener)) -> EntradaExpediente:
    boveda.agregar_documento(c, e)
    return e


@app.post("/contratos/{contrato_id}/cierre")
def cerrar_boveda(c: Contrato = Depends(obtener), hoy: date = Depends(fecha_eval)) -> SelloBoveda:
    if not c.hitos.fecha_protocolizacion_liquidacion:
        raise motor.BloqueoLegal("No se puede sellar el expediente antes de protocolizar la liquidación.")
    return boveda.sellar(c, hoy)


@app.get("/contratos/{contrato_id}/cierre/verificacion")
def verificar_boveda(c: Contrato = Depends(obtener)) -> dict:
    return {"sellado": c.sello is not None, "integro": boveda.verificar(c), "sello": c.sello}


# --------------------------------------------------------------------------- #
# Consulta asistida por IA y catálogo normativo
# --------------------------------------------------------------------------- #


class Consulta(BaseModel):
    pregunta: str


@app.post("/contratos/{contrato_id}/consultas")
def consultar(q: Consulta, c: Contrato = Depends(obtener), hoy: date = Depends(fecha_eval)) -> RespuestaConsulta:
    try:
        return consultor.consultar(c, q.pregunta, hoy)
    except ConsultaRechazada as exc:
        raise HTTPException(422, str(exc)) from exc


@app.get("/normativa")
def catalogo_normativo() -> list[Norma]:
    return list(CATALOGO.values())
