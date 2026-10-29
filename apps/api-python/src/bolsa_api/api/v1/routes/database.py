"""API: estado BD y purgas administrativas."""

from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_api.api.dependencies import (
    get_create_database_backup_use_case,
    get_database_maintenance_use_case,
    get_database_summary_use_case,
    get_db_session,
    get_list_closed_simulated_accounts_use_case,
    get_list_orphan_instruments_use_case,
    get_purge_closed_simulated_accounts_use_case,
    get_purge_orphan_instruments_use_case,
)
from bolsa_api.auth.request_principal import get_request_principal
from bolsa_api.auth.roles import require_admin_when_auth_enabled
from bolsa_api.schemas.account_lifecycle import (
    ClosedSimulatedAccountDto,
    ClosedSimulatedAccountsDto,
    ClosedSimulatedAccountsResponseDto,
    PurgeClosedAccountSkippedDto,
    PurgeClosedAccountsRequestDto,
    PurgeClosedAccountsResponseDto,
    PurgeClosedAccountsResultDto,
)
from bolsa_api.schemas.database import (
    DatabaseSummaryDto,
    DatabaseSummaryResponseDto,
    DatabaseTableCountDto,
    InstrumentOhlcvBreakdownDto,
)
from bolsa_api.schemas.database_maintenance import (
    BackupRunDto,
    BackupsStatusDto,
    CapacityStatusDto,
    CapacityTableDto,
    ConnectionsStatusDto,
    CreateDatabaseBackupRequestDto,
    CreateDatabaseBackupResponseDto,
    CreateDatabaseBackupResultDto,
    DatabaseMaintenanceDto,
    DatabaseMaintenanceResponseDto,
    IntegrityStatusDto,
    MaintenanceCheckDto,
    MaintenanceStatusDto,
    MaintenanceTableDto,
    SchemaStatusDto,
)
from bolsa_api.schemas.instrument_lifecycle import (
    OrphanInstrumentsResponseDto,
    PurgeOrphansRequestDto,
    PurgeOrphansResponseDto,
)
from bolsa_api.schemas.lifecycle_mappers import to_orphans_dto, to_purge_orphans_result_dto
from bolsa_application.account_lifecycle import ListClosedSimulatedAccountsResult
from bolsa_application.database_backup import BackupRunResult, CreateDatabaseBackup
from bolsa_application.database_maintenance import (
    BackupReport,
    CheckResult,
    DatabaseMaintenanceReport,
)
from bolsa_application.get_database_summary import DatabaseSummary

router = APIRouter()


def _to_dto(summary: DatabaseSummary) -> DatabaseSummaryDto:
    return DatabaseSummaryDto(
        connected=summary.connected,
        message=summary.message,
        tables=[
            DatabaseTableCountDto(table=t.table, label=t.label, count=t.count)
            for t in summary.tables
        ],
        instrument_ohlcv=[
            InstrumentOhlcvBreakdownDto(timeframe=i.timeframe, bar_count=i.bar_count)
            for i in summary.instrument_ohlcv
        ],
    )


@router.get("/database/summary", response_model=DatabaseSummaryResponseDto)
async def get_database_summary(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    instrument_id: Annotated[str | None, Query(alias="instrumentId")] = None,
) -> DatabaseSummaryResponseDto:
    summary = await get_database_summary_use_case(session).execute(instrument_id)
    return DatabaseSummaryResponseDto(data=_to_dto(summary))


def _to_check_dto(check: CheckResult) -> MaintenanceCheckDto:
    return MaintenanceCheckDto(
        id=check.id,
        label=check.label,
        status=check.status,
        detail=check.detail,
        value=check.value,
    )


