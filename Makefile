# GoalStats public developer interface. Advanced maintenance targets are private.
ifeq ($(OS),Windows_NT)
BASH := C:/Progra~1/Git/bin/bash.exe
else
BASH := /bin/bash
endif
.DEFAULT_GOAL := help

.PHONY: setup run test stop help
setup run stop:
	@$(BASH) scripts/local.sh $@

test:
	@$(BASH) scripts/test.sh

help:
	@$(BASH) scripts/local.sh help

# Internal maintenance interface. These targets intentionally do not appear in help.
PYTHON ?= python3.12
MESSAGE ?=
.PHONY: _migration _migration-check _smoke _coverage _certify
_migration:
	@ENV=local MESSAGE="$(MESSAGE)" $(PYTHON) scripts/workflow.py migration
_migration-check:
	@ENV=local $(PYTHON) scripts/workflow.py migration-check
_smoke:
	@$(PYTHON) scripts/workflow.py smoke
_coverage:
	@$(PYTHON) scripts/workflow.py coverage
_certify:
	@$(PYTHON) scripts/workflow.py certify
