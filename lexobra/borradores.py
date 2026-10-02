"""Borradores de cartas y asientos de Libro de Obras generados por el motor.

Son textos base para revisión del Administrador de Contrato o la Gerencia
Legal; nunca se envían ni se anotan sin validación humana.
"""

from __future__ import annotations

from datetime import date

from .modelos import Contrato, Paralizacion


def _f(d: date | None) -> str:
    return d.strftime("%d-%m-%Y") if d else "[fecha]"


def _pesos(monto: int) -> str:
    return "$" + f"{monto:,}".replace(",", ".")


def _encabezado(c: Contrato, destinatario: str, materia: str) -> str:
    return (
        f"Señor(a)\n{destinatario}\n{c.mandante}\nPresente\n\n"
        f"REF.: Contrato \"{c.nombre}\" (código {c.codigo}).\n"
        f"MAT.: {materia}\n\n"
    )


def _firma(c: Contrato) -> str:
    return (
        "\nSin otro particular, saluda atentamente,\n\n"
        f"{c.contratista_razon_social}\nRUT {c.contratista_rut}\n"
        "p.p. Representante legal"
    )


def carta_atraso_entrega_terreno(c: Contrato, programada: date, hoy: date) -> str:
    dias = (hoy - programada).days
    return (
        _encabezado(c, "Inspector(a) Fiscal", "Deja constancia de atraso no imputable en la entrega de terreno.")
        + f"Por medio de la presente, dejamos constancia de que a la fecha ({_f(hoy)}) la entrega de terreno, "
        f"programada para el {_f(programada)}, no se ha materializado, acumulando {dias} días de atraso "
        "por causas no imputables a esta empresa contratista.\n\n"
        "En consecuencia, y conforme al Reglamento para Contratos de Obras Públicas (DS 75/2004 MOP), "
        "solicitamos:\n"
        "1. Tener presente que el plazo contractual no puede computarse en perjuicio del contratista "
        "mientras no se efectúe la entrega de terreno.\n"
        "2. Reservar desde ya el derecho a solicitar la prórroga de plazo y la compensación de gastos "
        "generales que correspondan.\n"
        "3. Fijar a la brevedad una nueva fecha cierta de entrega, dejando constancia en el Libro de Obras.\n"
        + _firma(c)
    )


def carta_designacion_comision(c: Contrato, solicitud: date, vencimiento: date) -> str:
    return (
        _encabezado(c, "Director(a) de Vialidad", "Solicita designación de Comisión de Recepción Provisoria.")
        + f"Con fecha {_f(solicitud)} esta empresa comunicó el término de los trabajos y solicitó la "
        f"recepción provisoria. El plazo para designar la comisión receptora venció el {_f(vencimiento)} "
        "sin que conste su designación.\n\n"
        "Solicitamos disponer la designación inmediata de la Comisión, dejando constancia de que el "
        "período transcurrido no es imputable al contratista para efectos de multas ni de plazo.\n"
        + _firma(c)
    )


def carta_informe_comision(c: Contrato, designacion: date, vencimiento: date) -> str:
    return (
        _encabezado(c, "Presidente(a) Comisión de Recepción", "Solicita emisión de informe de recepción.")
        + f"La Comisión fue designada con fecha {_f(designacion)} y el plazo para emitir su informe venció "
        f"el {_f(vencimiento)}. Solicitamos su emisión a la brevedad, reiterando que el retraso no es "
        "imputable al contratista.\n"
        + _firma(c)
    )


def solicitud_recepcion_definitiva(c: Contrato, fecha_rp: date | None, vencimiento_garantia: date) -> str:
    return (
        _encabezado(c, "Director(a) de Vialidad", "Solicita Recepción Definitiva.")
        + f"Habiéndose otorgado la recepción provisoria el {_f(fecha_rp)} y venciendo el plazo de garantía de "
        f"las obras el {_f(vencimiento_garantia)}, solicitamos se disponga la Recepción Definitiva del "
        "contrato y la designación de la comisión respectiva.\n"
        + _firma(c)
    )


def asiento_paralizacion(c: Contrato, p: Paralizacion, gg_diario: int | None, hoy: date) -> str:
    fin = p.fecha_fin or hoy
    dias = (fin - p.fecha_inicio).days + 1
    texto = (
        f"LIBRO DE OBRAS — Contrato {c.codigo}\nFecha: {_f(hoy)}\n\n"
        f"El contratista deja constancia de la paralización de faenas desde el {_f(p.fecha_inicio)}"
        + (f" hasta el {_f(p.fecha_fin)}" if p.fecha_fin else " a la fecha, sin término")
        + f" ({dias} días), por causa: {p.causa.value.replace('_', ' ')}. {p.descripcion}\n"
        f"Se acompañan {len(p.evidencia_fotografica)} registros fotográficos fechados y georreferenciados.\n"
        "Se reserva el derecho a solicitar aumento de plazo por los días de paralización"
    )
    if gg_diario:
        texto += (
            f" y el pago de gastos generales proporcionales, estimados en {_pesos(gg_diario)} diarios, "
            f"total {_pesos(gg_diario * dias)} a la fecha"
        )
    return texto + ".\nSe solicita al Inspector Fiscal tomar conocimiento y pronunciarse."


def notificacion_canje(c: Contrato, retenido: int, vigencia_minima: date) -> str:
    return (
        f"A: Gerencia de Finanzas\nRE: Oportunidad de canje de retenciones — Contrato {c.codigo}\n\n"
        f"Retenciones acumuladas: {_pesos(retenido)}. Es posible solicitar su canje por boleta de garantía "
        f"o póliza por igual monto, con vigencia mínima hasta el {_f(vigencia_minima)} (plazo del contrato "
        f"más {c.parametros.canje_vigencia_extra_meses} meses). Evaluar costo financiero del documento "
        "frente al costo de capital inmovilizado."
    )
