"""Diagnóstico de mantenimiento de PostgreSQL (solo lectura).

La pestaña **Configuración → BD** respondía a «¿cuántas filas hay?» y a dos purgas. No
respondía a las preguntas que de verdad importan cuando la BD es el corazón de los datos:

* ¿el esquema ejecutado es el que el código espera (head de Alembic, tablas y columnas)?
* ¿cuánto ocupa y qué tablas crecen?
* ¿está trabajando ``autovacuum`` o hay basura acumulada?
* ¿hay conexiones o transacciones colgadas?
* ¿existe una copia reciente y verificable?
* ¿el estado durable es coherente (fila única de ``sync_settings``, huérfanos, duplicados)?

Este módulo **no escribe nada**: ni ``VACUUM``, ni ``ANALYZE``, ni ``CREATE/DROP``, ni
purgas. Solo lee catálogo y estadísticas, y publica lo que ve. Una métrica que no se
puede leer se declara ``unknown`` con su motivo: **nunca se rellena con un cero** que la
UI pueda confundir con «sano».

Los dos datos que no viven en PostgreSQL se inyectan como puertos, para que la capa de
aplicación no dependa de infraestructura:

* ``SchemaContract`` — qué tablas/columnas/constraints espera el código, y qué
  divergencias históricas están declaradas (allowlist con motivo).
* ``BackupInventory`` — qué copias hay en disco, su edad y su checksum.

Doctrina heredada del área de proveedores: **sin medición no hay verde**.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

__all__ = [
    "BackupReport",
    "BackupSnapshot",
    "CapacityReport",
    "CapacityTable",
    "CheckResult",
    "ConnectionsReport",
    "DatabaseMaintenanceReport",
    "GetDatabaseMaintenance",
    "IntegrityReport",
    "MaintenanceReport",
    "MaintenanceTable",
    "SchemaContract",
    "SchemaContractSnapshot",
    "SchemaExpectedConstraint",
    "SchemaReport",
    "summarize_backup_snapshot",
    "worst_status",
]

CheckStatus = Literal["ok", "warning", "error", "unknown"]

#: Severidad para agregar. ``unknown`` no es un fallo, pero tampoco es un verde: se
#: ordena por encima de ``ok`` para que un panel incompleto no se pinte como sano.
_SEVERITY: Mapping[CheckStatus, int] = {
    "ok": 0,
    "unknown": 1,
    "warning": 2,
    "error": 3,
}


def worst_status(statuses: Iterable[CheckStatus]) -> CheckStatus:
    """Devuelve el estado más severo de la lista (``ok`` si está vacía)."""
    worst: CheckStatus = "ok"
    for status in statuses:
        if _SEVERITY[status] > _SEVERITY[worst]:
            worst = status
    return worst


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Una comprobación legible: qué se miró, qué se vio y con qué severidad."""

    id: str
    label: str
    status: CheckStatus
    detail: str
    value: str | None = None


@dataclass(frozen=True, slots=True)
class SchemaExpectedConstraint:
    """Constraint que el código declara en metadatos y debe existir en la BD."""

    name: str
    table: str
    kind: str


@dataclass(frozen=True, slots=True)
class SchemaContractSnapshot:
    """Fotografía del contrato de esquema (la construye infraestructura)."""

    expected_tables: frozenset[str] = frozenset()
    expected_columns: frozenset[tuple[str, str]] = frozenset()
    expected_constraints: tuple[SchemaExpectedConstraint, ...] = ()
    allowlisted: tuple[str, ...] = ()
    source: str = "metadatos SQLAlchemy"


class SchemaContract(Protocol):
    """Puerto: qué esquema espera el código y qué divergencias están declaradas."""

    def snapshot(self) -> SchemaContractSnapshot: ...


@dataclass(frozen=True, slots=True)
class BackupSnapshot:
    """Fotografía del inventario de copias (la construye infraestructura)."""

    accessible: bool
    directory: str
    count: int = 0
    latest_name: str | None = None
    latest_bytes: int | None = None
    latest_created_at: datetime | None = None
    latest_schema: str | None = None
    checksum_present: bool = False
    mirror_configured: bool = False
    retention: int = 0
    detail: str = ""


class BackupInventory(Protocol):
    """Puerto: estado de las copias de seguridad en el árbol local/espejo."""

    def snapshot(self) -> BackupSnapshot: ...


