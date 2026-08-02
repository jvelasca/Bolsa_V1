"""Punto de entrada FastAPI — Bolsa V1 API.

Arranque:
    uvicorn bolsa_api.main:app --reload --port 8000
    # o: python -m bolsa_api.main

Responsabilidades:
    - Lifespan: engine SQLAlchemy, session factory, evaluators de alertas (precio + estrategia).
    - Middleware: CORS + auth opcional (APP_PASSWORD).
    - Router v1 bajo prefijo /api.

Ver docs/API_REFERENCE.md y docs/ONBOARDING.md.
"""
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from bolsa_api.ai_bootstrap import configure_ai_governance_proxy, teardown_ai_governance_proxy
from bolsa_api.api.v1.router import api_v1_router
from bolsa_api.background.auto_sync_worker import start_auto_sync_worker
from bolsa_api.background.core_r_cron_worker import start_core_r_cron_worker
from bolsa_api.background.daily_alert_evaluator import start_daily_alert_evaluator
from bolsa_api.background.fa_weekly_worker import start_fa_weekly_worker
from bolsa_api.background.index_subscribe_worker import start_index_subscribe_worker
from bolsa_api.background.optimization_worker import start_optimization_worker
from bolsa_api.background.scan_worker import start_scan_worker
from bolsa_api.background.signal_alert_evaluator import start_signal_alert_evaluator
from bolsa_api.background.tracker_schedule_worker import start_tracker_schedule_worker
from bolsa_api.logging_redact import install_log_redact
from bolsa_api.middleware.auth import AuthMiddleware
from bolsa_api.middleware.rate_limit import RateLimitMiddleware
from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.llm_call_audit import dispose_llm_call_audit_engine
from bolsa_infrastructure.database.session import (
    create_engine,
    create_session_factory,
)
from bolsa_infrastructure.queue.scan_job_arq import close_scan_job_arq_pool


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    engine = create_engine(settings)
    app.state.engine = engine
    app.state.session_factory = create_session_factory(engine)
    configure_ai_governance_proxy()
    _warn_if_routes_missing(app)
    settings = get_settings()
    evaluator_task = start_daily_alert_evaluator(app.state.session_factory)
    signal_alert_task = start_signal_alert_evaluator(app.state.session_factory)
    tracker_schedule_task = start_tracker_schedule_worker(app.state.session_factory)
    fa_weekly_task = start_fa_weekly_worker(app.state.session_factory)
    core_r_cron_task = start_core_r_cron_worker(app.state.session_factory)
    auto_sync_task = start_auto_sync_worker(app.state.session_factory)
    index_subscribe_task = start_index_subscribe_worker(app.state.session_factory)
    scan_worker_task: asyncio.Task[None] | None = None
    optimization_worker_task: asyncio.Task[None] | None = None
    if settings.scan_queue_backend.lower() != "arq":
        scan_worker_task = start_scan_worker(app.state.session_factory)
        optimization_worker_task = start_optimization_worker(app.state.session_factory)
    else:
        import logging

        logging.getLogger("uvicorn.error").info(
            "SCAN_QUEUE_BACKEND=arq — workers inline desactivados; ejecuta bolsa-arq-worker",
        )
    try:
        yield
    finally:
        if scan_worker_task is not None:
            scan_worker_task.cancel()
        if optimization_worker_task is not None:
            optimization_worker_task.cancel()
        index_subscribe_task.cancel()
        auto_sync_task.cancel()
        signal_alert_task.cancel()
        if tracker_schedule_task is not None:
            tracker_schedule_task.cancel()
        if fa_weekly_task is not None:
            fa_weekly_task.cancel()
        if core_r_cron_task is not None:
            core_r_cron_task.cancel()
        evaluator_task.cancel()
        tasks = [index_subscribe_task, auto_sync_task, signal_alert_task, evaluator_task]
        if tracker_schedule_task is not None:
            tasks.append(tracker_schedule_task)
        if fa_weekly_task is not None:
            tasks.append(fa_weekly_task)
        if core_r_cron_task is not None:
            tasks.append(core_r_cron_task)
        if scan_worker_task is not None:
            tasks.insert(0, scan_worker_task)
        if optimization_worker_task is not None:
            tasks.insert(0, optimization_worker_task)
        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        if settings.scan_queue_backend.lower() == "arq":
            await close_scan_job_arq_pool()
        dispose_llm_call_audit_engine()
        teardown_ai_governance_proxy()
    await engine.dispose()


def _route_path_exists(app: FastAPI, full_path: str) -> bool:
    """True if a route is mounted — without building the OpenAPI schema (~0.5s+)."""
    from fastapi.routing import APIRoute

    def walk(routes: list, prefix: str = "") -> bool:
        for route in routes:
            if isinstance(route, APIRoute):
                if f"{prefix}{route.path}" == full_path:
                    return True
                continue
            ctx = getattr(route, "include_context", None)
            if ctx is not None:
                nested_prefix = f"{prefix}{ctx.prefix or ''}"
                if walk(list(ctx.included_router.routes), nested_prefix):
                    return True
                continue
            nested = getattr(route, "routes", None)
            if nested is not None:
                path = getattr(route, "path", "") or ""
                if walk(list(nested), f"{prefix}{path}"):
                    return True
        return False

    return walk(list(app.routes))


def _warn_if_routes_missing(app: FastAPI) -> None:
    if not _route_path_exists(app, "/api/alerts"):
        import logging

        logging.getLogger("uvicorn.error").warning(
            "Rutas /api/alerts no registradas — reinicia la API "
            "(detén depuraciones duplicadas en :8000)",
        )


def _cors_origins(settings) -> list[str]:
    raw = settings.cors_origin.strip()
    if not raw:
        return []
    return [part.strip() for part in raw.split(",") if part.strip()]


def _cors_origin_regex(settings) -> str | None:
    if settings.environment != "development":
        return None
    # LAN dev: http://192.168.x.x:5173, http://10.x.x.x:5173, etc.
    return r"https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?"


def create_app() -> FastAPI:
    settings = get_settings()
    install_log_redact()

    app = FastAPI(
        title="Bolsa V1 API",
        version="0.2.0",
        description="Backend Python — análisis bursátil e IA",
        lifespan=lifespan,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # Last added = outermost. Rate limit before auth so 429 does not require token dance.
    app.add_middleware(AuthMiddleware)
    app.add_middleware(RateLimitMiddleware, enabled=settings.environment != "test")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(settings),
        allow_origin_regex=_cors_origin_regex(settings),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_v1_router, prefix="/api")

    return app


app = create_app()


def run() -> None:
    import os
    import sys

    import uvicorn

    settings = get_settings()
    reload_raw = os.environ.get("BOLSA_API_RELOAD", "0").strip().lower()
    reload = reload_raw in {"1", "true", "yes", "on"}
    loop = (
        "bolsa_api.win_loop:selector_event_loop_factory"
        if sys.platform == "win32"
        else "auto"
    )
    uvicorn.run(
        "bolsa_api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        loop=loop,
        reload=reload,
    )


if __name__ == "__main__":
    run()
