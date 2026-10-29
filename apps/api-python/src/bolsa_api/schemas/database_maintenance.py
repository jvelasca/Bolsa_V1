"""DTOs HTTP del diagnóstico de mantenimiento de PostgreSQL (solo lectura)."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CheckStatusDto = Literal["ok", "warning", "error", "unknown"]


class MaintenanceCheckDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    id: str
    label: str
    status: CheckStatusDto
    detail: str
    value: str | None = None


class SchemaStatusDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    status: CheckStatusDto
    current_revision: str | None = Field(default=None, alias="currentRevision")
    expected_head: str | None = Field(default=None, alias="expectedHead")
    database_tables: int = Field(alias="databaseTables")
    expected_tables: int = Field(alias="expectedTables")
    missing_tables: list[str] = Field(default_factory=list, alias="missingTables")
    missing_columns: list[str] = Field(default_factory=list, alias="missingColumns")
    missing_constraints: list[str] = Field(default_factory=list, alias="missingConstraints")
    unexpected_tables: list[str] = Field(default_factory=list, alias="unexpectedTables")
    allowlisted: list[str] = Field(default_factory=list)
    detail: str


class CapacityTableDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    table: str
    label: str
    rows: int
    size_bytes: int = Field(alias="sizeBytes")
    size_pretty: str = Field(alias="sizePretty")


class CapacityStatusDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    status: CheckStatusDto
    database_bytes: int = Field(alias="databaseBytes")
    database_pretty: str = Field(alias="databasePretty")
    tables: list[CapacityTableDto] = Field(default_factory=list)
    detail: str


class MaintenanceTableDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    table: str
    live_tuples: int = Field(alias="liveTuples")
    dead_tuples: int = Field(alias="deadTuples")
    last_autovacuum: str | None = Field(default=None, alias="lastAutovacuum")
    last_autoanalyze: str | None = Field(default=None, alias="lastAutoanalyze")


class MaintenanceStatusDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    status: CheckStatusDto
    autovacuum_enabled: bool | None = Field(default=None, alias="autovacuumEnabled")
    naptime_seconds: int | None = Field(default=None, alias="naptimeSeconds")
    dead_tuples_total: int = Field(alias="deadTuplesTotal")
    tables_with_dead_tuples: list[MaintenanceTableDto] = Field(
        default_factory=list, alias="tablesWithDeadTuples"
    )
    last_autovacuum: str | None = Field(default=None, alias="lastAutovacuum")
    detail: str


class ConnectionsStatusDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    status: CheckStatusDto
    total: int
    active: int
    idle: int
    idle_in_transaction: int = Field(alias="idleInTransaction")
    max_connections: int | None = Field(default=None, alias="maxConnections")
    longest_transaction_seconds: float | None = Field(
        default=None, alias="longestTransactionSeconds"
    )
    detail: str


class BackupsStatusDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    status: CheckStatusDto
    accessible: bool
    directory: str
    count: int
    retention: int
    latest_name: str | None = Field(default=None, alias="latestName")
    latest_bytes: int | None = Field(default=None, alias="latestBytes")
    latest_created_at: str | None = Field(default=None, alias="latestCreatedAt")
    latest_schema: str | None = Field(default=None, alias="latestSchema")
    age_hours: float | None = Field(default=None, alias="ageHours")
    stale: bool | None = None
    checksum_present: bool = Field(alias="checksumPresent")
    mirror_configured: bool = Field(alias="mirrorConfigured")
    detail: str


class IntegrityStatusDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    status: CheckStatusDto
    checks: list[MaintenanceCheckDto] = Field(default_factory=list)
    detail: str


class DatabaseMaintenanceDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    status: CheckStatusDto
    generated_at: str = Field(alias="generatedAt")
    connected: bool
    message: str
    # ``schema`` sombrea el método histórico de BaseModel; el alias mantiene el contrato.
    schema_status: SchemaStatusDto = Field(alias="schema")
    capacity: CapacityStatusDto
    maintenance: MaintenanceStatusDto
    connections: ConnectionsStatusDto
    backups: BackupsStatusDto
    integrity: IntegrityStatusDto
    checks: list[MaintenanceCheckDto] = Field(default_factory=list)


class DatabaseMaintenanceResponseDto(BaseModel):
    data: DatabaseMaintenanceDto


class CreateDatabaseBackupRequestDto(BaseModel):
    """Confirmación escrita obligatoria: el cuerpo debe traer exactamente ``COPIAR``."""

    confirm: str


class BackupRunDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    ok: bool
    file: str | None = None
    bytes: int | None = None
    sha256: str | None = None
    schema_revision: str | None = Field(default=None, alias="schemaRevision")
    pruned: int = 0
    mirror_path: str | None = Field(default=None, alias="mirrorPath")
    duration_ms: int = Field(default=0, alias="durationMs")
    error_code: str | None = Field(default=None, alias="errorCode")
    error: str | None = None


class CreateDatabaseBackupResultDto(BaseModel):
    """El intento y el estado real de las copias después (recalculado, no cacheado)."""

    model_config = ConfigDict(populate_by_name=True, ser_json_by_alias=True)  # type: ignore[typeddict-unknown-key]

    run: BackupRunDto
    backups: BackupsStatusDto | None = None


class CreateDatabaseBackupResponseDto(BaseModel):
    data: CreateDatabaseBackupResultDto
