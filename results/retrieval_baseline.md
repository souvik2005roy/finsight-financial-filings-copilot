# FinSight Retrieval Evaluation — Baseline

Date: 12 October 2026
Corpus: Tata Motors FY2023 and FY2025 annual reports
Queries: 4 manually labelled questions
Metric: Relevant-page recall@4

| Retrieval method | Average recall@4 |
|---|---:|
| BM25 | 0.812 |
| Vector search | 0.750 |
| Standard hybrid | 0.875 |
| Diversified hybrid | 1.000 |

Method:
- Retrieve the top four chunks for each question.
- Count distinct manually labelled relevant pages present in the results.
- Average the recall across four questions.

Limitations:
- Small, manually labelled evaluation set.
- Only one company is represented.
- Relevant pages are known targets, not exhaustive relevance labels.
- Retrieval recall does not establish answer accuracy, citation correctness,
  or financial-data accuracy.
