from datetime import UTC, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from bolsa_infrastructure.config import get_settings
from bolsa_infrastructure.database.session import check_database

router = APIRouter()


class DatabaseHealthDto(BaseModel):
    status: str
    message: str


class ComponentHealthDto(BaseModel):
    status: str
    message: str


class HealthResponseDto(BaseModel):
    status: str
    service: str = "bolsa-api-python"
    timestamp: str
    database: DatabaseHealthDto | None = None
    components: dict[str, ComponentHealthDto] = Field(default_factory=dict)
    stack: str = Field(default="python-fastapi")


def _yahoo_component() -> ComponentHealthDto:
    # Best-effort: no network probe on every health hit (avoid rate limit).
    return ComponentHealthDto(
        status="configured",
        message="Yahoo Finance client available (no live probe)",
    )


def _xtb_component() -> ComponentHealthDto:
    settings = get_settings()
    if settings.xtb_bridge_url:
        return ComponentHealthDto(
            status="configured",
            message=f"XTB_BRIDGE_URL set ({settings.xtb_bridge_url})",
        )
    return ComponentHealthDto(
        status="disabled",
        message="XTB_BRIDGE_URL not set",
    )


@router.get("/health", response_model=HealthResponseDto)
async def health_check(request: Request) -> HealthResponseDto:
    engine = request.app.state.engine
    db_ok, db_message = await check_database(engine)
    components = {
        "database": ComponentHealthDto(
            status="ok" if db_ok else "error",
            message=db_message,
        ),
        "yahoo": _yahoo_component(),
        "xtb": _xtb_component(),
    }
    degraded = (not db_ok) or any(c.status == "error" for c in components.values())
    return HealthResponseDto(
        status="degraded" if degraded else "ok",
        timestamp=datetime.now(tz=UTC).isoformat(),
        database=DatabaseHealthDto(
            status="ok" if db_ok else "error",
            message=db_message,
        ),
        components=components,
    )
