"""Pruebas HTTP reales con FastAPI TestClient y el SVM incluido en artifacts."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from src.api.app import app


def test_health_and_docs():
    with TestClient(app) as client:
        assert client.get("/api/health").json()["estado"] == "ok"
        assert client.get("/openapi.json").status_code == 200


def test_sessions_isolated_and_reset():
    with TestClient(app) as client:
        a = client.post("/api/chat", json={"mensaje": "Dame información de Gold Ship"})
        assert a.status_code == 200, a.text
        sid_a = a.json()["session_id"]
        sid_b = client.post("/api/chat", json={"mensaje": "Hola"}).json()["session_id"]
        assert sid_a != sid_b
        assert a.json()["contexto"]["slots"]["personaje"] is not None
        assert client.post("/api/chat", json={"session_id": sid_a, "mensaje": "Y sus aptitudes?"}).status_code == 200
        assert client.post("/api/chat", json={"session_id": sid_b, "mensaje": "Hola"}).json()["contexto"]["slots"]["personaje"] is None
        assert client.post("/api/reset", json={"session_id": sid_a}).status_code == 200
        after = client.post("/api/chat", json={"session_id": sid_a, "mensaje": "Hola"}).json()
        assert after["contexto"]["slots"]["personaje"] is None
        assert after["contexto"]["turnos"] == 1


def test_validation_and_unknown_session():
    with TestClient(app) as client:
        for body in [{"mensaje": " "}, {"mensaje": "x" * 2001}, {"mensaje": "hola", "session_id": "no-es-uuid"}]:
            assert client.post("/api/chat", json=body).status_code == 422
        assert client.post("/api/chat", json={"mensaje": "hola", "session_id": "00000000-0000-4000-8000-000000000001"}).status_code == 404
        assert client.post("/api/reset", json={"session_id": "00000000-0000-4000-8000-000000000001"}).status_code == 404


def test_cors_allowed_and_disallowed():
    with TestClient(app) as client:
        allowed = client.options("/api/chat", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"})
        assert allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"
        blocked = client.options("/api/chat", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
        assert blocked.headers.get("access-control-allow-origin") is None


def run():
    test_health_and_docs()
    test_sessions_isolated_and_reset()
    test_validation_and_unknown_session()
    test_cors_allowed_and_disallowed()
    print("OK: 4 grupos de pruebas HTTP superados")


if __name__ == "__main__":
    run()
