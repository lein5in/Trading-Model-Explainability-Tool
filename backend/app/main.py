from fastapi import FastAPI

app = FastAPI(title = "Trading Explainability Tool")


@app.get("/health")
def health():
    return {"status": "ok"} 