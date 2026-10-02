import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from lexobra import api
from lexobra.ia import Consultor


@pytest.fixture
def client():
    api.repo.contratos.clear()
    return TestClient(api.app)


def _crear(client) -> str:
    r = client.post(
        "/contratos",
        json={
            "codigo": "VIA-2026-002",
            "nombre": "Conservación global Ruta 68",
            "contratista_rut": "76.123.456-7",
            "contratista_razon_social": "Constructora Vial SpA",
            "monto_inicial": 5_000_000_000,
            "plazo_dias": 365,
            "hitos": {"fecha_ingreso_oficina_partes": "2026-01-06"},
        },
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_flujo_alertas_y_bloqueos(client):
    cid = _crear(client)
    r = client.get(f"/contratos/{cid}/alertas", params={"hoy": "2026-01-25", "solo_bloqueos": True})
    assert {"F1_PROTOCOLIZACION", "F1_GARANTIA_FIEL_CUMPLIMIENTO"} <= {a["codigo_regla"] for a in r.json()}

    r = client.post(f"/contratos/{cid}/modificaciones", json={"tipo": "obra_extraordinaria", "descripcion": "x", "monto": 2_000_000_000, "fecha": "2026-03-01"})
    assert r.status_code == 409 and r.json()["bloqueo"]

    r = client.post(f"/contratos/{cid}/trabajadores", json={"rut": "1-9", "nombre": "Juan Soto", "empresa_rut": "76.123.456-7"})
    assert r.status_code == 201
    r = client.post(f"/contratos/{cid}/trabajadores/1-9/habilitar")
    assert r.status_code == 409 and "Ley 21.643" in r.json()["motivo"]


def test_cierre_requiere_liquidacion_protocolizada_y_sella(client):
    cid = _crear(client)
    client.post(f"/contratos/{cid}/expediente", json={"categoria": "libro_obras", "titulo": "Folio 1", "fecha": "2026-02-01", "contenido_sha256": "a" * 64})
    assert client.post(f"/contratos/{cid}/cierre").status_code == 409

    client.patch(f"/contratos/{cid}/hitos", json={"fecha_protocolizacion_liquidacion": "2028-03-01"})
    r = client.post(f"/contratos/{cid}/cierre", params={"hoy": "2028-03-02"})
    assert r.status_code == 200 and r.json()["cantidad_documentos"] == 1
    assert client.get(f"/contratos/{cid}/cierre/verificacion").json()["integro"]
    assert client.post(f"/contratos/{cid}/garantias", json={}).status_code == 409


def test_consulta_ia_usa_formato_obligatorio(client, monkeypatch):
    cid = _crear(client)
    respuesta = {
        "sintesis_ejecutiva": "Protocolizar hoy.",
        "riesgo_legal_asignado": "Alto",
        "articulo_rcop": "DS 75/2004 MOP (RCOP), Art. 90",
        "ley_especial_cruzada": "DFL 850/1997 MOP, Art. 89",
        "analisis_juridico": "...",
        "analisis_reputacional": "...",
        "plan_accion_inmediato": {"tipo": "bloqueo_sistema", "descripcion": "...", "borrador": "..."},
        "advertencias_verificacion": [],
    }
    llamadas = []

    def create(**kwargs):
        llamadas.append(kwargs)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=json.dumps(respuesta))])

    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    monkeypatch.setattr(api, "consultor", Consultor(client=fake))

    r = client.post(f"/contratos/{cid}/consultas", params={"hoy": "2026-01-25"}, json={"pregunta": "¿Qué riesgo corremos?"})
    assert r.status_code == 200 and r.json()["riesgo_legal_asignado"] == "Alto"
    enviado = llamadas[0]["messages"][0]["content"]
    assert "F1_PROTOCOLIZACION" in enviado and "<consulta>" in enviado
    assert llamadas[0]["output_config"]["format"]["type"] == "json_schema"
