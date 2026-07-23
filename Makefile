.PHONY: validate test install uninstall dry-run stack-audit

validate:
	python3 scripts/validate.py
	python3 scripts/test_sync_agent_stack.py
	python3 scripts/test_sync_instructions.py
	python3 scripts/test_sync_opencode_config.py
	python3 scripts/test_check_pin_freshness.py
	sh -n install.sh bootstrap.sh scripts/test-install.sh

test: validate
	./scripts/test-install.sh
	@if command -v pwsh >/dev/null 2>&1; then pwsh -NoProfile -File scripts/test-install.ps1; else echo "pwsh not found; skipping PowerShell installer tests"; fi

install:
	./install.sh

uninstall:
	./install.sh --uninstall

dry-run:
	./install.sh --dry-run

stack-audit:
	python3 scripts/sync_agent_stack.py
