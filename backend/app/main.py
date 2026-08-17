from fastapi import FastAPI
from app.db.client import get_supabase_client

app = FastAPI(title="Trading Explainability Tool")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db():
    client = get_supabase_client()
    return {"status": "connected", "supabase_url_configured": client.supabase_url is not None}