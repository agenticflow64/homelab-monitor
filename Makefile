# homelab-monitor — команды демо и разработки

COMPOSE := docker compose --profile full

.PHONY: up down rebuild logs status test unit smoke feed
.PHONY: incident-cpu incident-disk incident-down cleanup

up:            ## поднять весь стек (prometheus, alertmanager, node_exporter, loki, grafana, agent)
	$(COMPOSE) up -d --build

down:          ## остановить стек (данные в volume сохраняются)
	$(COMPOSE) down

rebuild:       ## пересобрать alert-agent и перезапустить
	$(COMPOSE) up -d --build --force-recreate alert-agent

logs:          ## логи alert-agent
	$(COMPOSE) logs -f alert-agent

status:        ## статус сервисов
	$(COMPOSE) ps

test:          ## все тесты (юнит)
	uv run --with pytest --with fastapi --with httpx -m pytest tests -q

unit:          ## только юнит-тесты
	uv run --with pytest --with fastapi --with httpx -m pytest tests -q -m "not integration"

smoke:         ## интеграционный smoke: поднимает стек и прогоняет тестовый алерт
	uv run --with pytest --with fastapi --with httpx -m pytest tests -q -m integration

feed:          ## открыть ленту алертов
	xdg-open http://localhost:8081/ || open http://localhost:8081/

# --- демо-инциденты (см. .claude/skills/incident-sim) ---

# заполнять нужно именно корневую ФС (/): /home — отдельный раздел,
# а старый /var/tmp/homelab-sim принадлежит root, поэтому новый каталог
SIM_DIR ?= /var/tmp/homelab-fill

incident-disk: ## залить ~9ГБ на системную ФС -> HighDiskUsage (~через 2 мин)
	@mkdir -p $(SIM_DIR)
	@df -h / | tail -1
	@echo "пишу 9G в $(SIM_DIR)/fillfile..."
	dd if=/dev/zero of=$(SIM_DIR)/fillfile bs=1M count=9216 status=progress
	@df -h / | tail -1

incident-cpu:  ## загрузить все ядра на 11 мин -> HighCPUUsage (~через 10-11 мин)
	@echo "нагрузка CPU (timeout 660s, все ядра: $(nproc)); правилу нужно окно rate[5m] + for:5m..."
	timeout 660 bash -c 'for i in $$(seq $(nproc)); do (while :; do :; done) & done; wait' || true

incident-down: ## остановить loki -> ServiceDown (~через 2 мин)
	$(COMPOSE) stop loki
	@echo "loki остановлен; восстановление: make cleanup"

cleanup:       ## убрать все воздействия инцидентов и вернуть сервисы
	rm -rf $(SIM_DIR)
	pkill -f 'while :; do :; done' || true
	$(COMPOSE) start
	@df -h / | tail -1
	$(COMPOSE) ps