@dataclass(frozen=True, slots=True)
class SchemaReport:
    status: CheckStatus
    current_revision: str | None
    expected_head: str | None
    database_tables: int
    expected_tables: int
    missing_tables: tuple[str, ...] = ()
    missing_columns: tuple[str, ...] = ()
    missing_constraints: tuple[str, ...] = ()
    unexpected_tables: tuple[str, ...] = ()
    allowlisted: tuple[str, ...] = ()
    detail: str = ""


@dataclass(frozen=True, slots=True)
class CapacityTable:
    table: str
    label: str
    rows: int
    size_bytes: int
    size_pretty: str


@dataclass(frozen=True, slots=True)
class CapacityReport:
    status: CheckStatus
    database_bytes: int
    database_pretty: str
    tables: tuple[CapacityTable, ...] = ()
    detail: str = ""


@dataclass(frozen=True, slots=True)
class MaintenanceTable:
    table: str
    live_tuples: int
    dead_tuples: int
    last_autovacuum: datetime | None = None
    last_autoanalyze: datetime | None = None


@dataclass(frozen=True, slots=True)
class MaintenanceReport:
    status: CheckStatus
    autovacuum_enabled: bool | None
    naptime_seconds: int | None
    dead_tuples_total: int
    tables_with_dead_tuples: tuple[MaintenanceTable, ...] = ()
    last_autovacuum: datetime | None = None
    detail: str = ""


@dataclass(frozen=True, slots=True)
class ConnectionsReport:
    status: CheckStatus
    total: int
    active: int
    idle: int
    idle_in_transaction: int
    max_connections: int | None
    longest_transaction_seconds: float | None
    detail: str = ""


@dataclass(frozen=True, slots=True)
class BackupReport:
    status: CheckStatus
    accessible: bool
    directory: str
    count: int
    retention: int
    latest_name: str | None
    latest_bytes: int | None
    latest_created_at: datetime | None
    latest_schema: str | None
    age_hours: float | None
    stale: bool | None
    checksum_present: bool
    mirror_configured: bool
    detail: str = ""


def summarize_backup_snapshot(
    snapshot: BackupSnapshot,
    *,
    expected_head: str | None,
    stale_hours: float,
    now: datetime,
) -> BackupReport:
    """Traduce un ``BackupSnapshot`` a informe con severidad, edad y hallazgos.

    Vive fuera del caso de uso porque lo comparten dos rutas: el diagnóstico
    (``GET /api/database/maintenance``) y la respuesta de la copia bajo demanda
    (``POST /api/database/backup``). Una sola regla de frescura/checksum/esquema evita
    que el mismo estado se pinte distinto según por dónde se mire.
    """
    if not snapshot.accessible:
        return BackupReport(
            status="warning",
            accessible=False,
            directory=snapshot.directory,
            count=snapshot.count,
            retention=snapshot.retention,
            latest_name=snapshot.latest_name,
            latest_bytes=snapshot.latest_bytes,
            latest_created_at=snapshot.latest_created_at,
            latest_schema=snapshot.latest_schema,
            age_hours=None,
            stale=None,
            checksum_present=snapshot.checksum_present,
            mirror_configured=snapshot.mirror_configured,
            detail=snapshot.detail or "El directorio de copias no es accesible desde la API",
        )

    age_hours = None
    if snapshot.latest_created_at is not None:
        age_hours = max(
            0.0,
            (now - snapshot.latest_created_at.astimezone(UTC)).total_seconds() / 3600.0,
        )
    stale = None if age_hours is None else age_hours > stale_hours

    status: CheckStatus = "ok"
    problems: list[str] = []
    if snapshot.count == 0 or snapshot.latest_name is None:
        status = "error"
        problems.append("no hay ninguna copia en el directorio")
    elif stale:
        status = "warning"
        problems.append(f"la copia más reciente tiene {age_hours:.1f} h")
    if snapshot.latest_name and not snapshot.checksum_present:
        status = worst_status((status, "warning"))
        problems.append("la copia más reciente no tiene sidecar de checksum")
    if snapshot.latest_schema and expected_head and snapshot.latest_schema != expected_head:
        status = worst_status((status, "warning"))
        problems.append(
            f"la copia se tomó en {snapshot.latest_schema}, no en el head {expected_head}"
        )
    if not snapshot.mirror_configured and snapshot.count > 0:
        problems.append("sin espejo off-site configurado")

    if problems:
        detail = "; ".join(problems)
    else:
        detail = f"{snapshot.count} copia(s); la más reciente {age_hours:.1f} h"
    return BackupReport(
        status=status,
        accessible=True,
        directory=snapshot.directory,
        count=snapshot.count,
        retention=snapshot.retention,
        latest_name=snapshot.latest_name,
        latest_bytes=snapshot.latest_bytes,
        latest_created_at=snapshot.latest_created_at,
        latest_schema=snapshot.latest_schema,
        age_hours=age_hours,
        stale=stale,
        checksum_present=snapshot.checksum_present,
        mirror_configured=snapshot.mirror_configured,
        detail=detail,
    )


