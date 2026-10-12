"""Measure your system. Two modes:

  python evaluate.py --retrieval-only    # no LLM needed: compares vector vs bm25 vs hybrid search
  python evaluate.py                     # full run (needs LLM_API_KEY): routing, SQL, RAG, number-checker
"""
import argparse, json
from checker import numbers_in

def is_correct(answer, expected):
    """Number expected -> some number in the answer matches (1% tolerance). Text -> substring."""
    nums = numbers_in(answer.replace(",", ""))
    for e in expected:
        try:
            v = float(e)
            if not any(abs(n - v) <= max(0.06, 0.01 * abs(v)) for n in nums):
                return False
        except ValueError:
            if e.lower() not in answer.lower():
                return False
    return True

def retrieval_eval(questions, retriever, k=4):
    rag = [q for q in questions if q["type"] == "rag"]
    print(f"Retrieval hit@{k} on {len(rag)} document questions (right file in top-{k} chunks)")
    for mode in ("vector", "bm25", "hybrid"):
        hits = sum(q["source"] in {retriever.sources[i] for i in retriever.search(q["q"], k, mode)} for q in rag)
        print(f"  {mode:7s} {hits}/{len(rag)} = {hits/len(rag):.0%}")

def full_eval(questions, bot, mode):
    stats = {"sql": [0, 0], "rag": [0, 0]}
    route_ok = flagged_wrong = wrong = 0
    for q in questions:
        out = bot.ask(q["q"], mode)
        ok = is_correct(out["answer"].split("[WARNING]")[0], q["expect"])
        stats[q["type"]][0] += ok
        stats[q["type"]][1] += 1
        route_ok += out["route"] == ("sql" if q["type"] == "sql" else "docs")
        if not ok:
            wrong += 1
            flagged_wrong += bool(out["unverified"])
            print("  WRONG:", q["q"], "->", out["answer"][:120].replace("\n", " "))
    print(f"\nRouting accuracy : {route_ok}/{len(questions)}")
    for t, (a, b) in stats.items():
        print(f"{t.upper():4s} accuracy    : {a}/{b} = {a/b:.0%}")
    if wrong:
        print(f"Wrong answers caught by the number-checker: {flagged_wrong}/{wrong}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--retrieval-only", action="store_true")
    ap.add_argument("--mode", default="hybrid", choices=["vector", "bm25", "hybrid"])
    args = ap.parse_args()
    questions = json.load(open("data/eval_questions.json"))
    if args.retrieval_only:
        from rag import Retriever
        retrieval_eval(questions, Retriever())
    else:
        from pipeline import FinSight
        full_eval(questions, FinSight(), args.mode)
