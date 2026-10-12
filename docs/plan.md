# План разработки — homelab-monitor

Формат: три вечера по 2–3 часа. Цель каждого вечера — закончить работоспособным
состоянием, которое можно показать.

## Вечер 1 — стек мониторинга + правила

- [x] Каркас репозитория (docker-compose, prometheus.yml, alerts.yml, docs)
- [ ] `docker compose --profile full up -d` — проверить, что всё поднялось
- [ ] Prometheus: убедиться, что `up == 1` для всех целей (http://localhost:9090/targets)
- [ ] Проверить правила: `HighDiskUsage`, `HighCPUUsage`, `ServiceDown`
      (временно снизить пороги, чтобы убедиться, что срабатывают)
- [ ] Grafana: подключить Prometheus и Loki как datasources
- [ ] Grafana: простой дашборд (CPU, диск, память, up)
- [ ] Commit + push

## Вечер 2 — агент + GLM + Telegram

- [ ] Каркас `agent/`: Python 3.12, зависимости (httpx), Dockerfile
- [ ] Приём алертов: Alertmanager webhook (или опрос Prometheus API, выбрать простое)
- [ ] Сбор контекста: метрики из Prometheus API + последние логи из Loki API
- [ ] Промпт для GLM: контекст → «что случилось / вероятная причина / что проверить»
- [ ] Вызов GLM API (`GLM_BASE_URL` + `GLM_API_KEY` из `.env`)
- [ ] Отправка в Telegram (Bot API)
- [ ] Раскомментировать сервис `alert-agent` в docker-compose.yml
- [ ] E2E-проверка: `incident-sim` → алерт в Telegram с объяснением
- [ ] Commit + push

## Вечер 3 — демо-инциденты, замеры, упаковка

- [ ] Прогнать все три сценария `incident-sim` (CPU, диск, стоп контейнера)
- [ ] Замер: время разбора инцидента — сырой алерт vs алерт с объяснением (демо)
- [ ] Замер: доля ложных срабатываний за демо-период (демо)
- [ ] Записать демо по docs/demo-script.md (≤ 2 минут)
- [ ] Обновить «Результат» в README (команда `/case-update`)
- [ ] Дублировать кейс в `~/freelans-way/portfolio/case-homelab-monitor/`
- [ ] Финальный прогон README: запускается ли всё по инструкции с нуля
- [ ] Commit + push

## Definition of done

- Одна команда поднимает всё (`docker compose --profile full up -d`)
- Любой из трёх инцидентов `incident-sim` даёт Telegram-алерт с объяснением за < 2 мин
- README содержит замеры с пометкой «демо»
- В git нет секретов
