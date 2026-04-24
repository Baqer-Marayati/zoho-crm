# Archived Zoho API seeds

| File | Note |
|------|------|
| [`pipelines_seed.radiology.json`](pipelines_seed.radiology.json) | **Superseded** — use **Line of business = Radiology** on Lead/Deal; `pipelines_seed.json` in the parent folder defines the live **Standard (Standard)** pipeline. |

Re-run with an alternate seed: `cd tools/zoho && ./venv/bin/python provision_pipelines.py --seed archive/pipelines_seed.radiology.json` (rare; verify stage labels in Zoho first).
