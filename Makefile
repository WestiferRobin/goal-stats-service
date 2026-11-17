# GoalStats developer interface: exactly nine supported commands.
ifeq ($(OS),Windows_NT)
ifeq ($(origin PYTHON),undefined)
PYTHON := $(shell py -3.12 -c "import sys; print(sys.executable.replace(chr(92), '/'))" 2>NUL)
ifeq ($(strip $(PYTHON)),)
PYTHON := python
endif
endif
BASH ?= C:/Progra~1/Git/bin/bash.exe
else
PYTHON ?= python3.12
BASH ?= /bin/bash
endif
.DEFAULT_GOAL := help

.PHONY: setup infra run deploy seed test certify stop help
setup infra run deploy stop:
	@$(BASH) scripts/development/local.sh $@

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
