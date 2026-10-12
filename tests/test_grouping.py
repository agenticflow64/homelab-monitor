"""Юнит-тесты группировки всплесков (cooldown-гейт)."""
from app.grouping import GroupGate


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def test_first_alert_passes():
    clock = FakeClock()
    gate = GroupGate(cooldown_seconds=600, clock=clock)
    allowed, suppressed = gate.allow("HighCPUUsage/x")
    assert allowed is True
    assert suppressed == 0


def test_repeat_within_cooldown_suppressed():
    clock = FakeClock()
    gate = GroupGate(cooldown_seconds=600, clock=clock)
    gate.allow("key")
    clock.advance(10)
    assert gate.allow("key") == (False, 1)
    clock.advance(10)
    assert gate.allow("key") == (False, 2)


def test_after_cooldown_passes_with_count():
    clock = FakeClock()
    gate = GroupGate(cooldown_seconds=600, clock=clock)
    gate.allow("key")
    clock.advance(100)
    gate.allow("key")  # подавлено 1
    clock.advance(601)
    allowed, suppressed = gate.allow("key")
    assert allowed is True
    assert suppressed == 1
    # после успешного прохода счётчик обнулился
    clock.advance(700)
    assert gate.allow("key") == (True, 0)


def test_different_keys_independent():
    clock = FakeClock()
    gate = GroupGate(cooldown_seconds=600, clock=clock)
    gate.allow("a")
    assert gate.allow("b")[0] is True
    clock.advance(5)
    assert gate.allow("a")[0] is False
    assert gate.allow("b")[0] is False
