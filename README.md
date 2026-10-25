# FinSight — Financial Filings Copilot

FinSight is a GenAI-powered financial research assistant that answers questions about Tata Motors using structured financial data and annual-report documents. It routes numerical questions to SQLite through text-to-SQL and narrative questions to Retrieval-Augmented Generation (RAG). Answers include source evidence where available, and a numerical evidence checker flags selected unsupported claims.

> **Project status:** Working single-company Tata Motors pilot. The project includes a Streamlit interface, SQL and RAG answering paths, page-aware retrieval, a heuristic numerical checker, automated tests, offline evaluation, and a quota-aware live evaluation script. A complete live-LLM answer-quality benchmark is still pending because Gemini API timeouts and quota exhaustion interrupted previous runs.

## What It Does

- **Question routing:** Uses a language model to select structured financial data (`sql`) or annual-report text (`docs`).
- **Text-to-SQL:** Generates read-only SQL queries over the financial database and returns answers based on query results.
- **Hybrid RAG:** Combines BM25 keyword retrieval, `all-MiniLM-L6-v2` vector similarity, and Reciprocal Rank Fusion (RRF).
- **Page-aware evidence:** Preserves document filenames, PDF page numbers, and chunk IDs for retrieved passages.
- **Page-diverse retrieval:** Reduces repeated chunks from the same PDF page when selecting evidence for answer generation.
- **Numerical evidence checking:** Flags selected numbers that cannot be matched to the supplied evidence, with heuristic checks for nearby financial metrics and fiscal years.
- **Streamlit interface:** Provides a browser-based chat interface with answers, route information, source citations, generated SQL, SQL evidence, and numerical-checker warnings when available.
- **REST API:** Exposes the application through FastAPI.
- **Evaluation utilities:** Includes automated tests, financial-source consistency checks, offline retrieval evaluation, and live end-to-end evaluation.
- **Quota-aware evaluation:** Separates API failures from completed answer evaluations and records skipped questions when a quota-exhaustion error stops the benchmark.

## Architecture

```text
                         User question
                               |
                               v
                         LLM router
                               |
                  +------------+------------+
                  |                         |
                  v                         v
          Financial question        Narrative question
                  |                         |
                  v                         v
             Text-to-SQL           PDF page-aware chunks
                  |                         |
                  v                         v
          Read-only SQL guard       BM25 + vector search
                  |                         |
                  v                         v
           SQLite financial table    RRF + page diversity
                  |                         |
                  v                         v
              LLM answer             LLM answer + citations
                  |                         |
                  +------------+------------+
                               |
                               v
                     Numerical evidence checker
                               |
                               v
                  Answer + evidence + warnings
                               |
                               v
                    Streamlit / CLI / REST API
```

**Current scope:** SQL and RAG are separate answering paths. Questions that require both financial calculations and narrative evidence do not yet have a dedicated multi-hop answer workflow.

## Current Tata Motors Dataset

The pilot uses two publicly available annual reports that must be downloaded separately and stored locally:

- `data/docs/tata_motors_fy2023.pdf` — Tata Motors FY2022–23 annual report.
- `data/docs/tata_motors_fy2025.pdf` — Tata Motors FY2024–25 annual report.

The financial dataset contains three annual records: FY2023, FY2024, and FY2025. It includes revenue, operating profit, net profit, reported EBIT and EBITDA margins, net automotive debt/cash, and the separately defined underlying EBIT margin where recorded.

The principal financial dataset used by the evaluation script is:

`data/financials_tata_motors_v2.csv`

The source register is:

`data/financial_sources.csv`

The source register associates financial observations with source reports, PDF page numbers, labels, and notes about definitions. Automated validation checks that the financial CSV and source register agree.

**Important data-quality limitation:** Internal consistency does not independently prove that every financial value was transcribed correctly. Source labels, financial definitions, reporting basis, and units still require manual review.

Headline EBIT margin, underlying EBIT margin, operating profit divided by revenue, total debt, and net automotive debt/cash are distinct measures. They must not be used interchangeably.

Annual-report references use **1-based PDF page order**, which can differ from the printed page number shown in the report.

### Financial figures in the current pilot

| Fiscal year | Consolidated revenue (₹ crore) | Operating profit (₹ crore) | Reported EBIT margin |
|---|---:|---:|---:|
| FY2023 | 345,966.97 | 42,491.51 | 3.6% |
| FY2024 | 434,016.00 | 68,831.00 | 8.0% |
| FY2025 | 439,695.00 | 65,848.00 | 7.9% |

