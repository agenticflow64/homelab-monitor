"""Сбор контекста инцидента: живые метрики из Prometheus API + логи из Loki.

Запросы к Prometheus — read-only instant queries. Каждый сбой отдельного
запроса не ломает пайплайн: недоступные данные помечаются как unknown.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

from .webhook import Alert

logger = logging.getLogger("alert-agent.context")

# Какие метрики подтянуть для каждого типа алерта.
# (заголовок для промпта, PromQL instant query)
ALERT_QUERIES: dict[str, list[tuple[str, str]]] = {
    "HighDiskUsage": [
        ("Заполнение файловых систем, %",
         '(1 - node_filesystem_avail_bytes{fstype!~"tmpfs|overlay|squashfs"}'
         ' / node_filesystem_size_bytes{fstype!~"tmpfs|overlay|squashfs"}) * 100'),
        ("Свободно на ФС, ГБ",
         'node_filesystem_avail_bytes{fstype!~"tmpfs|overlay|squashfs"} / 1024^3'),
    ],
    "HighCPUUsage": [
        ("Загрузка CPU по инстансам, %",
         '100 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100'),
        ("Load average 1m/5m/15m",
         'node_load1 or node_load5 or node_load15'),
        ("Занято памяти, %",
         '(1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) * 100'),
    ],
    "ServiceDown": [
        ("Доступность целей скрапа (up)",
         'up'),
    ],
}

COMMON_QUERIES: list[tuple[str, str]] = [
    ("Load average 1m", "node_load1"),
]


@dataclass
class MetricRow:
    title: str
    query: str
    series: list = field(default_factory=list)  # [{labels, value}]
    error: str = ""


@dataclass
class IncidentContext:
    metrics: list = field(default_factory=list)  # list[MetricRow]
    logs: list = field(default_factory=list)  # list[str]
    logs_error: str = ""

    def render(self) -> str:
        """Контекст в виде текста для промпта."""
        parts: list[str] = []
        for row in self.metrics:
            if row.error:
                parts.append(f"## {row.title}\n(нет данных: {row.error})")
                continue
            lines = [f"## {row.title}"]
            for point in row.series:
                label = ",".join(
                    f"{k}={v}" for k, v in sorted(point["labels"].items())
                ) or "(без лейблов)"
                lines.append(f"- {label}: {point['value']}")
            parts.append("\n".join(lines))
        if self.logs:
            parts.append("## Последние записи логов (Loki)\n" + "\n".join(self.logs))
        elif self.logs_error:
            parts.append(f"## Логи Loki\n(недоступны: {self.logs_error})")
        else:
            parts.append("## Логи Loki\n(записей за окно инцидента нет)")
        return "\n\n".join(parts)


def _fmt_value(value: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) >= 1000:
        return f"{number:.0f}"
    if number == int(number):
        return str(int(number))
    return f"{number:.2f}"


def query_prometheus(
    client: httpx.Client, prometheus_url: str, query: str
) -> MetricRow:
    try:
        response = client.get(
            f"{prometheus_url.rstrip('/')}/api/v1/query",
            params={"query": query},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "success":
            return MetricRow(title="", query=query, error=payload.get("error", "unknown"))
        series = [
            {"labels": item.get("metric") or {}, "value": _fmt_value(item["value"][1])}
            for item in (payload.get("data", {}).get("result") or [])
        ]
        return MetricRow(title="", query=query, series=series)
    except Exception as exc:  # noqa: BLE001 — любая ошибка не должна ронять пайплайн
        logger.warning("prometheus query failed: %s", type(exc).__name__)
        return MetricRow(title="", query=query, error=str(exc)[:120])


def query_loki(client: httpx.Client, loki_url: str, window_minutes: int = 30) -> list[str]:
    """Последние записи логов за окно инцидента (best effort)."""
    try:
        import time as _time

        now_ns = int(_time.time() * 1e9)
        start_ns = now_ns - window_minutes * 60 * 1_000_000_000
        response = client.get(
            f"{loki_url.rstrip('/')}/loki/api/v1/query_range",
            params={
                "query": '{job=~".+"}',
                "start": start_ns,
                "end": now_ns,
                "limit": 15,
                "direction": "backward",
            },
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        lines = []
        for stream in payload.get("data", {}).get("result") or []:
            labels = stream.get("stream") or {}
            for _, text in stream.get("values") or []:
                lines.append(f"[{labels.get('job', '?')}] {text[:200]}")
        return lines
    except Exception as exc:  # noqa: BLE001
        logger.info("loki unavailable: %s", type(exc).__name__)
        return []


def collect_context(
    alerts: list[Alert],
    prometheus_url: str,
    loki_url: str,
    client: httpx.Client | None = None,
) -> IncidentContext:
    """Метрики по типам сработавших алертов + общие + логи."""
    own_client = client is None
    client = client or httpx.Client()
    try:
        titles: dict[str, str] = {}
        rows: list[MetricRow] = []
        alertnames = {a.alertname for a in alerts}
        planned: list[tuple[str, str]] = list(COMMON_QUERIES)
        for alertname in sorted(alertnames):
            planned.extend(ALERT_QUERIES.get(alertname, []))
        seen: set[str] = set()
        for title, query in planned:
            if query in seen:
                continue
            seen.add(query)
            row = query_prometheus(client, prometheus_url, query)
            row.title = title
            rows.append(row)
        logs = query_loki(client, loki_url)
        return IncidentContext(metrics=rows, logs=logs)
    finally:
        if own_client:
            client.close()
