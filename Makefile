.DEFAULT_GOAL := help
ENV ?= local
PYTHON ?= $(if $(filter setup init dev doctor help,$(or $(MAKECMDGOALS),help)),python3.12,$(if $(wildcard .venv/bin/python),.venv/bin/python,python3.12))
export ENV MESSAGE
export PYTHONDONTWRITEBYTECODE = 1

include make/install.mk
include make/doctor.mk
include make/dev.mk
include make/db.mk
include make/test.mk
include make/coverage.mk
include make/ci.mk

.PHONY: help
help:
	@$(PYTHON) scripts/workflow.py help
