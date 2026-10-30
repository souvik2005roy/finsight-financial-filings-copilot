# FinSight — Financial Filings Copilot

FinSight is a **single-company GenAI prototype** for asking questions about Tata Motors' financial data and annual reports. It routes questions to structured SQL, retrieval-augmented generation (RAG), or a combined SQL + RAG workflow. The application is built with Python, SQLite, hybrid document retrieval, Gemini, and Streamlit.

> **Project scope:** Tata Motors pilot covering three annual financial records (FY2023–FY2025) and two annual reports. This is a portfolio prototype, not a production financial-advice system or a multi-company platform.

## Features

- **Three-way question routing:** classifies questions as `sql`, `docs`, or `both`.
- **Text-to-SQL:** generates read-only SQLite queries against the financial table, with a SQL safety check.
- **Hybrid RAG:** combines BM25 keyword retrieval and `all-MiniLM-L6-v2` vector retrieval using Reciprocal Rank Fusion (RRF).
- **Page-aware retrieval:** retains PDF filenames, PDF page numbers, and chunk identifiers for source traceability.
- **Page diversification:** reduces repeated chunks from the same report page in the retrieved context.
- **Focused retrieval for combined questions:** separates the narrative part of a mixed financial-and-risk question from its numerical wording before searching annual reports.
- **Combined SQL + RAG answers:** supplies SQL results and retrieved report passages to the answer-generation step.
- **Answer checks:** flags selected unsupported numeric claims and PDF page citations that do not match the retrieved-source list. Grouped page citations are supported.
- **Streamlit chat UI:** displays the answer route, sources, generated SQL, evidence, and separate validation warnings.
- **Offline evaluation:** checks financial/source-register consistency, SQL calculations, retrieval recall, and selected number-checker behaviour.

## Architecture

```text
                              User question
                                    |
                                    v
                              Gemini router
                                    |
                 +------------------+------------------+
                 |                  |                  |
                SQL                DOCS               BOTH
                 |                  |                  |
          Text-to-SQL        PDF text chunks      Original question
                 |                  |                  |
          Read-only guard    BM25 + embeddings          +------------------+
                 |                  |                                     |
             SQLite DB          RRF ranking                     Text-to-SQL
                 |                  |                                     |
                 |          Page diversification                  SQLite DB
                 |                  |                                     |
                 |            RAG context                                  |
                 |                  |                                     |
                 +------------------+-------------------------------------+
                                    |
                           Answer generation
                                    |
                    +---------------+---------------+
                    |                               |
             Numeric checker                 Citation matcher
                    |                               |
                    +---------------+---------------+
                                    |
                         Answer + metadata + warnings
                                    |
                              Streamlit UI
```

### Route behaviour

| Route | Typical question | Evidence source |
|---|---|---|
| `sql` | “What was reported EBIT margin in FY2025?” | SQLite financial table and query result |
| `docs` | “What supply-chain risks are discussed?” | Retrieved annual-report passages |
| `both` | “How did EBIT margin change, and what supply-chain risks could affect performance?” | SQL result plus focused annual-report retrieval |

For `both` questions, the original question is used for the SQL step. A focused narrative query is derived for the report-retrieval step so that financial terms do not dominate the RAG search.

## Data included in the pilot

### Financial dataset

The application uses:

- `data/financials_tata_motors_v2.csv` — three annual records for FY2023, FY2024, and FY2025.
- `data/financial_sources.csv` — source register connecting financial observations to report filenames, PDF pages, labels, and definition notes.

The financial table includes fields such as revenue, operating profit, net profit, total debt, employees, reported EBIT/EBITDA margins, net automotive debt, and underlying EBIT margin where recorded.

### Annual reports

Place the following PDFs in `data/docs/`:

- `tata_motors_fy2023.pdf` — FY2022–23 annual report.
- `tata_motors_fy2025.pdf` — FY2024–25 annual report.

The PDFs are not included in this repository. Obtain them from an authorized source and check the applicable terms before redistributing them. The application’s citation labels use **1-based PDF page order**, which may differ from the printed page number in the report.

