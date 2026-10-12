# FinSight Demo Runbook — Tata Motors pilot

Use the current local pilot paths before launching the app:

```powershell
$env:FINSIGHT_FINANCIALS_CSV = "data/financials_tata_motors_v2.csv"
$env:FINSIGHT_DOCS_DIR = "data/docs"
```

Ensure `LLM_API_KEY` is set privately in the current terminal. Do not capture it in screenshots or logs.

## Demo question 1 — SQL lookup

**Question:** What was Tata Motors' reported EBIT margin in FY2025?

**Expected result:** SQL route; `ebit_margin_pct = 7.9`; cited source label is the financials table.

Previously observed successful response: `Tata Motors reported an EBIT margin of 7.9%.`

## Demo question 2 — SQL comparison

**Question:** How did Tata Motors' reported EBIT margin change from FY2023 to FY2025?

**Expected values:** FY2023 3.6%; FY2025 7.9%; change +4.3 percentage points.

The percentage-point difference is a direct subtraction of the two reported headline margins. Do not substitute operating profit divided by revenue or the separate underlying EBIT margin.

## Demo question 3 — RAG supply-chain risks

**Question:** What supply-chain risks does Tata Motors discuss, including supplier and logistics disruptions, raw-material shortages, and climate-related risks?

Relevant FY2025 PDF pages previously retrieved: 75, 194 and 195. FY2023 PDF page 243 also contains related supplier/procurement risk disclosure. The answer should include citations to the report pages that support each claim.

## Demo question 4 — RAG climate risk

**Question:** How could climate change cause shortages of essential automotive raw materials and affect vulnerable suppliers?

Expected relevant source: `tata_motors_fy2025.pdf`, PDF page 194.

## Presenter notes

- Explain why the router sends numerical questions to SQL and narrative questions to RAG.
- Show the generated SQL and the retrieved evidence pages.
- Mention the small, manually labelled retrieval benchmark and its limitations.
- Explain that the number checker checks whether numeric strings appear in evidence; it is not a complete semantic fact verifier.
- Avoid claiming multi-company coverage or a completed aggregate live evaluation until those are implemented and measured.
