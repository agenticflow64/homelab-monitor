"""Юнит-тесты сборки промпта и fallback-объяснения."""
from app.context import IncidentContext, MetricRow
from app.llm import fallback_explanation, validate_sections
from app.prompt import SYSTEM_PROMPT, build_user_prompt
from app.webhook import parse_alert

ALERT = parse_alert(
    {
        "status": "firing",
        "labels": {
            "alertname": "HighCPUUsage",
            "instance": "node_exporter:9100",
            "severity": "warning",
        },
        "annotations": {
            "summary": "Загрузка CPU выше 90% в течение 5 минут",
            "description": "Инстанс node_exporter:9100: средняя загрузка CPU 96.2%",
        },
        "startsAt": "2026-10-12T18:00:00Z",
    }
)


def make_context():
    return IncidentContext(
        metrics=[
            MetricRow(
                title="Загрузка CPU по инстансам, %",
                query="100 - avg...",
                series=[{"labels": {"instance": "node_exporter:9100"}, "value": "96.2"}],
            ),
            MetricRow(
                title="Load average 1m",
                query="node_load1",
                series=[],
                error="connection refused",
            ),
        ],
        logs=["[node_exporter] GET /metrics 200"],
    )


def test_user_prompt_contains_alert_and_metrics():
    prompt = build_user_prompt([ALERT], make_context())
    assert "HighCPUUsage" in prompt
    assert "96.2" in prompt
    assert "node_exporter:9100" in prompt
    assert "Загрузка CPU по инстансам" in prompt
    assert "connection refused" in prompt  # недоступные метрики видны честно
    assert "[node_exporter] GET /metrics 200" in prompt


def test_system_prompt_requires_three_sections():
    for header in ("ЧТО СЛУЧИЛОСЬ", "ВЕРОЯТНАЯ ПРИЧИНА", "ЧТО ПРОВЕРИТЬ"):
        assert header in SYSTEM_PROMPT


def test_validate_sections():
    good = "ЧТО СЛУЧИЛОСЬ: x\nВЕРОЯТНАЯ ПРИЧИНА: y\nЧТО ПРОВЕРИТЬ: z"
    assert validate_sections(good) is True
    assert validate_sections("что случилось: x\nВероятная причина: y\nчто проверить: z") is True
    assert validate_sections("только один раздел") is False


def test_fallback_explanation_structure():
    text = fallback_explanation([ALERT], make_context())
    assert "ЧТО СЛУЧИЛОСЬ" in text.upper()
    assert "ВЕРОЯТНАЯ ПРИЧИНА" in text.upper()
    assert "ЧТО ПРОВЕРИТЬ" in text.upper()
    assert "96.2" in text  # метрики вклеены и без LLM
    assert "ps aux" in text  # конкретный чек-лист для CPU
