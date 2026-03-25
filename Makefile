.PHONY: help up down restart build logs logs-app logs-db shell-app shell-db clean status migrate

help: ## Show this help message
	@grep -E '^[1-9a-zA-Z_ -]+:.*?## .*$$|(^#--)' $(MAKEFILE_LIST) \
	| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[32m %-43s\033[0m %s\n", $$1, $$2}' \
	| sed -e 's/\[32m #-- /[33m/'

#-- Local development

up: ## Start all services
	docker compose up --build -d
	@echo "\n\033[32mStarted!\033[0m"
	@echo "  Streamlit UI:  http://localhost:8501"
	@echo "  MySQL:         localhost:3306"

up-fg: ## Start all services in foreground
	docker compose up --build

down: ## Stop all services
	docker compose down --remove-orphans

restart: ## Restart all services
	$(MAKE) down
	$(MAKE) up

build: ## Rebuild containers without starting
	docker compose build

ps: ## Show status of all services
	docker compose ps

#-- Logs

logs: ## Follow logs from all services
	docker compose logs -f

logs-app: ## Follow Streamlit app logs
	docker compose logs -f streamlit

logs-db: ## Follow MySQL logs
	docker compose logs -f mysql

#-- Database

migrate: ## Run pending database migrations
	docker exec -it vacation_app python migrate.py

#-- Shell Access

shell-app: ## Open a shell in the app container
	docker exec -it vacation_app /bin/bash

shell-db: ## Open a MySQL prompt
	docker exec -it vacation_mysql mysql -u vacation_user -pvacation_pass vacation_db

#-- Cleanup

clean: ## Stop services and remove all data
	docker compose down -v