These figures are included to document the current pilot dataset, not to replace verification against the original annual reports.

## Tech Stack

- **Language:** Python 3.12
- **Data handling:** pandas
- **Structured storage:** SQLite
- **PDF extraction:** pypdf
- **Keyword retrieval:** rank-bm25
- **Vector retrieval:** Sentence Transformers (`all-MiniLM-L6-v2`)
- **Hybrid retrieval:** Reciprocal Rank Fusion (RRF) and page-diverse context selection
- **LLM integration:** Gemini through an OpenAI-compatible API wrapper
- **Web interface:** Streamlit
- **REST API:** FastAPI and Uvicorn
- **Automated testing:** pytest

## Setup — Windows PowerShell

Run all commands from the project root, for example:

`E:\Self\finsight`

If PowerShell blocks virtual-environment activation, use `.venv\Scripts\python.exe` directly.

### 1. Create the virtual environment and install dependencies

```powershell
python -m venv .venv

.\.venv\Scripts\python.exe -m pip install --upgrade pip

.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The dependencies should include Streamlit, pandas, pypdf, rank-bm25, sentence-transformers, openai, FastAPI, Uvicorn, and pytest.

### 2. Configure the data paths and model

```powershell
$env:FINSIGHT_FINANCIALS_CSV = "data/financials_tata_motors_v2.csv"
$env:FINSIGHT_DOCS_DIR = "data/docs"
$env:LLM_MODEL = "gemini-3.6-flash"
```

The model name is configurable. Use a model currently available to your Google AI Studio project, and update the value when changing models.

### 3. Configure the API key securely

Create or retrieve an API key through [Google AI Studio](https://aistudio.google.com/apikey).

Set it in the current PowerShell session without placing the key in source files:

```powershell
$keySecure = Read-Host "Enter Gemini API key" -AsSecureString

$env:LLM_API_KEY = (
    New-Object System.Net.NetworkCredential("", $keySecure)
).Password.Trim()
```

The environment variable is local to that terminal session. If you open another terminal, configure it again.

**Never commit API keys, paste them into public issues, or include them in screenshots or source code.** If a key is accidentally exposed, revoke it and create a replacement.

API availability and rate limits depend on the model and Google AI Studio project. A `503` response can indicate temporary service unavailability. A quota-exhaustion response may require waiting for the applicable quota to reset or reviewing the project's quota settings. Repeatedly retrying a request does not necessarily solve either problem.

### 4. Download the annual reports

Download the appropriate annual reports from the official company source and save them under the exact filenames listed in the dataset section.

Do not commit or redistribute annual-report PDFs unless the applicable terms permit it. The repository should contain the source code and instructions needed to obtain the data, not automatically include the original PDFs.

## Run FinSight

### Streamlit web interface

Launch the browser-based interface:

```powershell
.\.venv\Scripts\python.exe -m streamlit run .\streamlit_app.py
```

The interface supports financial and narrative questions, displays the generated answer, and exposes supporting details such as citations, SQL, SQL evidence, and numerical-checker warnings when available.

Example questions:

- What was Tata Motors' reported EBIT margin in FY2025?
- How did its reported EBIT margin change from FY2023 to FY2025?
- What supply-chain risks does Tata Motors discuss, including supplier and logistics disruptions, raw-material shortages, and climate-related risks?

### Command-line chat

```powershell
.\.venv\Scripts\python.exe .\app.py
```

### REST API

Start the FastAPI service:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --port 8000
```

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) to inspect the API documentation and try the `/ask` endpoint.

## Tests and Evaluation

### 1. Automated tests

Run the complete test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The most recently observed local run passed **34 tests**. Rerun the command after changing the code to confirm the current result.

The tests cover areas such as numerical checking, citation handling, financial-data validation, SQL safety and calculations, RAG metadata, and evaluation-summary and quota-handling logic.

### 2. Local evaluation — no Gemini calls

```powershell
.\.venv\Scripts\python.exe .\evaluate_local.py
```

The offline evaluation checks:

- Financial CSV and source-register consistency.
- Duplicate company-year rows and source keys.
- SQLite financial results and calculations.
- Retrieval recall on the manually labelled benchmark.
- Selected numerical-checker behaviour.

