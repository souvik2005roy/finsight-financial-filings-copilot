from statistics import mean
from rag import Retriever

CASES = [
    {
        "name": "Broad supply-chain risks",
        "question": (
            "What supply-chain risks does Tata Motors discuss, including "
            "supplier and logistics disruptions, raw-material shortages, "
            "and climate-related risks?"
        ),
        "gold_pages": {
            ("tata_motors_fy2025.pdf", 75),
            ("tata_motors_fy2025.pdf", 194),
            ("tata_motors_fy2025.pdf", 195),
            ("tata_motors_fy2023.pdf", 243),
        },
    },
    {
        "name": "Climate and raw materials",
        "question": (
            "How could climate change cause shortages of essential "
            "automotive raw materials and affect vulnerable suppliers?"
        ),
        "gold_pages": {
            ("tata_motors_fy2025.pdf", 194),
        },
    },
    {
        "name": "Revenue and underlying EBIT margin",
        "question": (
            "Compare Tata Motors consolidated revenue from operations "
            "and underlying EBIT margin in FY2025 and FY2024."
        ),
        "gold_pages": {
            ("tata_motors_fy2025.pdf", 154),
        },
    },
    {
        "name": "Supplier disruption consequences",
        "question": (
            "How can supplier and logistics disruptions affect production "
            "costs, lead times, revenue, and profitability?"
        ),
        "gold_pages": {
            ("tata_motors_fy2025.pdf", 75),
        },
    },
]

MODES = [
    ("BM25", "bm25", False),
    ("Vector", "vector", False),
    ("Hybrid", "hybrid", False),
    ("Hybrid-diverse", "hybrid", True),
]

retriever = Retriever("data/docs")
scores = {name: [] for name, _, _ in MODES}

print("Evaluation: top-4 relevant-page recall")
print("Gold pages are manually identified targets, not exhaustive labels.")

for case in CASES:
    print(f"\n{'=' * 68}\n{case['name']}\n")

    for label, mode, diversify in MODES:
        hits = retriever.search(
            case["question"],
            k=4,
            mode=mode,
            diversify_pages=diversify,
        )

        retrieved_pages = {
            (retriever.sources[i], retriever.pages[i])
            for i in hits
        }

        relevant_hits = case["gold_pages"] & retrieved_pages
        recall = len(relevant_hits) / len(case["gold_pages"])
        scores[label].append(recall)

        pages = [
            f"{retriever.sources[i]}:{retriever.pages[i]}"
            for i in hits
        ]

        print(
            f"{label:16} recall@4={recall:.2f} "
            f"({len(relevant_hits)}/{len(case['gold_pages'])})"
        )
        print(" " * 18 + " | ".join(pages))

print(f"\n{'=' * 68}\nAVERAGE PAGE RECALL@4")
for label, _, _ in MODES:
    print(f"{label:16} {mean(scores[label]):.3f}")
