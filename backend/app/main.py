from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import build_router
from app.auth.http import HttpAuthMiddleware, HttpAuthSettings, validate_http_auth_configuration
from app.bootstrap import build_company_os
from app.core.models import Task
from app.persistence.factory import create_state_store
from app.services.company import CompanyApplicationService


def create_app(
    sqlite_path: str | None = None,
    database_url: str | None = None,
    auth_settings: HttpAuthSettings | None = None,
) -> FastAPI:
    persistence = create_state_store(sqlite_path=sqlite_path, database_url=database_url)
    company_os = build_company_os()
    service = CompanyApplicationService(company_os=company_os, persistence=persistence)
    active_auth_settings = auth_settings or HttpAuthSettings.from_env()
    validate_http_auth_configuration(service, active_auth_settings)
    fastapi_app = FastAPI(title="AI Company OS", version="0.1.0")
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    fastapi_app.add_middleware(
        HttpAuthMiddleware,
        service=service,
        settings=active_auth_settings,
    )
    fastapi_app.include_router(build_router(service))
    return fastapi_app


company_os = build_company_os()
service = CompanyApplicationService(company_os=company_os)
app = create_app()


def run_document_task(title: str, description: str) -> Task:
    task = Task(title=title, description=description)
    company_os.document_workflow.run(task)
    return task


if __name__ == "__main__":
    demo_task = run_document_task("AI Company OS first document", "Create the first internal operating note.")
    print(demo_task.status.value)