@dataclass(frozen=True, slots=True)
class IntegrityReport:
    status: CheckStatus
    checks: tuple[CheckResult, ...] = ()
    detail: str = ""


@dataclass(frozen=True, slots=True)
class DatabaseMaintenanceReport:
    status: CheckStatus
    generated_at: datetime
    connected: bool
    message: str
    schema: SchemaReport
    capacity: CapacityReport
    maintenance: MaintenanceReport
    connections: ConnectionsReport
    backups: BackupReport
    integrity: IntegrityReport
    checks: tuple[CheckResult, ...] = field(default_factory=tuple)


#: Tablas que la ventana destaca por tamaño. No es una lista de «tablas existentes»: el
#: tamaño se mide con ``pg_total_relation_size`` y los conteos con ``pg_stat_user_tables``.
CAPACITY_TOP_TABLES = 10

#: Umbral de basura por tabla para avisar (tuplas muertas absolutas y proporción).
DEAD_TUPLES_WARN_ABSOLUTE = 1_000
DEAD_TUPLES_WARN_RATIO = 0.2

#: Umbral de aviso para transacciones abiertas y conexiones frente a ``max_connections``.
LONG_TRANSACTION_WARN_SECONDS = 300.0
CONNECTIONS_WARN_RATIO = 0.8

_UNKNOWN_TABLE = "—"


