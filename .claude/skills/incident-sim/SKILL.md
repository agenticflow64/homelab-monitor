---
name: incident-sim
description: Симуляция инцидентов для демо homelab-monitor — CPU-нагрузка, заполнение диска, стоп контейнера — и безопасный cleanup после них. Использовать при подготовке/записи демо и при проверке alert-правил.
---

# incident-sim — симуляция инцидентов

Три сценария для проверки alert-правил и записи демо. Все воздействия — на локальный
демо-стенд, точки монтирования и объёмы ограничены. После каждого сценария —
обязательный cleanup.

## Общие правила безопасности

- Работаем только внутри демо-стенда homelab-monitor (docker compose-проект).
- Не трогаем пути вне `/tmp/homelab-sim/` и volumes демо-проекта.
- Ограничиваем объём: файл заполнения — не больше свободного места минус запас;
  перед созданием проверяем `df -h`.
- CPU-нагрузка — ограниченная по времени (timeout), не бесконечная.
- После каждого сценария выполняем cleanup и проверяем `df -h` / `docker compose ps`.

## Сценарий 1: заполнение диска (`HighDiskUsage`, > 85%)

Проверяем свободное место и создаем временный файл под контрольным размером:

```bash
mkdir -p /tmp/homelab-sim
df -h /tmp
# размер подбираем так, чтобы заполнить ФС выше 85%, но оставить запас
dd if=/dev/zero of=/tmp/homelab-sim/fillfile bs=1M count=4096 status=progress
df -h /tmp   # проверяем порог
```

Сработает `HighDiskUsage` через ~2 минуты (`for: 2m`).

Cleanup:

```bash
rm /tmp/homelab-sim/fillfile
df -h /tmp   # подтверждаем освобождение
```

## Сценарий 2: загрузка CPU (`HighCPUUsage`, > 90% 5 минут)

Загружаем все ядра на 6 минут (правило требует 5 минут подряд) с обязательным
авто-остановом:

```bash
# timeout гарантирует завершение, даже если забыли про процесс
timeout 360 bash -c 'for i in $(seq $(nproc)); do (while :; do :; done) & done; wait'
```

Проверка загрузки в другом терминале: `top` или Grafana-дашборд.

Cleanup (если процесс прерван раньше timeout):

```bash
pkill -f 'while :; do :; done' || true
```

## Сценарий 3: упавший сервис (`ServiceDown`, up == 0)

Останавливаем node_exporter — Prometheus перестаёт получать метрики:

```bash
docker compose --profile full stop node_exporter
```

`ServiceDown` сработает через ~1 минуту (`for: 1m`).

Cleanup (восстановление):

```bash
docker compose --profile full start node_exporter
docker compose ps   # подтверждаем, что статус Up/running
```

## Полный cleanup после демо

```bash
rm -rf /tmp/homelab-sim
pkill -f 'while :; do :; done' || true
docker compose --profile full start
df -h /tmp
docker compose ps
```

## Что ожидаем от alert-agent (для проверки демо)

| Сценарий | Алерт | Ожидаемое объяснение |
|---|---|---|
| Диск | HighDiskUsage | Указание на крупный недавний файл в /tmp, предложение проверить `du`/`lsof +L1` |
| CPU | HighCPUUsage | Указание на процесс-потребитель, предложение `top`/`ps aux --sort=-%cpu` |
| Сервис | ServiceDown | Факт недоступности node_exporter, предложение `docker compose ps` / `docker logs` |
