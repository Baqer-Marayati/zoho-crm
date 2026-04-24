# Convenience targets — requires GNU Make (macOS has it)
.PHONY: help docs-help venv zoho-venv zoho-setup zoho-connect zoho-exchange zoho-ping zoho-doctor zoho-provision-pipelines zoho-sync-pipelines zoho-provision-teamspace-direct-department zoho-quote-line-extensions zoho-quoted-line-deps zoho-quote-line-product-first-layout zoho-quote-line-hide-sku zoho-quote-line-machine-sku-wf zoho-cpq-product-configurator-pilot zoho-sync-canon-product-descriptions zoho-sync-product-catalog zoho-upload-canon-product-pdfs zoho-upload-product-images zoho-audit-zoho-products zoho-phase2-fields zoho-phase2-layouts zoho-phase2-tracking zoho-audit-lead-conversion zoho-build-canon-products-en zoho-build-canon-five-machines zoho-sync-canon-five-products zoho-phase3 zoho-phase3-products zoho-phase3-canon-products zoho-phase3-canon-five-machines zoho-phase3-canon-colorado zoho-phase3-canon-lfp-me zoho-phase3-verify

# Default: show common Zoho targets (fast orientation after clone)
help:
	@echo "Zoho-CRM make targets (run from repo root):"
	@echo "  make docs-help           - quick pointers to key docs"
	@echo "  make zoho-setup          - Node (npx) + Python venv + pip deps"
	@echo "  make zoho-connect        - interactive OAuth (writes tools/zoho/.env)"
	@echo "  make zoho-doctor         - token scopes + API smoke checks"
	@echo "  make zoho-sync-pipelines - push stages from pipelines_seed.json"
	@echo "  make zoho-phase2-fields | zoho-phase2-layouts | zoho-phase2-tracking"
	@echo "  make zoho-phase3         - price book, layouts, etc. (see tools/zoho/README)"
	@echo "  make zoho-phase3-products - Wave A import only (CSV must be ready)"
	@echo "  make zoho-build-canon-*  - rebuild Canon EN / five-machines CSVs"
	@echo "Full list: grep '^zoho' Makefile | cut -d: -f1 | sort -u"

# Fast docs orientation for new contributors and agents
docs-help:
	@echo "Zoho docs entrypoints:"
	@echo "  docs/zoho/INDEX.md                  - single navigation page"
	@echo "  docs/zoho/IMPLEMENTATION-CHECKLIST.md - phased execution order"
	@echo "  docs/PROJECT-STATUS.md              - current scope and next actions"
	@echo "  tools/zoho/README.md                - script usage and make targets"
	@echo "  docs/zoho/archive/README.md         - archived decisions and rounds"
venv: zoho-venv

# Node (npx → mcp-remote for Zoho MCP in Cursor) + Python venv. Re-run after cloning or OS reinstall.
zoho-setup:
	@if ! command -v node >/dev/null 2>&1; then \
	  if test -x /opt/homebrew/bin/brew; then \
	    /opt/homebrew/bin/brew install node; \
	  else \
	    echo "Install Node.js (https://nodejs.org/ LTS or brew install node) so npx can run Zoho MCP’s mcp-remote bridge."; \
	    exit 1; \
	  fi; \
	fi
	PATH="/opt/homebrew/bin:$$PATH" $(MAKE) zoho-venv
	@PATH="/opt/homebrew/bin:$$PATH" node -v && PATH="/opt/homebrew/bin:$$PATH" npx -v && echo "Zoho dev toolchain ready (API: tools/zoho/venv; MCP: paste JSON from https://mcp.zoho.com → Connect → Cursor)."

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

# Token scope + Zoho API connectivity (Leads, settings, automation, optional __apis index)
zoho-doctor:
	cd tools/zoho && ./venv/bin/python zoho_doctor.py

# Create pipelines from tools/zoho/pipelines_seed.json (needs settings OAuth scopes)
zoho-provision-pipelines:
	cd tools/zoho && ./venv/bin/python provision_pipelines.py

# Push stage changes from seed to existing Zoho pipelines (Production, MPS, …)
zoho-sync-pipelines:
	cd tools/zoho && ./venv/bin/python provision_pipelines.py --sync

# Next Gen teamspace "Direct department" from artifacts/zoho/teamspace/direct_department.json
zoho-provision-teamspace-direct-department:
	cd tools/zoho && ./venv/bin/python provision_teamspace.py

# Phase 2 picklists (Line of business, Lost Reason, Competitor) — needs settings.fields scope
zoho-phase2-fields:
	cd tools/zoho && ./venv/bin/python provision_phase2_fields.py

# Phase 2 Deals layout: Closing Date + Lost/Competitor required + Stage map dependencies
zoho-phase2-layouts:
	cd tools/zoho && ./venv/bin/python provision_phase2_layouts.py

# Phase 2: stage-probability API probe + field history tracking (Stage, Amount)
zoho-phase2-tracking:
	cd tools/zoho && ./venv/bin/python provision_phase2_tracking.py

# Read-only: print lead → deal conversion mapping from Zoho metadata API
zoho-audit-lead-conversion:
	cd tools/zoho && ./venv/bin/python audit_lead_conversion_mapping.py

# Rebuild English Canon catalog CSV from * EN.rtf under Dropbox …/Canon machine specs for SAP
zoho-build-canon-products-en:
	cd tools/zoho && ./venv/bin/python build_canon_products_en_csv.py

