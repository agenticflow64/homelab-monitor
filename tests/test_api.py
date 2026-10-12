"""Юнит-тесты HTTP-API агента (TestClient, без внешних вызовов)."""
import app.main as main
from app.webhook import Alert

SAMPLE = {
    "status": "firing",
    "alerts": [
        {
            "status": "firing",
            "labels": {"alertname": "ServiceDown", "job": "loki", "severity": "critical"},
            "annotations": {"summary": "Сервис недоступен"},
            "startsAt": "2026-10-12T18:00:00Z",
        }
    ],
}


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "cooldown_seconds" in body


def test_webhook_dispatches_processing(client, monkeypatch):
    calls = []

    def fake_process(alerts, received_at):
        calls.append((alerts, received_at))

    monkeypatch.setattr(main, "process_group", fake_process)
    response = client.post("/webhook", json=SAMPLE)
    assert response.status_code == 200
    body = response.json()
    assert body == {"received": 1, "processing": ["ServiceDown"]}
    assert len(calls) == 1
    alerts = calls[0][0]
    assert isinstance(alerts[0], Alert)
    assert alerts[0].alertname == "ServiceDown"


def test_webhook_skips_resolved_only(client, monkeypatch):
    monkeypatch.setattr(main, "process_group", lambda *a: None)
    resolved = {
        "status": "resolved",
        "alerts": [{**SAMPLE["alerts"][0], "status": "resolved"}],
    }
    response = client.post("/webhook", json=resolved)
    assert response.status_code == 200
    assert response.json() == {"received": 1, "processed": 0}


def test_webhook_invalid_json(client):
    response = client.post(
        "/webhook", content=b"not-json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 400
