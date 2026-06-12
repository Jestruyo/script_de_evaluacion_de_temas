# Atajos para docker compose. Requiere config.json en la raíz y .env con GEMINI_API_KEY (para gemini/retake).
# Uso: make help

.PHONY: help build fetch snapshot gemini retake dry-run submit config-ui

COMPOSE   := docker compose
RUN       := $(COMPOSE) run --rm
RUN_IT    := $(COMPOSE) run --rm -it
CONFIG    := --config /app/config.json
OUT       := /app/out

# Opcional: make gemini MODEL=gemini-2.0-flash
MODEL ?=
MODEL_ARG := $(if $(MODEL),--model $(MODEL),)

help:
	@echo "Comandos Moodle quiz (Docker):"
	@echo ""
	@echo "  make build      Construir imagen moodle-quiz"
	@echo "  make fetch      Ver preguntas del intento (config.json)"
	@echo "  make snapshot   Igual que fetch + guarda out/quiz_snapshot.json"
	@echo "  make gemini     Genera out/answers_gemini.json con Gemini"
	@echo "  make retake     Tras entregar: out/answers_retake.json (review + Gemini)"
	@echo "  make dry-run    Simula envío sin mandar al campus"
	@echo "  make submit     Entrega el intento al campus"
	@echo "  make config-ui  Abre editor web local de config.json (puerto 8765)"
	@echo ""
	@echo "Opcional: make gemini MODEL=gemini-2.0-flash"

build:
	$(COMPOSE) build moodle-quiz

fetch:
	$(RUN) moodle-quiz fetch $(CONFIG)

snapshot:
	$(RUN) moodle-quiz fetch $(CONFIG) --snapshot $(OUT)/quiz_snapshot.json

gemini:
	$(RUN_IT) moodle-quiz gemini-answers $(CONFIG) --answers-out $(OUT)/answers_gemini.json $(MODEL_ARG)

retake:
	$(RUN_IT) moodle-quiz retake-answers $(CONFIG) --answers-out $(OUT)/answers_retake.json $(MODEL_ARG)

dry-run:
	$(RUN_IT) moodle-quiz submit $(CONFIG) --dry-run

submit:
	$(RUN_IT) moodle-quiz submit $(CONFIG)

config-ui:
	python3 config_ui_server.py --open
