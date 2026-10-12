"""Разбор полезной нагрузки webhook-ресивера Alertmanager.

Чистые функции без побочных эффектов — удобно тестировать.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Alert:
    alertname: str
    status: str
    severity: str
    summary: str
    description: str
    instance: str
    job: str
    starts_at: str
    ends_at: str
    fingerprint: str
    labels: dict = field(default_factory=dict)
    annotations: dict = field(default_factory=dict)
    value: str = ""


def _first(payload_alert: dict, *keys: str, default: str = "") -> str:
    """Значение из annotations (приоритет) или labels."""
    for source in (payload_alert.get("annotations") or {}, payload_alert.get("labels") or {}):
        for key in keys:
            if source.get(key):
                return str(source[key])
    return default


def parse_alert(payload_alert: dict) -> Alert:
    labels = dict(payload_alert.get("labels") or {})
    annotations = dict(payload_alert.get("annotations") or {})
    return Alert(
        alertname=labels.get("alertname") or "UnknownAlert",
        status=payload_alert.get("status") or "firing",
        severity=labels.get("severity") or "unknown",
        summary=_first(payload_alert, "summary"),
        description=_first(payload_alert, "description"),
        instance=labels.get("instance") or "",
        job=labels.get("job") or "",
        starts_at=payload_alert.get("startsAt") or "",
        ends_at=payload_alert.get("endsAt") or "",
        fingerprint=payload_alert.get("fingerprint") or "",
        labels=labels,
        annotations=annotations,
        value=_first(payload_alert, "value"),
    )


def parse_webhook(payload: dict) -> list[Alert]:
    """Payload Alertmanager -> список алертов. Некорректные записи пропускаются."""
    if not isinstance(payload, dict):
        return []
    raw_alerts = payload.get("alerts")
    if not isinstance(raw_alerts, list):
        return []
    alerts: list[Alert] = []
    for item in raw_alerts:
        if isinstance(item, dict):
            alerts.append(parse_alert(item))
    return alerts


def firing(alerts: list[Alert]) -> list[Alert]:
    return [a for a in alerts if a.status == "firing"]


def group_key(alert: Alert) -> str:
    """Ключ группировки всплеска: имя алерта + инстанс."""
    return f"{a_key(alert.alertname)}/{a_key(alert.instance or alert.job)}"


def a_key(value: str) -> str:
    return (value or "-").strip() or "-"


def format_raw(alert: Alert) -> str:
    """Сырой алерт в компактном человекочитаемом виде (левая колонка ленты)."""
    lines = [
        f"[{alert.severity.upper()}] {alert.alertname}",
    ]
    if alert.summary:
        lines.append(alert.summary)
    if alert.description:
        lines.append(alert.description)
    if alert.instance:
        lines.append(f"instance: {alert.instance}")
    if alert.job:
        lines.append(f"job: {alert.job}")
    if alert.starts_at:
        lines.append(f"startsAt: {alert.starts_at}")
    extra_labels = {
        k: v
        for k, v in alert.labels.items()
        if k not in {"alertname", "severity", "instance", "job"}
    }
    if extra_labels:
        rendered = ", ".join(f"{k}={v}" for k, v in sorted(extra_labels.items()))
        lines.append(f"labels: {rendered}")
    return "\n".join(lines)


def format_raw_group(alerts: list[Alert]) -> str:
    return "\n\n".join(format_raw(a) for a in alerts)