class GetDatabaseMaintenance:
    """Lee el estado de PostgreSQL y lo publica sin escribir ni inventar.

    El caso de uso es deliberadamente tolerante a fallos: si una consulta concreta falla,
    su bloque queda ``unknown`` con el motivo; el resto del informe se publica igual. Si
    la BD no responde, se devuelve ``connected=False`` y **ningún** subinforme afirma
    salud.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        schema_contract: SchemaContract,
        backup_inventory: BackupInventory,
        expected_head: str | None = None,
        backup_stale_hours: float = 24.0,
    ) -> None:
        self._session = session
        self._schema_contract = schema_contract
        self._backup_inventory = backup_inventory
        self._expected_head = expected_head
        self._backup_stale_hours = backup_stale_hours

    async def execute(
        self,
        *,
        expected_head: str | None = None,
        backup_stale_hours: float | None = None,
        now: datetime | None = None,
    ) -> DatabaseMaintenanceReport:
        moment = now or datetime.now(UTC)
        head = expected_head if expected_head is not None else self._expected_head
        stale_hours = (
            backup_stale_hours
            if backup_stale_hours is not None
            else self._backup_stale_hours
        )

        if not await self._ping():
            return self._disconnected_report(moment)

        schema = await self._read_schema(head)
        capacity = await self._read_capacity()
        maintenance = await self._read_maintenance()
        connections = await self._read_connections()
        backups = self._read_backups(head, stale_hours, moment)
        integrity = await self._read_integrity()

        checks = self._flatten_checks(
            schema=schema,
            capacity=capacity,
            maintenance=maintenance,
            connections=connections,
            backups=backups,
            integrity=integrity,
        )
        status = worst_status(
            (
                schema.status,
                capacity.status,
                maintenance.status,
                connections.status,
                backups.status,
                integrity.status,
            )
        )
        return DatabaseMaintenanceReport(
            status=status,
            generated_at=moment,
            connected=True,
            message="PostgreSQL conectado",
            schema=schema,
            capacity=capacity,
            maintenance=maintenance,
            connections=connections,
            backups=backups,
            integrity=integrity,
            checks=checks,
        )

    # ------------------------------------------------------------------ helpers

    async def _ping(self) -> bool:
        try:
            await self._session.execute(text("SELECT 1"))
        except Exception:  # noqa: BLE001 — la BD puede estar caída; es un dato, no un crash
            return False
        return True

    def _disconnected_report(self, moment: datetime) -> DatabaseMaintenanceReport:
        """Sin BD no se afirma nada: todo subinforme queda ``unknown`` con su motivo."""
        reason = "PostgreSQL no responde: no se puede leer el estado"
        unknown = self._unknown_checks(reason)
        return DatabaseMaintenanceReport(
            status="error",
            generated_at=moment,
            connected=False,
            message="PostgreSQL inaccesible",
            schema=SchemaReport(
                status="unknown",
                current_revision=None,
                expected_head=None,
                database_tables=0,
                expected_tables=0,
                detail=reason,
            ),
            capacity=CapacityReport(
                status="unknown",
                database_bytes=0,
                database_pretty=_UNKNOWN_TABLE,
                detail=reason,
            ),
            maintenance=MaintenanceReport(
                status="unknown",
                autovacuum_enabled=None,
                naptime_seconds=None,
                dead_tuples_total=0,
                detail=reason,
            ),
            connections=ConnectionsReport(
                status="unknown",
                total=0,
                active=0,
                idle=0,
                idle_in_transaction=0,
                max_connections=None,
                longest_transaction_seconds=None,
                detail=reason,
            ),
            backups=BackupReport(
                status="unknown",
                accessible=False,
                directory="",
                count=0,
                retention=0,
                latest_name=None,
                latest_bytes=None,
                latest_created_at=None,
                latest_schema=None,
                age_hours=None,
                stale=None,
                checksum_present=False,
                mirror_configured=False,
                detail=reason,
            ),
            integrity=IntegrityReport(status="unknown", detail=reason),
            checks=(
                CheckResult(
                    id="database.connectivity",
                    label="Conexión a PostgreSQL",
                    status="error",
                    detail=reason,
                ),
                *unknown,
            ),
        )

    @staticmethod
    def _unknown_checks(reason: str) -> tuple[CheckResult, ...]:
        return tuple(
            CheckResult(id=check_id, label=label, status="unknown", detail=reason)
            for check_id, label in (
                ("schema.alignment", "Esquema en head"),
                ("backups.freshness", "Copia reciente"),
                ("integrity.durable_state", "Coherencia del estado durable"),
            )
        )

    async def _read_schema(self, expected_head: str | None) -> SchemaReport:
        contract = self._schema_contract.snapshot()
        try:
            current = await self._scalar_str("SELECT version_num FROM alembic_version LIMIT 1")
            rows = (
                await self._session.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                    )
                )
            ).scalars()
            database_tables = frozenset(str(name) for name in rows)

            column_rows = (
                await self._session.execute(
                    text(
                        "SELECT table_name, column_name FROM information_schema.columns "
                        "WHERE table_schema = 'public'"
                    )
                )
            ).all()
            database_columns = frozenset((str(t), str(c)) for t, c in column_rows)

            constraint_rows = (
                await self._session.execute(
                    text(
                        "SELECT conname FROM pg_constraint "
                        "WHERE connamespace = 'public'::regnamespace"
                    )
                )
            ).scalars()
            database_constraints = frozenset(str(name) for name in constraint_rows)
        except Exception as exc:  # noqa: BLE001 — catálogo ilegible: se declara
            return SchemaReport(
                status="unknown",
                current_revision=None,
                expected_head=expected_head,
                database_tables=0,
                expected_tables=len(contract.expected_tables),
                detail=f"No se pudo leer el catálogo de esquema ({_short(exc)})",
            )

        missing_tables = tuple(sorted(contract.expected_tables - database_tables))
        missing_columns = tuple(
            f"{table}.{column}"
            for table, column in sorted(contract.expected_columns - database_columns)
        )
        allowlisted = contract.allowlisted
        allowed_names = _allowlisted_table_names(allowlisted)
        allowed_objects = _allowlisted_object_names(allowlisted)
        missing_constraints = tuple(
            sorted(
                item.name
                for item in contract.expected_constraints
                if item.name not in database_constraints
                and item.name not in allowed_objects
            )
        )
        unexpected = tuple(
            sorted(
                name
                for name in database_tables - contract.expected_tables
                if name not in allowed_names
            )
        )

        problems: list[str] = []
        status: CheckStatus = "ok"
        if expected_head and current != expected_head:
            status = "error"
            problems.append(
                f"esquema {current or 'sin migrar'} ≠ head esperado {expected_head}"
            )
        if missing_tables:
            status = "error"
            problems.append(f"{len(missing_tables)} tabla(s) requeridas ausentes")
        if missing_columns:
            status = "error"
            problems.append(f"{len(missing_columns)} columna(s) requeridas ausentes")
        if missing_constraints:
            status = worst_status((status, "warning"))
            problems.append(f"{len(missing_constraints)} constraint(s) del contrato ausentes")
        if unexpected:
            status = worst_status((status, "warning"))
            problems.append(f"{len(unexpected)} tabla(s) fuera del contrato")

        if not problems:
            detail = (
                f"Esquema en head ({current}); {len(contract.expected_tables)} tablas del "
                f"contrato presentes"
                + (
                    f"; {len(allowlisted)} divergencia(s) históricas declaradas"
                    if allowlisted
                    else ""
                )
            )
        else:
            detail = "; ".join(problems) + f". Origen: {contract.source}"

        return SchemaReport(
            status=status,
            current_revision=current,
            expected_head=expected_head,
            database_tables=len(database_tables),
            expected_tables=len(contract.expected_tables),
            missing_tables=missing_tables,
            missing_columns=missing_columns,
            missing_constraints=missing_constraints,
            unexpected_tables=unexpected,
            allowlisted=allowlisted,
            detail=detail,
        )

    async def _read_capacity(self) -> CapacityReport:
        try:
            size_row = (
                await self._session.execute(
                    text("SELECT pg_database_size(current_database()) AS bytes")
                )
            ).one()
            database_bytes = int(size_row.bytes or 0)
            rows = (
                await self._session.execute(
                    text(
                        "SELECT relname, n_live_tup, "
                        "pg_total_relation_size(relid) AS bytes "
                        "FROM pg_stat_user_tables "
                        "ORDER BY pg_total_relation_size(relid) DESC "
                        "LIMIT :limit"
                    ),
                    {"limit": CAPACITY_TOP_TABLES},
                )
            ).all()
        except Exception as exc:  # noqa: BLE001
            return CapacityReport(
                status="unknown",
                database_bytes=0,
                database_pretty=_UNKNOWN_TABLE,
                detail=f"No se pudo medir el tamaño ({_short(exc)})",
            )

        tables = tuple(
            CapacityTable(
                table=str(row.relname),
                label=_table_label(str(row.relname)),
                rows=int(row.n_live_tup or 0),
                size_bytes=int(row.bytes or 0),
                size_pretty=_pretty_bytes(int(row.bytes or 0)),
            )
            for row in rows
        )
        return CapacityReport(
            status="ok",
            database_bytes=database_bytes,
            database_pretty=_pretty_bytes(database_bytes),
            tables=tables,
            detail=f"{_pretty_bytes(database_bytes)} en total; top {len(tables)} tablas por tamaño",
        )

    async def _read_maintenance(self) -> MaintenanceReport:
        try:
            settings = (
                await self._session.execute(
                    text(
                        "SELECT name, setting FROM pg_settings "
                        "WHERE name IN ('autovacuum', 'autovacuum_naptime')"
                    )
                )
            ).all()
            autovacuum = None
            naptime = None
            for row in settings:
                if row.name == "autovacuum":
                    autovacuum = str(row.setting).lower() == "on"
                elif row.name == "autovacuum_naptime":
                    naptime = int(str(row.setting))
            rows = (
                await self._session.execute(
                    text(
                        "SELECT relname, n_live_tup, n_dead_tup, "
                        "last_autovacuum, last_autoanalyze "
                        "FROM pg_stat_user_tables WHERE n_dead_tup > 0 "
                        "ORDER BY n_dead_tup DESC LIMIT :limit"
                    ),
                    {"limit": CAPACITY_TOP_TABLES},
                )
            ).all()
            total_row = (
                await self._session.execute(
                    text("SELECT COALESCE(SUM(n_dead_tup), 0) AS total FROM pg_stat_user_tables")
                )
            ).one()
        except Exception as exc:  # noqa: BLE001
            return MaintenanceReport(
                status="unknown",
                autovacuum_enabled=None,
                naptime_seconds=None,
                dead_tuples_total=0,
                detail=f"No se pudieron leer las estadísticas de mantenimiento ({_short(exc)})",
            )

        tables = tuple(
            MaintenanceTable(
                table=str(row.relname),
                live_tuples=int(row.n_live_tup or 0),
                dead_tuples=int(row.n_dead_tup or 0),
                last_autovacuum=row.last_autovacuum,
                last_autoanalyze=row.last_autoanalyze,
            )
            for row in rows
        )
        total = int(total_row.total or 0)
        last_autovacuum = max(
            (t.last_autovacuum for t in tables if t.last_autovacuum is not None),
            default=None,
        )

        status: CheckStatus = "ok"
        problems: list[str] = []
        if autovacuum is False:
            status = "warning"
            problems.append("autovacuum está desactivado")
        lagging = tuple(
            t
            for t in tables
            if t.dead_tuples >= DEAD_TUPLES_WARN_ABSOLUTE
            and t.live_tuples > 0
            and t.dead_tuples / max(t.live_tuples, 1) >= DEAD_TUPLES_WARN_RATIO
        )
        if lagging:
            status = worst_status((status, "warning"))
            problems.append(
                f"{len(lagging)} tabla(s) con ≥{int(DEAD_TUPLES_WARN_RATIO * 100)}% de "
                "tuplas muertas (autovacuum pendiente)"
            )

        detail = (
            "; ".join(problems)
            if problems
            else (
                f"autovacuum {'activo' if autovacuum else 'desconocido'}; "
                f"{total} tuplas muertas en total"
            )
        )
        return MaintenanceReport(
            status=status,
            autovacuum_enabled=autovacuum,
            naptime_seconds=naptime,
            dead_tuples_total=total,
            tables_with_dead_tuples=tables,
            last_autovacuum=last_autovacuum,
            detail=detail,
        )

    async def _read_connections(self) -> ConnectionsReport:
        try:
            rows = (
                await self._session.execute(
                    text(
                        "SELECT state, COUNT(*) AS n "
                        "FROM pg_stat_activity WHERE datname = current_database() "
                        "GROUP BY state"
                    )
                )
            ).all()
            max_row = (
                await self._session.execute(
                    text("SELECT setting FROM pg_settings WHERE name = 'max_connections'")
                )
            ).first()
            longest_row = (
                await self._session.execute(
                    text(
                        "SELECT MAX(EXTRACT(EPOCH FROM (now() - xact_start))) AS seconds "
                        "FROM pg_stat_activity "
                        "WHERE datname = current_database() AND xact_start IS NOT NULL"
                    )
                )
            ).one()
        except Exception as exc:  # noqa: BLE001
            return ConnectionsReport(
                status="unknown",
                total=0,
                active=0,
                idle=0,
                idle_in_transaction=0,
                max_connections=None,
                longest_transaction_seconds=None,
                detail=f"No se pudieron leer las conexiones ({_short(exc)})",
            )

        counts: dict[str, int] = {}
        for row in rows:
            counts[str(row.state or "unknown")] = int(row.n or 0)
        total = sum(counts.values())
        active = counts.get("active", 0)
        idle = counts.get("idle", 0)
        idle_in_transaction = counts.get("idle in transaction", 0) + counts.get(
            "idle in transaction (aborted)", 0
        )
        max_connections = int(str(max_row.setting)) if max_row is not None else None
        longest = (
            float(longest_row.seconds) if longest_row.seconds is not None else None
        )

        status: CheckStatus = "ok"
        problems: list[str] = []
        if idle_in_transaction > 0:
            status = "warning"
            problems.append(f"{idle_in_transaction} conexión(es) idle in transaction")
        if longest is not None and longest >= LONG_TRANSACTION_WARN_SECONDS:
            status = worst_status((status, "warning"))
            problems.append(f"transacción abierta desde hace {int(longest)} s")
        if max_connections and total >= max_connections * CONNECTIONS_WARN_RATIO:
            status = worst_status((status, "warning"))
            problems.append(f"{total}/{max_connections} conexiones en uso")

        detail = (
            "; ".join(problems)
            if problems
            else f"{total} conexiones ({active} activas, {idle} idle)"
        )
        return ConnectionsReport(
            status=status,
            total=total,
            active=active,
            idle=idle,
            idle_in_transaction=idle_in_transaction,
            max_connections=max_connections,
            longest_transaction_seconds=longest,
            detail=detail,
        )

    def _read_backups(
        self,
        expected_head: str | None,
        stale_hours: float,
        now: datetime,
    ) -> BackupReport:
        try:
            snapshot = self._backup_inventory.snapshot()
        except Exception as exc:  # noqa: BLE001 — el puerto no debe tumbar el informe
            return BackupReport(
                status="unknown",
                accessible=False,
                directory="",
                count=0,
                retention=0,
                latest_name=None,
                latest_bytes=None,
                latest_created_at=None,
                latest_schema=None,
                age_hours=None,
                stale=None,
                checksum_present=False,
                mirror_configured=False,
                detail=f"No se pudo leer el inventario de copias ({_short(exc)})",
            )
        return summarize_backup_snapshot(
            snapshot,
            expected_head=expected_head,
            stale_hours=stale_hours,
            now=now,
        )

    async def _read_integrity(self) -> IntegrityReport:
        checks: list[CheckResult] = []

        checks.append(await self._check_singleton())
        checks.append(await self._check_alembic_singleton())
        checks.append(await self._check_orphan_bars())
        checks.append(await self._check_duplicate_bars())
        checks.append(await self._check_orphan_ledger())
        checks.append(await self._check_provider_rows())

        available = [c for c in checks if c.status != "unknown"]
        status = worst_status(c.status for c in available) if available else "unknown"
        failed = [c for c in checks if c.status in {"warning", "error"}]
        detail = (
            "; ".join(f"{c.label}: {c.detail}" for c in failed)
            if failed
            else f"{len(checks)} comprobaciones de coherencia sin hallazgos"
        )
        return IntegrityReport(status=status, checks=tuple(checks), detail=detail)

    async def _check_singleton(self) -> CheckResult:
        try:
            row = (
                await self._session.execute(
                    text("SELECT COUNT(*) AS n, MIN(id) AS only_id FROM sync_settings")
                )
            ).one()
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                id="integrity.sync_settings_singleton",
                label="Fila única de sync_settings",
                status="unknown",
                detail=f"No se pudo comprobar ({_short(exc)})",
            )
        count = int(row.n or 0)
        if count == 1:
            return CheckResult(
                id="integrity.sync_settings_singleton",
                label="Fila única de sync_settings",
                status="ok",
                detail="Existe exactamente una fila de configuración",
                value=str(row.only_id or ""),
            )
        return CheckResult(
            id="integrity.sync_settings_singleton",
            label="Fila única de sync_settings",
            status="error",
            detail=f"Se esperaba 1 fila y hay {count}",
            value=str(count),
        )

    async def _check_alembic_singleton(self) -> CheckResult:
        try:
            row = (
                await self._session.execute(
                    text("SELECT COUNT(*) AS n FROM alembic_version")
                )
            ).one()
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                id="integrity.alembic_version_singleton",
                label="Versión de Alembic",
                status="unknown",
                detail=f"No se pudo comprobar ({_short(exc)})",
            )
        count = int(row.n or 0)
        status: CheckStatus = "ok" if count == 1 else "error"
        return CheckResult(
            id="integrity.alembic_version_singleton",
            label="Versión de Alembic",
            status=status,
            detail=(
                "Exactamente una revisión aplicada"
                if count == 1
                else f"Se esperaba 1 revisión y hay {count}"
            ),
            value=str(count),
        )

    async def _check_orphan_bars(self) -> CheckResult:
        try:
            row = (
                await self._session.execute(
                    text(
                        "SELECT EXISTS ("
                        " SELECT 1 FROM ohlcv_bars b"
                        " LEFT JOIN instruments i ON i.id = b.instrument_id"
                        " WHERE i.id IS NULL LIMIT 1) AS found"
                    )
                )
            ).one()
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                id="integrity.ohlcv_orphans",
                label="Velas sin instrumento",
                status="unknown",
                detail=f"No se pudo comprobar ({_short(exc)})",
            )
        found = bool(row.found)
        return CheckResult(
            id="integrity.ohlcv_orphans",
            label="Velas sin instrumento",
            status="error" if found else "ok",
            detail=(
                "Hay velas cuyo instrumento ya no existe"
                if found
                else "Toda vela referencia un instrumento existente"
            ),
        )

    async def _check_duplicate_bars(self) -> CheckResult:
        try:
            row = (
                await self._session.execute(
                    text(
                        "SELECT EXISTS ("
                        " SELECT 1 FROM ohlcv_bars"
                        " GROUP BY instrument_id, timeframe, timestamp"
                        " HAVING COUNT(*) > 1 LIMIT 1) AS found"
                    )
                )
            ).one()
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                id="integrity.ohlcv_duplicates",
                label="Velas duplicadas",
                status="unknown",
                detail=f"No se pudo comprobar ({_short(exc)})",
            )
        found = bool(row.found)
        return CheckResult(
            id="integrity.ohlcv_duplicates",
            label="Velas duplicadas",
            status="error" if found else "ok",
            detail=(
                "Hay más de una vela para el mismo instrumento, marco y fecha"
                if found
                else "Sin duplicados por (instrumento, marco, fecha)"
            ),
        )

    async def _check_orphan_ledger(self) -> CheckResult:
        try:
            row = (
                await self._session.execute(
                    text(
                        "SELECT EXISTS ("
                        " SELECT 1 FROM ledger_entries l"
                        " LEFT JOIN investment_accounts a ON a.id = l.account_id"
                        " WHERE l.account_id IS NOT NULL AND a.id IS NULL LIMIT 1) AS found"
                    )
                )
            ).one()
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                id="integrity.ledger_orphans",
                label="Asientos sin cuenta",
                status="unknown",
                detail=f"No se pudo comprobar ({_short(exc)})",
            )
        found = bool(row.found)
        return CheckResult(
            id="integrity.ledger_orphans",
            label="Asientos sin cuenta",
            status="error" if found else "ok",
            detail=(
                "Hay asientos que apuntan a una cuenta inexistente"
                if found
                else "Todo asiento referencia una cuenta existente"
            ),
        )

    async def _check_provider_rows(self) -> CheckResult:
        """Configuración de proveedores: si no hay filas, el estado es «sin sembrar».

        No se considera un error (la tabla se siembra en la primera lectura), pero tampoco
        un verde: sin filas no hay última comprobación persistida.
        """
        try:
            row = (
                await self._session.execute(
                    text(
                        "SELECT COUNT(*) AS n, "
                        "COUNT(last_check_at) AS measured "
                        "FROM market_provider_settings"
                    )
                )
            ).one()
        except Exception as exc:  # noqa: BLE001
            return CheckResult(
                id="integrity.provider_rows",
                label="Configuración de proveedores",
                status="unknown",
                detail=f"No se pudo comprobar ({_short(exc)})",
            )
        count = int(row.n or 0)
        measured = int(row.measured or 0)
        if count == 0:
            status: CheckStatus = "warning"
            detail = "La tabla está vacía: se sembrará en la primera lectura de proveedores"
        elif measured == 0:
            status = "warning"
            detail = f"{count} proveedor(es) sin ninguna comprobación persistida"
        else:
            status = "ok"
            detail = f"{count} proveedor(es); {measured} con medición persistida"
        return CheckResult(
            id="integrity.provider_rows",
            label="Configuración de proveedores",
            status=status,
            detail=detail,
            value=str(count),
        )

    def _flatten_checks(
        self,
        *,
        schema: SchemaReport,
        capacity: CapacityReport,
        maintenance: MaintenanceReport,
        connections: ConnectionsReport,
        backups: BackupReport,
        integrity: IntegrityReport,
    ) -> tuple[CheckResult, ...]:
        return (
            CheckResult(
                id="schema.alignment",
                label="Esquema en head",
                status=schema.status,
                detail=schema.detail,
                value=schema.current_revision,
            ),
            CheckResult(
                id="capacity.database_size",
                label="Tamaño de la base de datos",
                status=capacity.status,
                detail=capacity.detail,
                value=capacity.database_pretty,
            ),
            CheckResult(
                id="maintenance.autovacuum",
                label="Mantenimiento automático",
                status=maintenance.status,
                detail=maintenance.detail,
                value=str(maintenance.dead_tuples_total),
            ),
            CheckResult(
                id="connections.usage",
                label="Conexiones",
                status=connections.status,
                detail=connections.detail,
                value=f"{connections.total}/{connections.max_connections or '—'}",
            ),
            CheckResult(
                id="backups.freshness",
                label="Copia reciente",
                status=backups.status,
                detail=backups.detail,
                value=backups.latest_name,
            ),
            CheckResult(
                id="integrity.durable_state",
                label="Coherencia del estado durable",
                status=integrity.status,
                detail=integrity.detail,
            ),
        )

    async def _scalar_str(self, sql: str) -> str | None:
        value = (await self._session.execute(text(sql))).scalar()
        if value is None:
            return None
        text_value = str(value).strip()
        return text_value or None


#: Nombres de tabla que una entrada de allowlist puede citar («tabla.columna» o «tabla»).
def _allowlisted_table_names(entries: Sequence[str]) -> frozenset[str]:
    names: set[str] = set()
    for entry in entries:
        token = entry.strip().split()[0] if entry.strip() else ""
        if not token:
            continue
        names.add(token.split(".", 1)[0])
    return frozenset(names)


#: Nombres de objeto (constraint/índice) citados como «tabla.nombre» en la allowlist.
def _allowlisted_object_names(entries: Sequence[str]) -> frozenset[str]:
    names: set[str] = set()
    for entry in entries:
        token = entry.strip().split()[0] if entry.strip() else ""
        parts = token.split(".", 1)
        if len(parts) == 2 and parts[1]:
            names.add(parts[1])
    return frozenset(names)


def _short(exc: BaseException) -> str:
    """Mensaje corto y sin detalle de conexión para publicar en la UI."""
    message = str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__
    return message[:180]


def _pretty_bytes(size: int) -> str:
    units = ("B", "kB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{size} B"


def _table_label(table: str) -> str:
    """Etiqueta legible sin inventar nombres comerciales.

    Reutiliza las etiquetas de la ventana BD cuando existen y, si no, humaniza el nombre
    técnico: ``market_provider_settings`` → «Market provider settings».
    """
    from bolsa_application.get_database_summary import TABLE_LABELS

    for name, label in TABLE_LABELS:
        if name == table:
            return label
    humanized = table.replace("_", " ").strip()
    return humanized[:1].upper() + humanized[1:] if humanized else table