### Financial-definition caution

Do not treat these as interchangeable:

- reported EBIT margin;
- underlying EBIT margin excluding discontinued operations;
- operating profit divided by revenue;
- total debt; and
- net automotive debt/cash.

For example, the dataset records reported EBIT margins of 3.6% in FY2023 and 7.9% in FY2025, a change of **+4.3 percentage points**. That is a direct difference between the two reported margin values; it is not a percentage growth rate and should not be recomputed from unrelated financial fields.

The validation script confirms internal consistency between the financial CSV and source register. It does **not** independently prove that every value was transcribed correctly from the original report; source figures and accounting definitions still require manual review.

## Technology stack

- Python 3.12
- pandas and SQLite
- `pypdf` for PDF text extraction
- `rank-bm25` for keyword retrieval
- Sentence Transformers with `all-MiniLM-L6-v2` for embeddings
- Reciprocal Rank Fusion (RRF) and page-diverse selection
- Gemini through an OpenAI-compatible API client
- Streamlit for the chat interface
- FastAPI for the optional REST endpoint
- pytest for automated tests

## Setup — Windows PowerShell

Run commands from the project root, for example `E:\Self\finsight`.

### 1. Create the environment and install dependencies

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If PowerShell blocks virtual-environment activation, continue using `.\.venv\Scripts\python.exe` directly as shown above.

### 2. Add the data files

Create the report directory if it does not already exist:

```powershell
New-Item -ItemType Directory -Force .\data\docs | Out-Null
```

