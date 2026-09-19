import logging

from fastapi import FastAPI

from .seeding import ensure_seeded
from .routers import admin, auth_routes, media, student
from .settings import get_settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Benchmark CCL Prep API", docs_url="/api/docs", openapi_url="/api/openapi.json")
ensure_seeded()  # creates tables; seeds demo data on first boot (bundled audio only)

app.include_router(auth_routes.router)
app.include_router(student.router)
app.include_router(media.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    s = get_settings()
    return {"ok": True, "stt": s.resolved_stt, "marker": s.resolved_marker}
