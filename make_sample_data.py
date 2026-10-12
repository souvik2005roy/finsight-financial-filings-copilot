"""Creates FICTIONAL sample data (4 made-up companies) so the repo runs out of the box.
Replace data/financials.csv and data/docs/ with real PUBLIC filings for your own results.
Run:  python make_sample_data.py
"""
import json, os
import pandas as pd

# company, sector, revenue FY22..FY25, operating profit, net profit, debt, employees(FY25), risk phrase, outlook
C = {
 "Northwind Foods":  ("FMCG",   [310.0, 340.5, 377.0, 412.5], [41.0, 46.2, 52.9, 60.1], [27.5, 31.0, 36.2, 41.8], [120, 110, 98, 90],  3200,
                      "dependence on a single edible-oil supplier", "open 40 new distribution centres"),
 "Orbit Tech":       ("IT",     [820.0, 960.0, 1105.0, 1190.0], [150.0, 182.0, 210.5, 221.0], [118.0, 140.0, 161.0, 170.5], [0, 0, 15, 20], 9100,
                      "attrition among senior engineers above 18 percent", "hire 1200 engineers in tier-2 cities"),
 "Helio Motors":     ("Auto",   [1500.0, 1710.0, 1880.0, 2040.0], [118.0, 137.0, 160.0, 171.0], [60.0, 74.0, 90.5, 98.0], [400, 420, 380, 350], 12400,
                      "single-source supply of battery cells", "launch three electric models by FY27"),
 "Cedar Pharma":     ("Pharma", [540.0, 585.0, 640.0, 702.0], [95.0, 99.5, 118.0, 131.0], [70.0, 71.0, 86.5, 97.2], [210, 190, 175, 160], 5600,
                      "regulatory delay in USFDA approvals", "file 12 new abbreviated drug applications"),
}
RISK_KEY = {"Northwind Foods": "edible-oil", "Orbit Tech": "attrition", "Helio Motors": "battery", "Cedar Pharma": "USFDA"}
OUT_KEY = {"Northwind Foods": "40", "Orbit Tech": "1200", "Helio Motors": "three", "Cedar Pharma": "12"}
rows = []
for name, (sec, rev, op, np_, debt, emp, risk, outlook) in C.items():
    for i, fy in enumerate([2022, 2023, 2024, 2025]):
        rows.append([name, sec, fy, rev[i], op[i], np_[i], debt[i], emp])
df = pd.DataFrame(rows, columns=["company", "sector", "fiscal_year", "revenue_cr",
                                 "operating_profit_cr", "net_profit_cr", "total_debt_cr", "employees"])
os.makedirs("data/docs", exist_ok=True)
df.to_csv("data/financials.csv", index=False)

questions = []
for name, (sec, rev, op, np_, debt, emp, risk, outlook) in C.items():
    growth = (rev[3] / rev[2] - 1) * 100
    slug = name.lower().replace(" ", "_")
    open(f"data/docs/{slug}_annual_report.txt", "w").write(f"""{name} - Annual Report FY25 (FICTIONAL, for demo only)

Overview. {name} operates in the {sec} sector and employs about {emp} people.

Management discussion. Revenue grew {growth:.1f} percent to {rev[3]} crore in FY25 from {rev[2]} crore in FY24.
Operating profit was {op[3]} crore and net profit was {np_[3]} crore. Total debt stood at {debt[3]} crore.

Risk factors. The most significant risk to the business is {risk}. Management has started a mitigation programme
but the risk is expected to remain material through FY26. Other risks include currency movements and input-cost inflation.

Outlook. In FY26 the company plans to {outlook}. The board expects margins to remain stable.
""")
    questions += [
      {"type": "sql", "q": f"What was the revenue of {name} in FY25?", "expect": [f"{rev[3]}"]},
      {"type": "sql", "q": f"What was the operating margin of {name} in FY25 in percent?", "expect": [f"{op[3]/rev[3]*100:.1f}"]},
      {"type": "rag", "q": f"What is the biggest risk {name} reports?", "expect": [RISK_KEY[name]], "source": f"{slug}_annual_report.txt"},
      {"type": "rag", "q": f"What does {name} plan to do in FY26?", "expect": [OUT_KEY[name]], "source": f"{slug}_annual_report.txt"},
    ]
best = max(C, key=lambda n: C[n][3][3])
lowest_debt = min(C, key=lambda n: C[n][4][2])
questions += [
  {"type": "sql", "q": "Which company had the highest net profit in FY25?", "expect": [best]},
  {"type": "sql", "q": "Which company had the lowest total debt in FY24?", "expect": [lowest_debt]},
  {"type": "sql", "q": "What was the combined revenue of all companies in FY25?", "expect": [f"{sum(v[1][3] for v in C.values()):.1f}"]},
  {"type": "sql", "q": "How many employees did Orbit Tech have?", "expect": ["9100"]},
]
json.dump(questions, open("data/eval_questions.json", "w"), indent=1)
print(len(df), "financial rows,", len(C), "documents,", len(questions), "eval questions")
