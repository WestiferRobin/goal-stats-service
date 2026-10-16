# GoalStats developer interface: exactly nine supported commands.
PYTHON ?= python3.12
ifeq ($(OS),Windows_NT)
BASH := C:/Progra~1/Git/bin/bash.exe
else
BASH := /bin/bash
endif
.DEFAULT_GOAL := help

.PHONY: setup infra run deploy seed test certify stop help
setup infra run deploy stop:
	@PYTHON="$(PYTHON)" $(BASH) scripts/development/local.sh $@

test:
	@$(BASH) scripts/testing/test.sh

certify:
	@$(BASH) scripts/testing/test.sh certify

help:
	@$(BASH) scripts/development/local.sh help

# Values travel through the environment, never through shell source interpolation.
override DATASET := $(value DATASET)
export DATASET
ifneq ($(origin DRY_RUN),undefined)
override DRY_RUN := $(value DRY_RUN)
export DRY_RUN
endif
DRY ?= false
override DRY := $(value DRY)
export DRY
export PYTHON
seed:
	@$(BASH) scripts/development/local.sh seed
