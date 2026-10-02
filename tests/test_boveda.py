import hashlib
from datetime import date

import pytest

from lexobra import boveda
from lexobra.modelos import EntradaExpediente


def _doc(n: int) -> EntradaExpediente:
    return EntradaExpediente(categoria="libro_obras", titulo=f"Folio {n}", fecha=date(2026, 1, n), contenido_sha256=hashlib.sha256(str(n).encode()).hexdigest())


def test_sello_detecta_alteracion(contrato):
    for n in range(1, 6):
        boveda.agregar_documento(contrato, _doc(n))
    sello = boveda.sellar(contrato, date(2029, 1, 10))
    assert sello.cantidad_documentos == 5 and boveda.verificar(contrato)

    contrato.expediente[2].contenido_sha256 = "0" * 64
    assert not boveda.verificar(contrato)


def test_expediente_sellado_no_admite_documentos(contrato):
    boveda.sellar(contrato, date(2029, 1, 10))
    with pytest.raises(boveda.ExpedienteSellado):
        boveda.agregar_documento(contrato, _doc(1))
