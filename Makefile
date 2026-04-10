.PHONY: help up down restart reload build logs logs-app logs-db shell-app shell-db clean nuclear-restart ps migrate test

#-- Meta

help: ## Show this help message
	@grep -E '^[1-9a-zA-Z_ -]+:.*?## .*$$|(^#--)' $(MAKEFILE_LIST) \
	| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[32m %-43s\033[0m %s\n", $$1, $$2}' \
	| sed -e 's/\[32m #-- /[33m/'

#-- Local development

reload: ## Reload Flask (touch app.py inside container)
	docker exec vacation_app touch /app/app.py

up: ## Start all services
	docker compose up -d
	@echo "\n\033[32mStarted!\033[0m"
	@echo "  Web UI:  http://localhost:8501"
	@echo "  MySQL:   localhost:3306"

up-fg: ## Start all services in foreground
	docker compose up

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

logs-app: ## Follow app logs
	docker compose logs -f web

logs-db: ## Follow MySQL logs
	docker compose logs -f mysql

#-- Database

migrate: ## Run pending database migrations
	docker exec -it vacation_app python migrate.py

#-- Admin

make-admin: ## Promote a user to admin (usage: make make-admin user=shortname)
	@if [ -z "$(user)" ]; then echo "\033[31mUsage: make make-admin user=shortname\033[0m"; exit 1; fi
	docker exec vacation_mysql mysql -u vacation_user -pvacation_pass vacation_db \
		-e "UPDATE users SET role = 'admin' WHERE username = '$(user)';"
	@echo "\033[32mUser '$(user)' is now admin.\033[0m"

#-- Shell Access

shell-app: ## Open a shell in the app container
	docker exec -it vacation_app /bin/bash

shell-db: ## Open a MySQL prompt
	docker exec -it vacation_mysql mysql -u vacation_user -pvacation_pass vacation_db

#-- Testing

test: ## Run tests inside the app container
	docker exec vacation_app python -m pytest tests/ -v

#-- Cleanup

clean: ## Stop services and remove all data
	docker compose down -v

nuclear-restart: ## Wipe database, rebuild, and start fresh with migrations
	docker compose down -v
	@printf "SECRET_KEY=%s\n" "$$(openssl rand -hex 32)" > .env
	docker compose up -d --build
	@echo "\n\033[32mNuclear restart complete! Migrations run automatically on app startup.\033[0m"
	@echo "  Web UI:  http://localhost:5000"
