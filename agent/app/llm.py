"""LLM-клиент: GLM (основной) -> OpenRouter free (резерв) -> fallback-текст.

Ретраи с экспоненциальной паузой на каждого провайдера. Ключи в логи не
попадают: логируются только коды/типы ошибок.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from .config import Settings
from .context import IncidentContext
from .prompt import SYSTEM_PROMPT, build_user_prompt
from .webhook import Alert

logger = logging.getLogger("alert-agent.llm")

SECTION_HEADERS = ("ЧТО СЛУЧИЛОСЬ", "ВЕРОЯТНАЯ ПРИЧИНА", "ЧТО ПРОВЕРИТЬ")


@dataclass
class Explanation:
    text: str
    model: str
    latency_s: float
    degraded: bool = False  # True — LLM не ответил, текст собран правилами


def _post_chat(
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    timeout: float,
    retries: int,
    glm_thinking_off: bool,
) -> str:
    """Один провайдер с ретраями. Возвращает текст ответа или бросает исключение."""
    body: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 900,
    }
    if glm_thinking_off:
        # У GLM thinking-режим съедает бюджет токенов и замедляет ответ — выключаем.
        body["thinking"] = {"type": "disabled"}
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            response = client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "homelab-monitor/1.0",
                },
                json=body,
                timeout=httpx.Timeout(timeout, connect=15),
            )
            if response.status_code == 200:
                payload = response.json()
                # OpenRouter иногда отдаёт 200 с error в теле (upstream overloaded)
                if payload.get("error"):
                    logger.warning("llm upstream error body (attempt %s)", attempt + 1)
                    last_error = RuntimeError("upstream error body")
                else:
                    message = payload["choices"][0]["message"]
                    content = (message.get("content") or "").strip()
                    if content:
                        return content
                    last_error = RuntimeError("empty content")
            else:
                # Тело ошибки может содержать детали, но не ключи — можно логировать код.
                logger.warning(
                    "llm http %s from %s (attempt %s)",
                    response.status_code,
                    base_url.split("//")[1].split("/")[0],
                    attempt + 1,
                )
                last_error = RuntimeError(f"http {response.status_code}")
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                "llm request failed (%s, attempt %s)", type(exc).__name__, attempt + 1
            )
        time.sleep(min(2**attempt, 8))
    raise last_error or RuntimeError("llm failed")


def fallback_explanation(alerts: list[Alert], context: IncidentContext) -> str:
    """Правила вместо LLM: грубое, но полезное объяснение по аннотациям и метрикам."""
    primary = alerts[0]
    parts = [
        "ЧТО СЛУЧИЛОСЬ:",
        f"Сработал алерт {primary.alertname} (severity: {primary.severity}).",
        primary.description or primary.summary or "Описание отсутствует.",
        "",
        "ВЕРОЯТНАЯ ПРИЧИНА:",
        "LLM недоступен, причина по правилам не определяется — смотрите метрики ниже.",
        "",
        "ЧТО ПРОВЕРИТЬ:",
    ]
    checklist = {
        "HighDiskUsage": [
            "df -h — какие ФС заполнены",
            "du -xh --max-depth=2 / | sort -rh | head -20 — кто съел место",
            "lsof +L1 — удалённые, но открытые файлы",
        ],
        "HighCPUUsage": [
            "ps aux --sort=-%cpu | head -15 — топ процессов",
            "uptime — load average",
            "docker stats --no-stream — лимиты контейнеров",
        ],
        "ServiceDown": [
            "docker compose ps — статус сервисов",
            "docker compose logs --tail=50 <сервис> — последние логи",
            "curl -s <адрес>/metrics — отвечает ли экспортер",
        ],
    }.get(primary.alertname, ["docker compose ps", "docker compose logs --tail=50"])
    parts.extend(f"- {item}" for item in checklist)
    metric_lines = []
    for row in context.metrics:
        for point in row.series[:3]:
            metric_lines.append(f"- {row.title}: {point['value']}")
    if metric_lines:
        parts.append("")
        parts.append("Метрики на момент инцидента:")
        parts.extend(metric_lines[:8])
    return "\n".join(parts)


def validate_sections(text: str) -> bool:
    """Ответ модели должен содержать все три раздела, иначе считаем его битым."""
    upper = text.upper()
    return all(header in upper for header in SECTION_HEADERS)


def summarize(alerts: list[Alert], context: IncidentContext, settings: Settings) -> Explanation:
    """Полная цепочка: GLM -> OpenRouter -> fallback. Никогда не бросает исключение."""
    user_prompt = build_user_prompt(alerts, context)
    started = time.monotonic()
    providers: list[tuple[str, str, str, bool]] = []
    if settings.glm_enabled:
        providers.append(
            (settings.glm_base_url, settings.glm_api_key, settings.glm_model, True)
        )
    if settings.openrouter_enabled:
        providers.append(
            (
                settings.openrouter_base_url,
                settings.openrouter_api_key,
                settings.openrouter_model,
                False,
            )
        )
    with httpx.Client() as client:
        for base_url, api_key, model, glm_flag in providers:
            try:
                text = _post_chat(
                    client,
                    base_url,
                    api_key,
                    model,
                    SYSTEM_PROMPT,
                    user_prompt,
                    settings.llm_timeout_seconds,
                    settings.llm_retries,
                    glm_flag,
                )
                if not validate_sections(text):
                    logger.warning("llm answer missing sections, trying next provider")
                    continue
                return Explanation(
                    text=text,
                    model=model,
                    latency_s=round(time.monotonic() - started, 2),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("provider %s failed: %s", model, type(exc).__name__)
                continue
    logger.warning("all llm providers failed, using rule-based fallback")
    return Explanation(
        text=fallback_explanation(alerts, context),
        model="rule-based-fallback",
        latency_s=round(time.monotonic() - started, 2),
        degraded=True,
    )
