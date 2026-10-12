"""Настройки alert-agent из переменных окружения.

Секреты (API-ключи, токены) читаются только из env и никогда не логируются.
Пустая строка в env трактуется как «не задано».
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _clean(value: str | None) -> str:
    return (value or "").strip()


@dataclass(frozen=True)
class Settings:
    prometheus_url: str
    loki_url: str

    glm_base_url: str
    glm_api_key: str
    glm_model: str

    openrouter_base_url: str
    openrouter_api_key: str
    openrouter_model: str

    telegram_bot_token: str
    telegram_chat_id: str

    cooldown_seconds: float
    llm_timeout_seconds: float
    llm_retries: int
    data_dir: str

    @property
    def glm_enabled(self) -> bool:
        return bool(self.glm_api_key)

    @property
    def openrouter_enabled(self) -> bool:
        return bool(self.openrouter_api_key)

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @classmethod
    def from_env(cls, env: dict | None = None) -> "Settings":
        env = dict(os.environ if env is None else env)
        return cls(
            prometheus_url=_clean(env.get("PROMETHEUS_URL")) or "http://localhost:9090",
            loki_url=_clean(env.get("LOKI_URL")) or "http://localhost:3100",
            glm_base_url=_clean(env.get("GLM_BASE_URL"))
            or "https://open.bigmodel.cn/api/paas/v4",
            glm_api_key=_clean(env.get("GLM_API_KEY")),
            glm_model=_clean(env.get("GLM_MODEL")) or "glm-4.5-flash",
            openrouter_base_url=_clean(env.get("OPENROUTER_BASE_URL"))
            or "https://openrouter.ai/api/v1",
            openrouter_api_key=_clean(env.get("OPENROUTER_API_KEY")),
            openrouter_model=_clean(env.get("OPENROUTER_MODEL"))
            or "nvidia/nemotron-3-ultra-550b-a55b:free",
            telegram_bot_token=_clean(env.get("TELEGRAM_BOT_TOKEN")),
            telegram_chat_id=_clean(env.get("TELEGRAM_CHAT_ID")),
            cooldown_seconds=float(_clean(env.get("GROUP_COOLDOWN_SECONDS")) or 600),
            llm_timeout_seconds=float(_clean(env.get("LLM_TIMEOUT_SECONDS")) or 150),
            llm_retries=int(_clean(env.get("LLM_RETRIES")) or 2),
            data_dir=_clean(env.get("AGENT_DATA_DIR")) or "data",
        )
