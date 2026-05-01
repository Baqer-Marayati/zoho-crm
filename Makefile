# Convenience targets — requires GNU Make (macOS has it)
.PHONY: help docs-help venv zoho-venv zoho-setup zoho-connect zoho-exchange zoho-ping zoho-doctor zoho-provision-pipelines zoho-sync-pipelines zoho-deal-stage-labels zoho-merge-proposal-quote-stage zoho-pipeline-refresh zoho-provision-teamspace-direct-department zoho-quote-template zoho-quote-template-replace zoho-quote-line-extensions zoho-quoted-line-deps zoho-quote-line-product-first-layout zoho-quote-line-hide-sku zoho-quote-line-machine-sku-wf zoho-cpq-product-configurator-pilot zoho-sync-canon-product-descriptions zoho-sync-product-catalog zoho-upload-canon-product-pdfs zoho-upload-product-images zoho-audit-zoho-products zoho-phase2-fields zoho-phase2-layouts zoho-phase2-tracking zoho-deals-quotes-process zoho-deals-stage-visibility-client-script zoho-audit-lead-conversion zoho-lead-layout-hide zoho-align-unused-from-leads zoho-lead-address-iraq zoho-lead-country-iraq-wf zoho-lead-country-iraq-client-script zoho-leads-industry-sector zoho-delete-lead-address-iraq zoho-delete-blueprints zoho-build-canon-products-en zoho-build-canon-five-machines zoho-sync-canon-five-products zoho-phase3 zoho-phase3-products zoho-phase3-canon-products zoho-phase3-canon-five-machines zoho-phase3-canon-colorado zoho-phase3-canon-lfp-me zoho-phase3-verify
.PHONY: zoho-cache-summary zoho-cache-refresh zoho-cache-status

# Default: show common Zoho targets (fast orientation after clone)
help:
	@echo "Zoho-CRM make targets (run from repo root):"
	@echo "  make docs-help           - quick pointers to key docs"
	@echo "  make zoho-setup          - Node (npx) + Python venv + pip deps"
	@echo "  make zoho-connect        - interactive OAuth (writes tools/zoho/.env)"
	@echo "  make zoho-doctor         - token scopes + API smoke checks"
	@echo "  make zoho-cache-summary  - refresh/read compact Zoho metadata cache"
	@echo "  make zoho-sync-pipelines - push stages from pipelines_seed.json"
	@echo "  make zoho-deals-quotes-process | zoho-deals-stage-visibility-client-script"
	@echo "  make zoho-phase2-fields | zoho-phase2-layouts | zoho-phase2-tracking"
	@echo "  make zoho-phase3         - price book, layouts, etc. (see tools/zoho/README)"
	@echo "  make zoho-phase3-products - Wave A import only (CSV must be ready)"
	@echo "  make zoho-build-canon-*  - rebuild Canon EN / five-machines CSVs"
	@echo "  make zoho-quote-template-replace - push Aljazeera Quotation PDF template to Zoho"
	@echo "Full list: grep '^zoho' Makefile | cut -d: -f1 | sort -u"

# Fast docs orientation for new contributors and agents
docs-help:
	@echo "Zoho docs entrypoints:"
	@echo "  docs/zoho/INDEX.md                  - single navigation page"
	@echo "  docs/zoho/IMPLEMENTATION-CHECKLIST.md - phased execution order"
	@echo "  docs/PROJECT-STATUS.md              - current scope and next actions"
	@echo "  docs/zoho/REPO-LAYOUT.md            - folder map (docs, tools, artifacts)"
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

# Local metadata cache (auto-refreshes when stale) to reduce Zoho API calls + AI context
zoho-cache-summary:
	cd tools/zoho && ./venv/bin/python zoho_metadata_cache.py summary

# Force-refresh the local metadata cache after changing Zoho metadata
zoho-cache-refresh:
	cd tools/zoho && ./venv/bin/python zoho_metadata_cache.py refresh

# Show cache age/path without calling Zoho
zoho-cache-status:
	cd tools/zoho && ./venv/bin/python zoho_metadata_cache.py status

