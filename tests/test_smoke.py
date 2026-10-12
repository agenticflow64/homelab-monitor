"""Интеграционный smoke: реальный docker-стек, тестовый алерт через webhook.

Поднимает стек (если не поднят), ждёт healthcheck всех сервисов, отправляет
в агент тестовый алерт curl-ом и ждёт объяснение в ленте /api/alerts.

Запуск: make smoke  (нужен .env с GLM_API_KEY для живой LLM; без неё агент
пойдёт в fallback и тест всё равно пройдёт — проверяется конвейер).
"""
import json
import os
import subprocess
import time
import urllib.request

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENT = "http://localhost:8081"
PROMETHEUS = "http://localhost:9090"
ALERTMANAGER = "http://localhost:9093"

pytestmark = pytest.mark.integration

SERVICES = [
    ("alert-agent", f"{AGENT}/healthz"),
    ("prometheus", f"{PROMETHEUS}/-/ready"),
    ("alertmanager", f"{ALERTMANAGER}/-/ready"),
    ("grafana", "http://localhost:3001/api/health"),
    ("loki", "http://localhost:3100/ready"),
]


def http_get(url: str, timeout: float = 5.0):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.status, response.read()


def compose(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "compose", "--profile", "full", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )


def wait_http(url: str, deadline_s: float = 180.0) -> None:
    deadline = time.monotonic() + deadline_s
    last_error = None
    while time.monotonic() < deadline:
        try:
            status, _ = http_get(url)
            if status == 200:
                return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(3)
    raise AssertionError(f"{url} not ready: {last_error}")


def test_stack_up_all_services_healthy():
    result = compose("up", "-d", "--build")
    assert result.returncode == 0, result.stderr
    for name, url in SERVICES:
        wait_http(url)
        assert True, f"{name} healthy"


def test_test_alert_produces_explanation():
    payload = {
        "version": "4",
        "status": "firing",
        "receiver": "agent",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "ServiceDown",
                    "instance": "loki:3100",
                    "job": "loki",
                    "severity": "critical",
                },
                "annotations": {
                    "summary": "Сервис недоступен (scrape failed)",
                    "description": "Цель loki/loki:3100 не отвечает более 1 минуты",
                },
                "startsAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "endsAt": "0001-01-01T00:00:00Z",
                "fingerprint": "smoke-test-1",
            }
        ],
    }
    request = urllib.request.Request(
        f"{AGENT}/webhook",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        assert response.status == 200
        body = json.loads(response.read())
    assert body["processing"] == ["ServiceDown"]

    # Ждём появления записи в ленте с непустым объяснением (LLM до 90s + ретраи)
    deadline = time.monotonic() + 180
    entry = None
    while time.monotonic() < deadline:
        _, raw = http_get(f"{AGENT}/api/alerts")
        alerts = json.loads(raw)
        matches = [a for a in alerts if a.get("alertname") == "ServiceDown"]
        if matches and matches[0].get("explanation", {}).get("text"):
            entry = matches[0]
            break
        time.sleep(3)
    assert entry is not None, "explanation not found in feed"
    text = entry["explanation"]["text"].upper()
    for header in ("ЧТО СЛУЧИЛОСЬ", "ВЕРОЯТНАЯ ПРИЧИНА", "ЧТО ПРОВЕРИТЬ"):
        assert header in text, f"missing section {header}"
    assert entry["channels"]["console"] is True
    assert entry["timings_ms"]["total"] > 0
    print(f"\nmodel={entry['explanation']['model']} "
          f"latency={entry['explanation']['latency_s']}s "
          f"total={entry['timings_ms']['total']}ms")
