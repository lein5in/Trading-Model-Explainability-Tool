from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.client import get_supabase_client
from app.api.routes_models import router as models_router
from app.api.routes_analysis import router as analysis_router
from app.auth.routes import router as auth_router

app = FastAPI(title="Trading Explainability Tool")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(models_router)
app.include_router(analysis_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db():
    client = get_supabase_client()
    return {"status": "connected", "supabase_url_configured": client.supabase_url is not None}