from datetime import date

from lexobra.calendario import es_habil, sumar_dias_corridos, sumar_dias_habiles, sumar_meses


def test_viernes_santo_es_inhabil():
    assert not es_habil(date(2026, 4, 3))


def test_dias_habiles_saltan_fin_de_semana_y_feriados():
    # Lunes 14-09-2026 + 5 hábiles: 15, 16, 17, (18 y 19 feriados, 20 domingo), 21, 22.
    assert sumar_dias_habiles(date(2026, 9, 14), 5) == date(2026, 9, 22)


def test_dias_corridos_vencen_en_habil_siguiente():
    # 01-08-2026 + 14 = 15-08-2026 (feriado, sábado) -> lunes 17-08-2026.
    assert sumar_dias_corridos(date(2026, 8, 1), 14) == date(2026, 8, 17)


def test_sumar_meses_ajusta_fin_de_mes():
    assert sumar_meses(date(2026, 1, 31), 1) == date(2026, 2, 28)