Place the two annual-report PDFs in `data/docs/` using the exact filenames listed in the [Data included in the pilot](#annual-reports) section. Ensure the Tata Motors financial CSV and source register are in `data/`.

### 3. Configure environment variables

```powershell
$env:FINSIGHT_FINANCIALS_CSV = "data/financials_tata_motors_v2.csv"
$env:FINSIGHT_DOCS_DIR = "data/docs"
```

Set `LLM_MODEL` to a Gemini model available to your Google AI Studio project if you need to override the default configured in `llm.py`:

```powershell
$env:LLM_MODEL = "<your-enabled-gemini-model>"
```

Enter the API key privately in the current PowerShell session. The secure prompt does not display the characters as you type or paste:

```powershell
$keySecure = Read-Host "Enter Gemini API key" -AsSecureString
$env:LLM_API_KEY = (New-Object System.Net.NetworkCredential("", $keySecure)).Password.Trim()
Remove-Variable keySecure
```

Do not paste API keys into source code, chat messages, screenshots, README files, or Git. These environment variables apply to the current terminal session. If you open a new terminal, configure them again. API availability and rate limits depend on the Google AI Studio project and selected model. A quota or service error does not represent model-answer accuracy.

## Run the application

### Streamlit interface

```powershell
.\.venv\Scripts\python.exe -m streamlit run .\streamlit_app.py
```

Open the local URL printed by Streamlit (typically `http://localhost:8501`). The interface shows the route, sources, generated SQL, evidence, and checker warnings.

### Command-line interface

```powershell
.\.venv\Scripts\python.exe .\app.py
```

### REST API (optional)

```powershell
.\.venv\Scripts\python.exe -m uvicorn api:app --port 8000
```

Open `http://127.0.0.1:8000/docs` to inspect the FastAPI documentation and try the `/ask` endpoint.

## Demo questions

### 1. SQL — financial lookup

**Question:** What was Tata Motors' consolidated revenue from operations in FY2025?

Expected dataset value: **₹4,39,695 crore**. The UI should show the SQL route, generated query, and SQL result.

### 2. SQL — financial comparison

**Question:** How did Tata Motors' reported EBIT margin change from FY2023 to FY2025?

Expected dataset values: FY2023 **3.6%**, FY2025 **7.9%**, change **+4.3 percentage points**.

### 3. RAG — narrative risk research

**Question:** What supply-chain risks does Tata Motors discuss, including supplier and logistics disruptions, raw-material shortages, and climate-related risks?

Relevant pages found in previous retrieval runs include FY2025 PDF pages **75, 194, and 195**, and FY2023 PDF pages **86, 243, and 244**. The exact top-four passages may vary with the query and retrieval implementation. The answer should cite only pages actually supplied to the generator.

### 4. Combined SQL + RAG

**Question:** How did Tata Motors' reported EBIT margin change from FY2023 to FY2025, and what supply-chain risks could affect its future financial performance?

Expected SQL values: **3.6%**, **7.9%**, and **+4.3 percentage points**. The narrative portion should be supported by retrieved annual-report passages.

## Tests and evaluation

### Automated tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The latest recorded test run collected and passed **52 tests**. Run the suite again after making changes; the result can differ if the code or environment changes.

### Offline validation — no Gemini calls

```powershell
.\.venv\Scripts\python.exe .\evaluate_local.py
```

The latest successful offline run reported:

- Financial rows: 3.
- Source-register records: 20; values matched: 20/20.
- Duplicate company/year rows: 0; duplicate source keys: 0.
- SQLite financial checks: PASS.
- Retrieval corpus: 6,779 indexed chunks.
- Number-checker sanity tests: PASS.
- Live Gemini calls during this evaluation: 0.

### Retrieval benchmark

The manually labelled four-query benchmark reported the following average relevant-page recall at the top four retrieved results:

| Retrieval method | Average recall@4 |
|---|---:|
| BM25 | 0.812 |
| Vector search | 0.750 |
| Standard hybrid | 0.875 |
| Hybrid-diverse | 1.000 |

These are preliminary results on **four manually labelled questions** for one company's reports. Recall@4 measures retrieval of labelled relevant pages; it is **not** answer accuracy, claim faithfulness, or proof of broad retrieval performance. The focused narrative-query tests also check query construction, but they do not by themselves establish improved end-to-end answer accuracy.

### Live LLM evaluation

The repository includes `evaluate_answers.py` for a small end-to-end evaluation. Earlier attempts were interrupted by Gemini service errors and quota exhaustion, so a complete, reliable aggregate live answer-accuracy score is **not currently reported**. Selected manual Streamlit checks have exercised the SQL, RAG, and combined routes, but they are not a substitute for a complete benchmark.

## Verification design and limitations

- **Numerical checker:** a heuristic compares selected numeric claims in the generated answer with the evidence text and flags values it cannot match. It is not a semantic fact verifier and can produce false positives or miss unsupported claims. A `5.0` warning appeared in one combined-answer demonstration and was not fully diagnosed; do not silently suppress such warnings.
- **Citation checker:** checks whether PDF filename/page references in the answer appear in the retrieved-source list. It supports grouped page citations, but source-list matching does not prove that the cited passage entails or supports the claim.
- **Text-to-SQL:** read-only validation prevents common write/DDL operations, but it does not guarantee that every generated SELECT query expresses the intended accounting metric. Review query output and financial definitions.
- **Routing:** route selection depends on the LLM classifier; API availability, latency, and model behaviour can affect a live request.
- **Scope:** this pilot covers one company, three annual financial records, and two annual reports. It has no multi-company ingestion pipeline or public production deployment.

## Security and data handling

- Never commit API keys, `.env` files, or terminal history containing secrets.
- Keep `.venv`, caches, temporary files, and local report PDFs out of version control unless there is a specific reason and redistribution is permitted.
- Verify annual-report values and definitions against the original documents before relying on them.
- Do not present the prototype as investment advice or a production-grade financial system.

## Future work

Potential next steps, outside the current pilot scope:

1. Expand the independently reviewed retrieval and answer-evaluation datasets.
2. Complete a quota-available live end-to-end evaluation and report answer-level metrics.
3. Improve claim-level evidence entailment and reduce false positives in numerical verification.
4. Extend the data model and source validation before adding more companies.
5. Add deployment and operational monitoring only after reliability and data governance requirements are defined.
