"""Хранилище ленты алертов: JSON-файл + кэш в памяти для /api/alerts."""
from __future__ import annotations

import json
import os
import threading
import time
import uuid

MAX_ENTRIES = 50


class AlertStore:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir.rstrip("/")
        self.path = f"{self.data_dir}/alerts.json"
        self._lock = threading.Lock()
        self._writable = True
        try:
            os.makedirs(self.data_dir, exist_ok=True)
        except OSError:
            self._writable = False  # только память, без persist
        self._entries: list[dict] = self._load()

    def _load(self) -> list[dict]:
        try:
            with open(self.path, encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                return data[-MAX_ENTRIES:]
        except (OSError, ValueError):
            pass
        return []

    def add(self, entry: dict) -> dict:
        record = {
            "id": uuid.uuid4().hex[:12],
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            **entry,
        }
        with self._lock:
            self._entries.append(record)
            self._entries = self._entries[-MAX_ENTRIES:]
            self._flush()
        return record

    def list(self) -> list[dict]:
        with self._lock:
            return list(reversed(self._entries))

    def _flush(self) -> None:
        if not self._writable:
            return
        try:
            tmp = f"{self.path}.tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(self._entries, handle, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except OSError:
            pass
