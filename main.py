from fastapi import FastAPI
from .router import router as tips_router

app = FastAPI(title="Personalized Tips Agent", version="1.0.0")

app.include_router(tips_router)

@app.get("/health")
def health():
	return {"ok": True}


