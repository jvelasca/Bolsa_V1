from datetime import UTC, datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from bolsa_infrastructure.database.session import check_database

router = APIRouter()


class DatabaseHealthDto(BaseModel):
    status: str
    message: str


class HealthResponseDto(BaseModel):
    status: str
    service: str = "bolsa-api-python"
    timestamp: str
    database: DatabaseHealthDto | None = None
    stack: str = Field(default="python-fastapi")


@router.get("/health", response_model=HealthResponseDto)
async def health_check(request: Request) -> HealthResponseDto:
    engine = request.app.state.engine
    db_ok, db_message = await check_database(engine)

    return HealthResponseDto(
        status="ok" if db_ok else "degraded",
        timestamp=datetime.now(tz=UTC).isoformat(),
        database=DatabaseHealthDto(
            status="ok" if db_ok else "error",
            message=db_message,
        ),
    )
