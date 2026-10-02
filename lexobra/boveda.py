"""Cierre de bóveda: sello de integridad del expediente mediante árbol de Merkle SHA-256.

El sello prueba que ningún documento del expediente fue alterado, agregado o
eliminado después del cierre: basta recalcular la raíz. No sustituye la firma
electrónica avanzada (Ley 19.799) ni un sellado de tiempo de un prestador
acreditado; para oponibilidad plena se recomienda firmar o sellar
temporalmente la raíz resultante con un prestador acreditado.
"""

from __future__ import annotations

import hashlib
from datetime import date

from .modelos import Contrato, EntradaExpediente, SelloBoveda


class ExpedienteSellado(Exception):
    pass


def hash_hoja(e: EntradaExpediente) -> str:
    material = f"{e.id}|{e.categoria}|{e.titulo}|{e.fecha.isoformat()}|{e.contenido_sha256}"
    return hashlib.sha256(material.encode()).hexdigest()


def raiz_merkle(hojas: list[str]) -> str:
    if not hojas:
        return hashlib.sha256(b"").hexdigest()
    nivel = hojas
    while len(nivel) > 1:
        if len(nivel) % 2:
            nivel = nivel + [nivel[-1]]
        nivel = [
            hashlib.sha256(bytes.fromhex(nivel[i]) + bytes.fromhex(nivel[i + 1])).hexdigest()
            for i in range(0, len(nivel), 2)
        ]
    return nivel[0]


def agregar_documento(c: Contrato, entrada: EntradaExpediente) -> None:
    if c.sello:
        raise ExpedienteSellado("El expediente está sellado; no admite nuevos documentos.")
    c.expediente.append(entrada)


def sellar(c: Contrato, hoy: date) -> SelloBoveda:
    if c.sello:
        raise ExpedienteSellado("El expediente ya fue sellado.")
    hojas = [hash_hoja(e) for e in c.expediente]
    c.sello = SelloBoveda(fecha=hoy, raiz_merkle=raiz_merkle(hojas), cantidad_documentos=len(hojas), hashes_hoja=hojas)
    return c.sello


def verificar(c: Contrato) -> bool:
    if not c.sello:
        return False
    hojas = [hash_hoja(e) for e in c.expediente]
    return hojas == c.sello.hashes_hoja and raiz_merkle(hojas) == c.sello.raiz_merkle
