# FinSight — Financial Filings Copilot

A single-company GenAI prototype that answers questions over Tata Motors annual reports by routing numeric questions to SQLite and narrative questions to Retrieval-Augmented Generation (RAG). Answers include report-page citations, and a numeric evidence checker flags selected unsupported numbers.

> **Project status:** Tata Motors pilot. The code, retrieval benchmark, and local data checks are implemented. A full live-LLM answer-accuracy benchmark is not yet complete because Gemini API quota limits interrupted the run.

## What it does

- **Question routing:** uses a language model to decide whether a question needs structured financial data (`sql`) or annual-report text (`docs`).
- **Text-to-SQL:** generates a read-only SQL query over the financial table and returns an answer grounded in query results.
- **Hybrid RAG:** combines BM25 keyword retrieval with `all-MiniLM-L6-v2` vector similarity and Reciprocal Rank Fusion (RRF).
- **Page-aware evidence:** preserves document filename, PDF page number and chunk ID for retrieved passages.
- **Page-diverse context selection:** reduces repeated chunks from the same PDF page before generation.
- **Numeric evidence check:** compares numeric claims in the answer with retrieved evidence and flags selected unmatched numbers.
- **Evaluation utilities:** includes unit tests, a local/offline evaluation script, a retrieval comparison script and a five-question live evaluation script.

## Architecture

```text
Question
   |
   v
LLM router
   |------------------------------|
   v                              v
Financial question                Narrative question
   |                              |
Text-to-SQL                       PDF page-aware chunks
   |                              |
Read-only SQL guard                BM25 + vector search
   |                              |
SQLite financial table             RRF + page diversity
   |                              |
LLM answer                         LLM answer with citations
   |------------------------------|
                  v
        Numeric evidence checker
                  |
                  v
        Answer + sources + warnings
```

## Current Tata Motors dataset

The pilot uses two public reports saved locally:

- `data/docs/tata_motors_fy2023.pdf` — FY2022–23 annual report.
- `data/docs/tata_motors_fy2025.pdf` — FY2024–25 annual report.

The financial table contains three annual records (FY2023, FY2024 and FY2025) and includes revenue, operating profit, profit for the year, headline EBIT/EBITDA margins, net automotive debt/cash, and the separately defined underlying EBIT margin where recorded. `data/financial_sources.csv` associates each observation with a report file, PDF page, label and notes about its definition.

The source register and CSV are checked for internal consistency. This does **not** independently guarantee every value was transcribed correctly; source labels, accounting definitions and reporting basis still require manual review. In particular, headline EBIT margin, underlying EBIT margin, operating profit divided by revenue, total debt and net automotive debt/cash are different concepts and must not be interchanged.

**Important:** Do not redistribute the annual-report PDFs in a public repository unless you have checked the applicable terms. Download the reports from the official company source and save them under the exact filenames above. Page references use 1-based PDF page order, which can differ from printed page numbers.

## Tech stack

- Python 3.12
- pandas and SQLite
- `pypdf` for PDF text extraction
- `rank-bm25` for keyword retrieval
- Sentence Transformers (`all-MiniLM-L6-v2`) for embeddings
- Reciprocal Rank Fusion (RRF) and page-diverse selection
- Gemini through its OpenAI-compatible API
- pytest for automated tests
- FastAPI for an optional REST interface

## Setup (Windows PowerShell)

Run commands from the project root (for example, `E:\Self\finsight`). If PowerShell blocks virtual-environment activation, call `.venv\Scripts\python.exe` directly as shown below.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Set the data paths for this pilot:

```powershell
$env:FINSIGHT_FINANCIALS_CSV = "data/financials_tata_motors_v2.csv"
$env:FINSIGHT_DOCS_DIR = "data/docs"
$env:LLM_MODEL = "gemini-3.8-flash"
```

Set the API key privately in the terminal. Do not paste it into source files, chat messages, screenshots, or Git:

```powershell
$keySecure = Read-Host "Enter Gemini API key" -AsSecureString
$env:LLM_API_KEY = (New-Object System.Net.NetworkCredential("", $keySecure)).Password.Trim()
```

API availability and rate limits depend on the Google AI Studio project and its quota. A `429` quota error cannot necessarily be fixed by retrying; check the configured model's quota before running the live evaluation repeatedly.

## Run FinSight

### Command-line chat

```powershell
.\.venv\Scripts\python.exe .\app.py
```

Try questions such as:

- `What was Tata Motors' reported EBIT margin in FY2025?`
- `How did its reported EBIT margin change from FY2023 to FY2025?`
- `What supply-chain risks does Tata Motors discuss, including supplier and logistics disruptions, raw-material shortages, and climate-related risks?`

### REST API

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --port 8000
```

Open `http://127.0.0.1:8000/docs` to inspect the API documentation and try the `/ask` endpoint.

## Tests and evaluation

### Unit tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

### Local evaluation — no Gemini calls

```powershell
.\.venv\Scripts\python.exe .\evaluate_local.py
```

This checks financial CSV/source-register consistency, direct SQLite results and calculations, offline retrieval recall, and selected number-checker behavior.

### Retrieval comparison

```powershell
.\.venv\Scripts\python.exe .\evaluate_retrieval.py
```

The current four-query manually labelled benchmark reported the following top-four relevant-page recall:

| Method | Average recall@4 |
|---|---:|
| BM25 | 0.812 |
| Vector search | 0.750 |
| Standard hybrid | 0.875 |
| Diversified hybrid | 1.000 |

These are preliminary results on four manually labelled questions for one company's reports. Relevant-page recall is **not** answer accuracy, faithfulness, or a production-quality evaluation. Do not generalize this result to other companies without a larger independently reviewed test set.

### Live end-to-end evaluation — uses Gemini quota

```powershell
.\.venv\Scripts\python.exe .\evaluate_answers.py
```

This tests routing, SQL answer values, expected RAG source pages and citation matching on a small five-question pilot. The first complete run was interrupted by Gemini `503` high demand and `429` quota exhaustion, so a valid aggregate live answer-accuracy score is not yet available. Do not report those failed requests as 0% model accuracy.

## Known limitations

- Only one company and three annual financial rows are included; this is not yet a multi-company financial copilot.
- The retrieval benchmark contains four manually labelled questions and is too small for broad performance claims.
- A correct source citation does not prove the generated claim is fully supported; citation faithfulness needs more robust checks.
- The number checker is a heuristic, not a semantic fact verifier. It can miss incorrect claims or flag legitimate values depending on wording and evidence formatting.
- Text-to-SQL can produce a plausible but incorrect query or use the wrong metric; queries and financial definitions need testing.
- Questions requiring SQL and report-text evidence in one combined answer are not implemented as a dedicated multi-hop flow.
- The final live LLM evaluation is pending a successful run within the available API quota.
- No public deployment or multi-company ingestion pipeline is included in this pilot.

## Suggested next improvements

1. Expand the independently verified evaluation set and complete the live answer-accuracy run when API quota is available.
2. Add more companies only after defining consistent metric mappings, units, reporting basis and source provenance.
3. Improve claim-level citation and numeric verification, and add a combined SQL + RAG route for questions that need both structured and narrative evidence.
4. Add a user interface and deployment after reliability checks pass.

## Security and data handling

- Never commit API keys or `.env` files.
- Keep `.venv`, cache folders, logs containing secrets and temporary files out of version control.
- Check the licence/terms before redistributing downloaded annual reports.
- Disclose the single-company scope and preliminary benchmark results accurately in demos and interviews.
