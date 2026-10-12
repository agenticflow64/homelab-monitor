# CLAUDE.md — homelab-monitor

## Цель проекта

Демо-кейс для портфолио: мониторинг-агент домашней лабы. Prometheus + node_exporter собирают
метрики, Loki — логи; при срабатывании правила алерта Python-агент отправляет контекст
(метрики + последние логи) в GLM API и доставляет в Telegram алерт с объяснением на
естественном языке: что случилось, вероятная причина, что проверить.

## Позиционирование

Backend-разработчик, встраивающий AI-агентов в реальную инфраструктуру.
Проект показывает не «чат-бот с LLM», а интеграцию AI-слоя в стандартный ops-стек
(Prometheus/Loki/Grafana) с измеримой пользой: время разбора инцидента и доля ложных срабатываний.

## Стек

- Метрики: Prometheus + node_exporter
- Логи: Loki
- Дашборды: Grafana
- Агент: Python 3.12+
- LLM: GLM API, base URL `https://open.bigmodel.cn/api/paas/v4`
- Доставка: Telegram Bot API
- Запуск: Docker Compose (одной командой `docker compose up -d`)

## Структура

- `docker-compose.yml` — все сервисы; `alert-agent` пока заглушка-комментарий
- `prometheus.yml` — scrape-конфиг и alerting rules (диск > 85%, CPU > 90% 5m, сервис down)
- `docs/architecture.md` — mermaid-схема потоков данных
- `docs/demo-script.md` — сценарий демо до 2 минут
- `docs/plan.md` — план по вечерам (1: стек+правила, 2: агент+GLM+Telegram, 3: демо+замеры)
- `.claude/skills/incident-sim/` — симуляция инцидентов для демо

## Правила

1. **Секреты — только в `.env`** (в git не попадает, см. `.gitignore`).
   Никогда не коммитить `GLM_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   и не вставлять их в код, README или docs. Для образца — `.env.example`.
2. **Git-identity — локальная для этого репо**: `agenticflow64` /
   `93826006+agenticflow64@users.noreply.github.com` (задана через локальный config,
   НЕ трогать `--global` — там личный аккаунт).
3. **Пушить только в `agenticflow64/homelab-monitor`** (remote `origin`). Никаких других remote.
4. **Ничего из основного места работы**: никаких внутренних названий сервисов, хостов,
   коллег, доменов и конфигов работодателя. Grafana/Prometheus/Loki/GLM — открытые
   инструменты, их можно.
5. **Все цифры результатов помечать «демо»**: любые замеры — из локального стенда,
   формулировка вида «цифры из локальных замеров (демо)».
6. Язык проекта — русский; технические названия, команды и код — английские.
7. Кейсовые обновления — через команду `/case-update` (обновляет «Результат» в README
   и дублирует кейс в `~/freelans-way/portfolio/case-homelab-monitor/`).
8. Перед коммитом проверять, что `.env` не попал в `git status`.
