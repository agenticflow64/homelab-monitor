"""Группировка всплесков алертов: подавление повторов одного ключа.

Один и тот же алерт (alertname + instance) в пределах cooldown-окна
обрабатывается один раз — LLM и уведомления не spam-ятся.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class GateState:
    last_sent: float = 0.0
    suppressed: int = 0


@dataclass
class GroupGate:
    cooldown_seconds: float
    clock: object = time.monotonic
    _states: dict = field(default_factory=dict)

    def allow(self, key: str) -> tuple[bool, int]:
        """Пропустить группу к обработке?

        Возвращает (allowed, suppressed_count) — сколько повторов было
        подавлено с прошлой обработки (0, если пропускаем сейчас же).
        """
        now = self.clock()
        state = self._states.get(key)
        if state is None:
            self._states[key] = GateState(last_sent=now, suppressed=0)
            return True, 0
        if now - state.last_sent >= self.cooldown_seconds:
            suppressed = state.suppressed
            state.last_sent = now
            state.suppressed = 0
            return True, suppressed
        state.suppressed += 1
        return False, state.suppressed

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self._states.clear()
        else:
            self._states.pop(key, None)
