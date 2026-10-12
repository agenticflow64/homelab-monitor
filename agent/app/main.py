"""alert-agent — webhook-ресивер Alertmanager с LLM-объяснением алертов.

Поток: Alertmanager -> POST /webhook -> группировка (cooldown) ->
контекст (Prometheus API) -> LLM (GLM -> OpenRouter -> fallback) ->
уведомления (консоль, alerts.log, Telegram) + лента (/api/alerts).
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from .config import Settings
from .context import collect_context
from .grouping import GroupGate
from .llm import summarize
from .notify import build_message, notify_all
from .store import AlertStore
from .webhook import firing, group_key, parse_webhook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("alert-agent")

settings = Settings.from_env()
gate = GroupGate(cooldown_seconds=settings.cooldown_seconds)
store = AlertStore(settings.data_dir)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="homelab alert-agent", version="1.0.0")


@app.get("/healthz")
def healthz() -> dict:
    return {
        "status": "ok",
        "glm_enabled": settings.glm_enabled,
        "openrouter_enabled": settings.openrouter_enabled,
        "telegram_enabled": settings.telegram_enabled,
        "cooldown_seconds": settings.cooldown_seconds,
    }


def process_group(alerts, received_at: str) -> None:
    """Обработка одной группы firing-алертов (в фоне, в thread pool)."""
    key = group_key(alerts[0])
    allowed, suppressed = gate.allow(key)
    if not allowed:
        logger.info(
            "group %s suppressed by cooldown (%d repeats)", key, suppressed
        )
        return
    pipeline_started = time.monotonic()
    context = collect_context(
        alerts, settings.prometheus_url, settings.loki_url
    )
    context_ms = round((time.monotonic() - pipeline_started) * 1000)
    explanation = summarize(alerts, context, settings)
    message = build_message(alerts[0].alertname, explanation, suppressed)
    channels = notify_all(message, settings)
    total_ms = round((time.monotonic() - pipeline_started) * 1000)
    entry = {
        "alertname": alerts[0].alertname,
        "severity": alerts[0].severity,
        "status": "firing",
        "received_at": received_at,
        "notified_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "suppressed_repeats": suppressed,
        "raw": [
            {
                "labels": a.labels,
                "annotations": a.annotations,
                "startsAt": a.starts_at,
                "status": a.status,
            }
            for a in alerts
        ],
        "summary": alerts[0].summary or alerts[0].description,
        "metrics": [
            {
                "title": row.title,
                "query": row.query,
                "series": row.series,
                "error": row.error,
            }
            for row in context.metrics
        ],
        "explanation": {
            "text": explanation.text,
            "model": explanation.model,
            "latency_s": explanation.latency_s,
            "degraded": explanation.degraded,
        },
        "channels": channels,
        "timings_ms": {
            "context": context_ms,
            "total": total_ms,
        },
    }
    record = store.add(entry)
    logger.info(
        "processed %s: model=%s, total=%sms, entry=%s",
        key,
        explanation.model,
        total_ms,
        record["id"],
    )


@app.post("/webhook")
async def webhook(request: Request, background: BackgroundTasks) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": "invalid json"}, status_code=400)
    alerts = parse_webhook(payload)
    firing_alerts = firing(alerts)
    received_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    if not firing_alerts:
        logger.info(
            "webhook received, no firing alerts (%d resolved) — skipped",
            len(alerts),
        )
        return JSONResponse({"received": len(alerts), "processed": 0})
    background.add_task(process_group, firing_alerts, received_at)
    return JSONResponse(
        {
            "received": len(alerts),
            "processing": [a.alertname for a in firing_alerts],
        }
    )


@app.get("/api/alerts")
def api_alerts() -> list[dict]:
    return store.list()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