# Flat EN CSV → five machine products + manifest (canon_product_line/)
zoho-build-canon-five-machines:
	cd tools/zoho && ./venv/bin/python build_canon_five_machines_csv.py

# Phase 3: IQD price book, Wave A products, Quote/Deal layout fields, attachments check
zoho-phase3:
	cd tools/zoho && ./venv/bin/python provision_phase3.py

# Wave A products only (CSV must have real SKUs — no "example sku" placeholder text)
zoho-phase3-products:
	cd tools/zoho && ./venv/bin/python provision_phase3.py --step 2

# Wave A: import canon_products_wave_a_en.csv (names + descriptions; no SKU; Unit_Price 0 until you edit CSV)
zoho-phase3-canon-products:
	cd tools/zoho && ./venv/bin/python provision_phase3.py --step 2 --products-csv ../../artifacts/zoho/import/canon_products_wave_a_en.csv

# Five consolidated Canon machine products (SKUs CANON-VP6K-TITAN, …)
zoho-phase3-canon-five-machines:
	cd tools/zoho && ./venv/bin/python provision_phase3.py --step 2 --products-csv ../../artifacts/zoho/import/canon_products_five_machines_en.csv

# Canon Colorado wide-format products (CANON-COLO-M-SER, CANON-COLO-1650)
zoho-phase3-canon-colorado:
	cd tools/zoho && ./venv/bin/python provision_phase3.py --step 2 --products-csv ../../artifacts/zoho/import/canon_products_colorado_en.csv

# Canon ME LFP: CAD/GIS plotters + photography/fine-art (imagePROGRAF, colorWAVE, plotWAVE)
zoho-phase3-canon-lfp-me:
	cd tools/zoho && ./venv/bin/python provision_phase3.py --step 2 --products-csv ../../artifacts/zoho/import/canon_products_lfp_me_en.csv

# Delete 23-row Wave-A Canon names in Zoho, then import five-machine CSV (no overlap)
zoho-sync-canon-five-products:
	cd tools/zoho && ./venv/bin/python sync_canon_five_products_zoho.py

# Push Product Description from canon_products_five_machines_en.csv (after editing or rebuild)
zoho-sync-canon-product-descriptions:
	cd tools/zoho && ./venv/bin/python sync_canon_product_descriptions.py

# Push Product_Name + Description for all catalog rows (canon_products_catalog_en.csv)
zoho-sync-product-catalog:
	cd tools/zoho && ./venv/bin/python sync_zoho_products_from_csv.py

# Read-only JSON audit: attachments + Product Image per product
zoho-audit-zoho-products:
	cd tools/zoho && ./venv/bin/python audit_zoho_products.py

# Upload PDFs from Dropbox Canon machine specs folder → Product Attachments
zoho-upload-canon-product-pdfs:
	cd tools/zoho && ./venv/bin/python upload_canon_product_pdfs.py

# Canon official imagery (graphiPLAZA + canon.a.bigcontent.io; local PDF fallback) → Product Image
zoho-upload-product-images:
	cd tools/zoho && ./venv/bin/python upload_zoho_product_web_images.py

# Brochure PDF first page → Product Image (legacy)
zoho-upload-product-images-pdf:
	cd tools/zoho && ./venv/bin/python upload_zoho_product_images.py

# Quote line finisher/POD picklists + product reference text (extensions_by_product_code.json)
zoho-quote-line-extensions:
	cd tools/zoho && ./venv/bin/python provision_quote_line_extensions.py

zoho-quoted-line-deps:
	cd tools/zoho && ./venv/bin/python provision_quoted_line_dependencies.py

# Quoted_Items: rename Machine SKU -> Product (Machine), move Product Name lookup off used layout, sync option ids
zoho-quote-line-product-first-layout:
	cd tools/zoho && ./venv/bin/python provision_quoted_line_product_first_layout.py

# Quoted_Items: move Machine SKU to Unused on line layout (field still in module for Deluge)
zoho-quote-line-hide-sku:
	cd tools/zoho && ./venv/bin/python provision_quoted_line_hide_machine_sku_layout.py

# Quoted_Items: Deluge + workflow to auto-fill Machine SKU (needs workflow + automation OAuth scopes)
zoho-quote-line-machine-sku-wf:
	cd tools/zoho && ./venv/bin/python provision_quoted_line_machine_sku_workflow.py

# CPQ (undocumented API): create a Product Configurator pilot rule — may 500; use --dry-run first
zoho-cpq-product-configurator-pilot:
	cd tools/zoho && ./venv/bin/python provision_cpq_product_configurator_pilot.py

# Phase 3 verify-only: confirm price book, products, fields, attachments (no changes)
zoho-phase3-verify:
	cd tools/zoho && ./venv/bin/python provision_phase3.py --verify

# Quotes: rename Subject label to Reference; then add client script from artifacts/zoho/client_scripts/
zoho-quote-reference-field:
	cd tools/zoho && ./venv/bin/python provision_quote_reference_field.py

# Client Script API for Quotes (GET/PUT) — needs OAuth scope for client_scripts; see script docstring
zoho-quote-client-script:
	cd tools/zoho && ./venv/bin/python provision_quote_client_script.py

# Field rename + push client script (latter no-ops with 401 until client_scripts scope is on the token)
zoho-quote-reference-full:
	cd tools/zoho && ./venv/bin/python provision_quote_reference_field.py && ./venv/bin/python provision_quote_client_script.py
