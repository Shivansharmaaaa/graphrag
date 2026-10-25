# Review III deliverables

| Deliverable | File | Built by |
|---|---|---|
| Final report (25 pages) | `Final_Report_GraphRAG_CTI_Platform.pdf` / `.docx` | `node generate_report.js` |
| User manual (18 pages) | `User_Manual_GraphRAG_CTI_Platform.pdf` / `.docx` | `node generate_manual.js` |
| Presentation (21 slides, speaker notes) | `Presentation_GraphRAG_CTI_Platform.pptx` / `.pdf` | `node generate_slides.js` |
| Demo runbook and viva preparation | `DEMO_RUNBOOK.md` | — |
| Performance results | `performance/*.json` | `make bench`, `make eval` |
| Diagrams | `figures/r3_*.png` | `python generate_figures.py` |
| Charts | `figures/chart_*.png` | `python make_charts.py` |
| Console screenshots | `screenshots/*.png` | `node capture_screenshots.js screenshots` |

Every measured number in the report, manual and slides is read from `performance/`, so the documents can be rebuilt after a new benchmark run.

## Rebuilding

```bash
cd review3
npm install                                   # docx, pptxgenjs, playwright-core
pip install pillow matplotlib==3.9.2          # diagrams and charts
python generate_figures.py && python make_charts.py
node capture_screenshots.js screenshots       # needs the demo stack on :5173, Ollama and Google Chrome
node generate_report.js && node generate_manual.js && node generate_slides.js   # need LibreOffice (soffice) and poppler (pdftotext)
```

## Performance data

| File | Contents |
|---|---|
| `benchmark_results.json` | final run, after the fixes: scale 1×–200×, load, Redis, MongoDB, Neo4j, Qdrant |
| `benchmark_baseline_before_fixes.json` | the first scale run, before the four scalability fixes |
| `eval_llama3.2-3b_default.json` | acceptance questions with the default model |
| `eval_llama3.2-3b_budget.json`, `eval_llama3.1_budget.json` | the two models with the prompt budget and gate fix |
| `llm_latency_runs.json` | every LLM latency measurement used in the report, with its source |