# Create pipelines from tools/zoho/pipelines_seed.json (needs settings OAuth scopes)
zoho-provision-pipelines:
	cd tools/zoho && ./venv/bin/python provision_pipelines.py

# Push stage changes from seed to existing Zoho pipelines (Production, MPS, …)
zoho-sync-pipelines:
	cd tools/zoho && ./venv/bin/python provision_pipelines.py --sync

# Deals Stage picklist labels → match pipelines_seed.json (rename in place + add missing)
zoho-deal-stage-labels:
	cd tools/zoho && ./venv/bin/python provision_deal_stage_picklist.py

# Full pipeline refresh: Stage labels, Standard pipeline order, Stage→Lost/Competitor maps
zoho-pipeline-refresh:
	$(MAKE) zoho-deal-stage-labels zoho-sync-pipelines zoho-phase2-layouts zoho-merge-proposal-quote-stage

# Merge live Deals/automation from removed Solution/Value + Quote Sent stages into Proposal / Quote
zoho-merge-proposal-quote-stage:
	cd tools/zoho && ./venv/bin/python merge_proposal_quote_stage.py

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

# Deals + Quotes: custom fields, layouts, workflows, Deluge guards, API gap probe
zoho-deals-quotes-process:
	cd tools/zoho && ./venv/bin/python provision_deals_quotes_process.py

# Deals: progressive field visibility client script. See AUTOMATION-STACK §4.1 for Safari/internal cscript flow.
zoho-deals-stage-visibility-client-script:
	cd tools/zoho && ./venv/bin/python provision_deals_stage_visibility_client_script.py

# Read-only: print lead → deal conversion mapping from Zoho metadata API
zoho-audit-lead-conversion:
	cd tools/zoho && ./venv/bin/python audit_lead_conversion_mapping.py

# Move selected Standard Leads form fields to Unused (hide on Create/Edit) — see provision_lead_layout_hide_fields.py
zoho-lead-layout-hide:
	cd tools/zoho && ./venv/bin/python provision_lead_layout_hide_fields.py

# Accounts / Contacts / Deals: move same standard fields to Unused as on Leads — see provision_align_unused_from_leads.py
zoho-align-unused-from-leads:
	cd tools/zoho && ./venv/bin/python provision_align_unused_from_leads.py

# Leads: workflow sets standard Address Country / Region to Iraq on every create/edit (see provision_lead_country_iraq_workflow.py)
zoho-lead-country-iraq-wf:
	cd tools/zoho && ./venv/bin/python provision_lead_country_iraq_workflow.py

# Leads: client script sets/locks standard Address Country / Region to Iraq on create/edit forms
zoho-lead-country-iraq-client-script:
	cd tools/zoho && ./venv/bin/python provision_lead_country_iraq_client_script.py

# Leads: Industry picklist (OCRD list) + Sector picklist — see provision_leads_industry_sector.py
zoho-leads-industry-sector:
	cd tools/zoho && ./venv/bin/python provision_leads_industry_sector.py

# Add Iraq-specific Country / Province / City picklists to Standard Leads Address Information
zoho-lead-address-iraq:
	cd tools/zoho && ./venv/bin/python provision_lead_address_iraq.py

# Remove Iraq custom Leads address picklists + map dependency (see delete_lead_address_iraq_fields.py)
zoho-delete-lead-address-iraq:
	cd tools/zoho && ./venv/bin/python delete_lead_address_iraq_fields.py

# Delete all Blueprint definitions (see provision_delete_blueprints.py)
zoho-delete-blueprints:
	cd tools/zoho && ./venv/bin/python provision_delete_blueprints.py

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

# Quoted_Items: Deluge + workflow to build dynamic line Description from product configuration
zoho-quote-line-description-wf:
	cd tools/zoho && ./venv/bin/python provision_quote_line_description_workflow.py

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

# Quote PDF — Aljazeera Quotation (inventory template HTML from provision_quote_template.py)
zoho-quote-template:
	cd tools/zoho && ./venv/bin/python provision_quote_template.py

# Same but delete+recreate in Zoho (template id changes) — use after editing build_html()
zoho-quote-template-replace:
	cd tools/zoho && ./venv/bin/python provision_quote_template.py --replace
