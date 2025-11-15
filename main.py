# main.py
from fastapi import FastAPI
from pydantic import BaseModel
from agent import get_agent_response

app = FastAPI(title="Financial Agent API")

class QueryInput(BaseModel):
    question: str

class QueryOutput(BaseModel):
    answer: str

@app.post("/ask", response_model=QueryOutput)
async def ask_agent(query: QueryInput):
    print(f"[API] Nhận: {query.question}")
    answer = get_agent_response(query.question)
    print(f"[API] Trả: {answer[:100]}...")
    return QueryOutput(answer=answer)

@app.get("/")
def root():
    return {"message": "API đang chạy. POST /ask"}