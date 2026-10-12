"""Юнит-тесты парсера webhook-полезной нагрузки Alertmanager."""
from app.webhook import firing, format_raw, group_key, parse_alert, parse_webhook

SAMPLE_PAYLOAD = {
    "version": "4",
    "groupKey": "/alertname/HighDiskUsage",
    "status": "firing",
    "receiver": "agent",
    "alerts": [
        {
            "status": "firing",
            "labels": {
                "alertname": "HighDiskUsage",
                "instance": "node_exporter:9100",
                "job": "node_exporter",
                "mountpoint": "/rootfs",
                "severity": "warning",
            },
            "annotations": {
                "summary": "Диск заполнен более чем на 92%",
                "description": "Файловая система /rootfs: занято 93.4%",
            },
            "startsAt": "2026-10-12T18:00:00Z",
            "endsAt": "0001-01-01T00:00:00Z",
            "fingerprint": "abc123",
        },
        {
            "status": "resolved",
            "labels": {"alertname": "ServiceDown", "job": "loki", "severity": "critical"},
            "annotations": {"summary": "Сервис недоступен"},
            "startsAt": "2026-10-12T17:50:00Z",
            "endsAt": "2026-10-12T17:58:00Z",
            "fingerprint": "def456",
        },
    ],
}


def test_parse_webhook_extracts_alerts():
    alerts = parse_webhook(SAMPLE_PAYLOAD)
    assert len(alerts) == 2
    first = alerts[0]
    assert first.alertname == "HighDiskUsage"
    assert first.severity == "warning"
    assert first.instance == "node_exporter:9100"
    assert first.summary == "Диск заполнен более чем на 92%"
    assert first.fingerprint == "abc123"


def test_parse_webhook_bad_payloads():
    assert parse_webhook(None) == []
    assert parse_webhook({}) == []
    assert parse_webhook({"alerts": "not-a-list"}) == []
    assert parse_webhook({"alerts": [42, {"labels": {"alertname": "X"}}]}) is not None


def test_parse_alert_falls_back_to_unknown():
    alert = parse_alert({})
    assert alert.alertname == "UnknownAlert"
    assert alert.status == "firing"


def test_firing_filters_resolved():
    alerts = parse_webhook(SAMPLE_PAYLOAD)
    firing_only = firing(alerts)
    assert [a.alertname for a in firing_only] == ["HighDiskUsage"]


def test_group_key_is_stable():
    a = parse_alert(SAMPLE_PAYLOAD["alerts"][0])
    assert group_key(a) == "HighDiskUsage/node_exporter:9100"


def test_format_raw_contains_essentials():
    raw = format_raw(parse_alert(SAMPLE_PAYLOAD["alerts"][0]))
    assert "HighDiskUsage" in raw
    assert "WARNING" in raw
    assert "mountpoint=/rootfs" in raw
    assert "startsAt" in raw