The latest recorded local run reported that financial data consistency, SQLite checks, retrieval benchmarking, and number-checker sanity checks all passed.

### 3. Retrieval comparison

```powershell
.\.venv\Scripts\python.exe .\evaluate_retrieval.py
```

The current four-query manually labelled benchmark reported the following average top-four relevant-page recall:

| Retrieval method | Average Recall@4 |
|---|---:|
| BM25 | 0.812 |
| Vector search | 0.750 |
| Standard hybrid | 0.875 |
| Diversified hybrid | 1.000 |

These results apply only to the current small, manually labelled benchmark for one company's reports.

**Recall@4 is not answer accuracy, faithfulness, or proof that every cited claim is correct.** The sample is too small to support broad performance claims or generalisation to other companies.

### 4. Live end-to-end evaluation — uses Gemini API quota

```powershell
.\.venv\Scripts\python.exe .\evaluate_answers.py
```

The five-question evaluation covers:

1. FY2025 reported EBIT margin.
2. FY2025 consolidated revenue.
3. EBIT-margin changes from FY2023 to FY2025.
4. Supply-chain risks.
5. Climate and raw-material risks.

It checks the expected route, expected financial numbers for SQL questions, and selected source pages and citation behaviour for narrative questions.

The results are saved to:

`results/answer_eval_latest.json`

The evaluation script distinguishes completed questions from API failures, other evaluation failures, and skipped questions. When a quota-exhaustion error is detected, the remaining questions are marked as skipped. Questions that did not complete are excluded from answer-quality denominators. Where no questions were evaluated, the corresponding metric is recorded as unavailable rather than being presented as 0%.

**Live evaluation status:** A complete end-to-end live benchmark has not yet been obtained. Previous runs were interrupted by Gemini timeouts, `503` high-demand responses, and quota exhaustion. Those infrastructure failures do not establish that the model's answer accuracy is 0%.

Do not report the incomplete benchmark as a valid aggregate answer-accuracy score. Run the live evaluation again only when API access and quota are available.

## Numerical Checker: Scope and Limitations

The checker uses heuristics to flag selected numeric claims that do not match the supplied evidence. It handles citation metadata, fiscal-year labels, small numbers, and contextual associations between values, financial metrics, and years.

It is not a complete semantic fact verifier.

Potential failure modes include:

- A number appearing in evidence under the wrong metric or fiscal year.
- Ambiguous sentences where the nearest metric or year is not the intended association.
- Legitimate values being flagged when evidence formatting is inconsistent.
- Incorrect claims escaping detection because a matching number appears somewhere in the evidence.

Automated tests establish expected behaviour for selected cases; they do not prove that every generated answer is correct. Stronger claim-level verification and independently reviewed evidence remain future improvements.

## Known Limitations

- The dataset covers only Tata Motors, with three annual financial records.
- Only two annual reports are used in the current pilot.
- The manually labelled retrieval benchmark contains four queries and is not large enough for broad performance claims.
- Live LLM answer accuracy has not yet been established by a complete benchmark.
- Citation presence does not guarantee that a claim is fully supported by the cited passage.
- Numerical checking is heuristic and cannot guarantee semantic correctness.
- Text-to-SQL may generate a plausible but incorrect query or use the wrong financial definition.
- Questions requiring SQL and report-text evidence in one combined answer do not yet have a dedicated multi-hop flow.
- A public deployment and multi-company ingestion pipeline are not included in the current pilot.

## Suggested Next Improvements

1. Expand the independently verified evaluation set and complete the live answer-quality benchmark when API access and quota are available.
2. Improve claim-level citation and metric/year verification, including harder edge cases for numerical checking.
3. Add a dedicated combined SQL + RAG workflow for questions that require financial calculations and narrative evidence in one answer.
4. Add more companies only after defining consistent financial metric mappings, units, reporting bases, and source provenance.
5. Polish the existing Streamlit interface and prepare deployment after reliability checks pass.

## Security and Data Handling

- Never commit API keys or `.env` files.
- Keep `.venv`, Python caches, temporary files, and sensitive logs out of version control.
- Check the licensing and usage terms before redistributing annual-report PDFs.
- Keep the financial CSV and its source register traceable to original reports.
- Disclose the single-company scope and preliminary benchmark results accurately in demos, documentation, and interviews.