"""REST API:  uvicorn api:app --port 8000   then open http://localhost:8000/docs"""
from fastapi import FastAPI
from pydantic import BaseModel
from pipeline import FinSight

app = FastAPI(title="FinSight")
bot = FinSight()

class Question(BaseModel):
    question: str
    mode: str = "hybrid"          # vector | bm25 | hybrid

@app.post("/ask")
def ask(q: Question):
    return bot.ask(q.question, q.mode)
