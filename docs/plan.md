# План разработки — homelab-monitor

Формат: три вечера по 2–3 часа. Цель каждого вечера — закончить работоспособным
состоянием, которое можно показать.

## Вечер 1 — стек мониторинга + правила

- [x] Каркас репозитория (docker-compose, prometheus.yml, alerts.yml, docs)
- [x] `make up` (`docker compose --profile full up -d`) — всё поднялось
- [x] Prometheus: `up == 1` для всех целей (http://localhost:9090/targets)
- [x] Правила загружены и валидны: `HighDiskUsage`, `HighCPUUsage`, `ServiceDown`
      (порог диска поднят до 92% под демо-хост: системная ФС постоянно ~89%)
- [x] Grafana: Prometheus и Loki подключены автопровижинингом datasources
- [x] Commit

## Вечер 2 — агент + GLM + Telegram

- [x] Каркас `agent/`: Python 3.12, FastAPI, httpx, Dockerfile
- [x] Приём алертов: Alertmanager webhook -> `POST /webhook`
- [x] Сбор контекста: instant queries Prometheus API (+ Loki best effort)
- [x] Промпт: контекст -> «что случилось / вероятная причина / что проверить»
- [x] LLM: GLM `glm-4.5-flash` (thinking off; `glm-4-flash` на эндпоинте нет)
      -> OpenRouter free -> rule-based fallback, ретраи
- [x] Уведомления: консоль, alerts.log, Telegram (по токену из env)
- [x] Сервис `alert-agent` в docker-compose (host-сеть, port 8081)
- [x] E2E: alertmanager -> агент -> объяснение (проверено на живом стеке)

## Вечер 3 — демо-инциденты, замеры, упаковка

- [x] Все три сценария прогнаны на живом стеке: ServiceDown (~105 с),
      HighDiskUsage (~85–90 с), HighCPUUsage (~10 мин)
- [x] Замер: сырой алерт vs алерт с объяснением (демо, сценарная оценка)
- [x] Веб-лента алертов: сырой алерт слева, объяснение справа (:8081)
- [x] Тесты: 18 юнит + интеграционный smoke (docker compose up + curl тестовый алерт)
- [x] README «Решение»/«Результат» обновлены реальными цифрами (демо)
- [x] docs/architecture.md, docs/demo-script.md актуализированы
- [ ] Записать демо по docs/demo-script.md (≤ 2 минут)
- [ ] Дублировать кейс в `~/freelans-way/portfolio/case-homelab-monitor/`
- [ ] Финальный прогон README с нуля (на чистой машине)

## Definition of done

- [x] Одна команда поднимает всё (`make up`)
- [x] Любой из трёх инцидентов даёт алерт с объяснением: ServiceDown/диск —
      за ~2 мин, CPU — ~10 мин (время правила, не агента; конвейер агента 11–15 с)
- [x] README содержит замеры с пометкой «демо»
- [x] В git нет секретов (`.env` в `.gitignore`, ключи только в env)
