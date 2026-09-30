.PHONY: build run stop logs providers providers-stop
build run stop logs providers providers-stop:
	@$(PYTHON) scripts/workflow.py $@

.PHONY: dev init seed quick-test
dev init seed quick-test:
	@$(PYTHON) scripts/workflow.py $@
