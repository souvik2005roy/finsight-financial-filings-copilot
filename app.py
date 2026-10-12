"""Command-line chat:  python app.py"""
from pipeline import FinSight

if __name__ == "__main__":
    bot = FinSight()
    print("FinSight ready. Ask about the companies (or type 'quit').")
    while (q := input("\n> ").strip()) and q.lower() != "quit":
        out = bot.ask(q)
        print(out["answer"])
        print(f"[route={out['route']}] sources={out['sources']}" + (f"\n[SQL] {out['sql']}" if out["sql"] else ""))