def _ts(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _to_maintenance_dto(report: DatabaseMaintenanceReport) -> DatabaseMaintenanceDto:
    return DatabaseMaintenanceDto(
        status=report.status,
        generated_at=report.generated_at.isoformat(),
        connected=report.connected,
        message=report.message,
        schema_status=SchemaStatusDto(
            status=report.schema.status,
            current_revision=report.schema.current_revision,
            expected_head=report.schema.expected_head,
            database_tables=report.schema.database_tables,
            expected_tables=report.schema.expected_tables,
            missing_tables=list(report.schema.missing_tables),
            missing_columns=list(report.schema.missing_columns),
            missing_constraints=list(report.schema.missing_constraints),
            unexpected_tables=list(report.schema.unexpected_tables),
            allowlisted=list(report.schema.allowlisted),
            detail=report.schema.detail,
        ),
        capacity=CapacityStatusDto(
            status=report.capacity.status,
            database_bytes=report.capacity.database_bytes,
            database_pretty=report.capacity.database_pretty,
            tables=[
                CapacityTableDto(
                    table=item.table,
                    label=item.label,
                    rows=item.rows,
                    size_bytes=item.size_bytes,
                    size_pretty=item.size_pretty,
                )
                for item in report.capacity.tables
            ],
            detail=report.capacity.detail,
        ),
        maintenance=MaintenanceStatusDto(
            status=report.maintenance.status,
            autovacuum_enabled=report.maintenance.autovacuum_enabled,
            naptime_seconds=report.maintenance.naptime_seconds,
            dead_tuples_total=report.maintenance.dead_tuples_total,
            tables_with_dead_tuples=[
                MaintenanceTableDto(
                    table=item.table,
                    live_tuples=item.live_tuples,
                    dead_tuples=item.dead_tuples,
                    last_autovacuum=_ts(item.last_autovacuum),
                    last_autoanalyze=_ts(item.last_autoanalyze),
                )
                for item in report.maintenance.tables_with_dead_tuples
            ],
            last_autovacuum=_ts(report.maintenance.last_autovacuum),
            detail=report.maintenance.detail,
        ),
        connections=ConnectionsStatusDto(
            status=report.connections.status,
            total=report.connections.total,
            active=report.connections.active,
            idle=report.connections.idle,
            idle_in_transaction=report.connections.idle_in_transaction,
            max_connections=report.connections.max_connections,
            longest_transaction_seconds=report.connections.longest_transaction_seconds,
            detail=report.connections.detail,
        ),
        backups=_to_backups_dto(report.backups),
        integrity=IntegrityStatusDto(
            status=report.integrity.status,
            checks=[_to_check_dto(check) for check in report.integrity.checks],
            detail=report.integrity.detail,
        ),
        checks=[_to_check_dto(check) for check in report.checks],
    )


def _to_backups_dto(backups: BackupReport) -> BackupsStatusDto:
    """Un solo mapeo para el diagnóstico y para la respuesta de la copia bajo demanda."""
    return BackupsStatusDto(
        status=backups.status,
        accessible=backups.accessible,
        directory=backups.directory,
        count=backups.count,
        retention=backups.retention,
        latest_name=backups.latest_name,
        latest_bytes=backups.latest_bytes,
        latest_created_at=_ts(backups.latest_created_at),
        latest_schema=backups.latest_schema,
        age_hours=backups.age_hours,
        stale=backups.stale,
        checksum_present=backups.checksum_present,
        mirror_configured=backups.mirror_configured,
        detail=backups.detail,
    )


@router.get("/database/maintenance", response_model=DatabaseMaintenanceResponseDto)
async def get_database_maintenance(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DatabaseMaintenanceResponseDto:
    """Diagnóstico read-only: esquema/head, capacidad, mantenimiento, conexiones y copias.

    Devuelve 200 incluso con la BD caída (``connected=false`` y checks con error), igual
    que ``/database/summary``: el panel debe poder explicar el fallo, no reventar. No hay
    ninguna acción de escritura: ni VACUUM, ni ANALYZE, ni purgas, ni migraciones.
    """
    report = await get_database_maintenance_use_case(session).execute()
    return DatabaseMaintenanceResponseDto(data=_to_maintenance_dto(report))


#: Palabra que el usuario debe escribir para confirmar la copia (no un simple clic).
BACKUP_CONFIRMATION = "COPIAR"

#: Fallos de entorno: la acción no pudo ni empezar (503), no es un volcado fallido (500).
_BACKUP_ENV_ERRORS = frozenset({"NODE_MISSING", "SCRIPT_MISSING", "DIR_ERROR"})


def _to_backup_run_dto(run: BackupRunResult) -> BackupRunDto:
    return BackupRunDto(
        ok=run.ok,
        file=run.file,
        bytes=run.bytes,
        sha256=run.sha256,
        schema_revision=run.schema,
        pruned=run.pruned,
        mirror_path=run.mirror_path,
        duration_ms=run.duration_ms,
        error_code=run.error_code,
        error=run.error,
    )


@router.post("/database/backup", response_model=CreateDatabaseBackupResponseDto)
async def create_database_backup(
    body: CreateDatabaseBackupRequestDto,
    request: Request,
    use_case: Annotated[CreateDatabaseBackup, Depends(get_create_database_backup_use_case)],
) -> CreateDatabaseBackupResponseDto:
    """Crea una copia local de la BD (única acción de mantenimiento de la ventana BD).

    ``pg_dump`` solo lee la BD; lo que sí escribe es un fichero con su sidecar ``.sha256``,
    el manifest y la poda por retención. Por eso no basta un clic: hay confirmación
    escrita, rol ``admin`` cuando la auth está activa, un cerrojo que impide dos copias
    simultáneas (409) y auditoría. Si la copia no se creó, la respuesta **no** es 200.
    """
    require_admin_when_auth_enabled(request)
    if body.confirm.strip().upper() != BACKUP_CONFIRMATION:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "confirmation_required",
                "message": f'Escribe "{BACKUP_CONFIRMATION}" para confirmar la copia',
            },
        )

    report = await use_case.execute(actor=get_request_principal(request))
    if report.refused:
        raise HTTPException(
            status_code=403,
            detail={
                "code": report.reason or "forbidden",
                "message": report.run.error or "La copia no está permitida en este entorno",
            },
        )
    if report.busy:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "backup_in_progress",
                "message": report.run.error or "Ya hay una copia en curso",
            },
        )
    if not report.run.ok:
        code = report.run.error_code or "DUMP_FAILED"
        raise HTTPException(
            status_code=503 if code in _BACKUP_ENV_ERRORS else 500,
            detail={"code": code, "message": report.run.error or "La copia no se creó"},
        )

    return CreateDatabaseBackupResponseDto(
        data=CreateDatabaseBackupResultDto(
            run=_to_backup_run_dto(report.run),
            backups=_to_backups_dto(report.backups) if report.backups is not None else None,
        )
    )


