# Convenience targets — requires GNU Make (macOS has it)
.PHONY: venv zoho-venv zoho-connect zoho-exchange zoho-ping zoho-provision-pipelines zoho-sync-pipelines zoho-phase2-fields zoho-phase2-layouts zoho-phase2-tracking zoho-phase3 zoho-phase3-verify
venv: zoho-venv

zoho-venv:
	cd tools/zoho && python3 -m venv venv && ./venv/bin/pip install --upgrade pip && ./venv/bin/pip install -r requirements.txt
	@echo "Next: cd tools/zoho && ./venv/bin/python connect_zoho.py  (interactive; secrets stay local)"

# Interactive OAuth + ping — run in Terminal; do not paste secrets into chat
zoho-connect:
	cd tools/zoho && ./venv/bin/python connect_zoho.py

# Run only after .env has grant code (see tools/zoho/README.md)
zoho-exchange:
	cd tools/zoho && ./venv/bin/python exchange_grant.py

zoho-ping:
	cd tools/zoho && ./venv/bin/python zoho_ping.py

# Create pipelines from tools/zoho/pipelines_seed.json (needs settings OAuth scopes)
zoho-provision-pipelines:
	cd tools/zoho && ./venv/bin/python provision_pipelines.py

# Push stage changes from seed to existing Zoho pipelines (Production, MPS, …)
zoho-sync-pipelines:
	cd tools/zoho && ./venv/bin/python provision_pipelines.py --sync

# Phase 2 picklists (Line of business, Lost Reason, Competitor) — needs settings.fields scope
zoho-phase2-fields:
	cd tools/zoho && ./venv/bin/python provision_phase2_fields.py

# Phase 2 Deals layout: Closing Date + Lost/Competitor required + Stage map dependencies
zoho-phase2-layouts:
	cd tools/zoho && ./venv/bin/python provision_phase2_layouts.py

# Phase 2 §5 probe (stage-probability API) + §6 field history tracking (Stage, Amount)
zoho-phase2-tracking:
	cd tools/zoho && ./venv/bin/python provision_phase2_tracking.py

# Phase 3: IQD price book, Wave A products, Quote/Deal layout fields, attachments check
zoho-phase3:
	cd tools/zoho && ./venv/bin/python provision_phase3.py

# Phase 3 verify-only: confirm price book, products, fields, attachments (no changes)
zoho-phase3-verify:
	cd tools/zoho && ./venv/bin/python provision_phase3.py --verify
