import logging

from fastapi import FastAPI
from sqlalchemy import text

from .db import SessionLocal
from .routers import auth, billing
from .settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="CCL Platform API", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.include_router(auth.router)
app.include_router(billing.router)


@app.get("/api/health")
def health():
    s = get_settings()
    with SessionLocal() as db:
        db.execute(text("select 1"))
    return {"ok": True, "environment": s.environment, "stt": s.resolved_stt, "evaluator": s.resolved_evaluator}