@router.get("/database/orphans", response_model=OrphanInstrumentsResponseDto)
async def list_orphan_instruments(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> OrphanInstrumentsResponseDto:
    result = await get_list_orphan_instruments_use_case(session).execute(limit=limit)
    return OrphanInstrumentsResponseDto(data=to_orphans_dto(result))


@router.post("/database/orphans/purge", response_model=PurgeOrphansResponseDto)
async def purge_orphan_instruments(
    body: PurgeOrphansRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PurgeOrphansResponseDto:
    raw = await get_purge_orphan_instruments_use_case(session).execute(limit=body.limit)
    return PurgeOrphansResponseDto(data=to_purge_orphans_result_dto(raw))


def _to_closed_accounts_dto(
    result: ListClosedSimulatedAccountsResult,
) -> ClosedSimulatedAccountsDto:
    return ClosedSimulatedAccountsDto(
        accounts=[
            ClosedSimulatedAccountDto(
                id=a.id,
                name=a.name,
                currency=a.currency,
                updated_at=a.updated_at.isoformat(),
                ledger_entry_count=a.ledger_entry_count,
                portfolio_count=a.portfolio_count,
                position_count=a.position_count,
                transaction_count=a.transaction_count,
                pending_order_count=a.pending_order_count,
            )
            for a in result.accounts
        ],
        total_ledger_entries=result.total_ledger_entries,
    )


@router.get("/database/closed-accounts", response_model=ClosedSimulatedAccountsResponseDto)
async def list_closed_simulated_accounts(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> ClosedSimulatedAccountsResponseDto:
    result = await get_list_closed_simulated_accounts_use_case(session).execute(limit=limit)
    return ClosedSimulatedAccountsResponseDto(data=_to_closed_accounts_dto(result))


@router.post("/database/closed-accounts/purge", response_model=PurgeClosedAccountsResponseDto)
async def purge_closed_simulated_accounts(
    body: PurgeClosedAccountsRequestDto,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PurgeClosedAccountsResponseDto:
    raw = await get_purge_closed_simulated_accounts_use_case(session).execute(limit=body.limit)
    skipped_raw = cast(list[object], raw.get("skipped") or [])
    skipped = [
        PurgeClosedAccountSkippedDto(
            account_id=str(item["accountId"]),
            name=str(item["name"]),
            reasons=list(item.get("reasons") or []),
        )
        for item in skipped_raw
        if isinstance(item, dict)
    ]
    return PurgeClosedAccountsResponseDto(
        data=PurgeClosedAccountsResultDto(
            purged_ids=list(cast(list[str], raw.get("purgedIds") or [])),
            skipped=skipped,
            scanned=int(cast(int, raw.get("scanned") or 0)),
        )
    )
