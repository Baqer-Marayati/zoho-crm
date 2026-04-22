# Convenience targets — requires GNU Make (macOS has it)
.PHONY: venv zoho-venv
venv: zoho-venv

zoho-venv:
	cd tools/zoho && python3 -m venv venv && ./venv/bin/pip install --upgrade pip && ./venv/bin/pip install -r requirements.txt
	@echo "Next: copy tools/zoho/.env.example to tools/zoho/.env and add OAuth values."
