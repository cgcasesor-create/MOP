"""Cómputo de plazos: días corridos, días hábiles administrativos y meses.

Días hábiles según Ley 19.880 Art. 25: excluye sábados, domingos y festivos.
Se incluyen los feriados nacionales de fecha fija y Viernes/Sábado Santo. Los
feriados trasladables (Ley 19.668) y los feriados regionales o especiales deben
cargarse como ``feriados_extra``.
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable
from datetime import date, timedelta

_FERIADOS_FIJOS = {
    (1, 1), (5, 1), (5, 21), (6, 20), (7, 16), (8, 15),
    (9, 18), (9, 19), (10, 12), (10, 31), (11, 1), (12, 8), (12, 25),
}


def _domingo_pascua(anio: int) -> date:
    # Algoritmo gregoriano anónimo (Meeus/Jones/Butcher).
    a = anio % 19
    b, c = divmod(anio, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(anio, mes, dia)


def es_feriado(dia: date, feriados_extra: Iterable[date] = ()) -> bool:
    if (dia.month, dia.day) in _FERIADOS_FIJOS:
        return True
    pascua = _domingo_pascua(dia.year)
    if dia in (pascua - timedelta(days=2), pascua - timedelta(days=1)):
        return True
    return dia in set(feriados_extra)


def es_habil(dia: date, feriados_extra: Iterable[date] = ()) -> bool:
    return dia.weekday() < 5 and not es_feriado(dia, feriados_extra)


def sumar_dias_habiles(inicio: date, dias: int, feriados_extra: Iterable[date] = ()) -> date:
    """Fecha en que vence un plazo de ``dias`` hábiles contado desde el día siguiente a ``inicio``."""
    extra = set(feriados_extra)
    actual = inicio
    restantes = dias
    while restantes > 0:
        actual += timedelta(days=1)
        if es_habil(actual, extra):
            restantes -= 1
    return actual


def sumar_dias_corridos(inicio: date, dias: int) -> date:
    """Plazo de días corridos; si vence en día inhábil se prorroga al hábil siguiente."""
    vence = inicio + timedelta(days=dias)
    while not es_habil(vence):
        vence += timedelta(days=1)
    return vence


def sumar_meses(inicio: date, meses: int) -> date:
    mes_total = inicio.month - 1 + meses
    anio = inicio.year + mes_total // 12
    mes = mes_total % 12 + 1
    dia = min(inicio.day, calendar.monthrange(anio, mes)[1])
    return date(anio, mes, dia)
