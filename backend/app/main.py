import logging

from fastapi import FastAPI
from sqlalchemy import text

from .db import SessionLocal
from .middleware import SecurityMiddleware
from .routers import (admin, admin_content, admin_enrolment, admin_imports, admin_students, auth, billing, courses, jobs,
                      media, public, resources, settings, student)
from .settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

_prod = get_settings().is_production
if get_settings().auto_migrate:  # serverless hosts: no separate migrate/seed step
    from .bootstrap import migrate_and_seed
    migrate_and_seed()
# Interactive API docs are for development only.
app = FastAPI(title="CCL Platform API", docs_url=None if _prod else "/api/docs", redoc_url=None,
              openapi_url=None if _prod else "/api/openapi.json")
app.add_middleware(SecurityMiddleware)
app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(admin_imports.router)
app.include_router(admin_content.router)
app.include_router(admin_students.router)
app.include_router(admin_enrolment.router)
app.include_router(student.router)
app.include_router(media.router)
app.include_router(courses.router)
app.include_router(resources.router)
app.include_router(resources.admin)
app.include_router(settings.public)
app.include_router(settings.admin)
app.include_router(jobs.router)


@app.get("/api/health")
def health():
    s = get_settings()
    with SessionLocal() as db:
        db.execute(text("select 1"))
    return {"ok": True, "environment": s.environment, "stt": s.resolved_stt, "evaluator": s.resolved_evaluator}
