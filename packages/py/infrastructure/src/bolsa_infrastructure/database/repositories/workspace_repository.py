from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import WorkspaceRow
from bolsa_infrastructure.ids import new_id


def _owner_visibility_clause(owner_user_id: str) -> Any:
    """F7c: filtra solo ``user_id == owner`` (legacy NULL excluido)."""
    return WorkspaceRow.user_id == owner_user_id


@dataclass(frozen=True, slots=True)
class WorkspaceSummary:
    id: str
    name: str
    is_default: bool
    updated_at: str


@dataclass(frozen=True, slots=True)
class WorkspaceRecord:
    id: str
    name: str
    is_default: bool
    document: dict[str, Any]
    dock_layout: dict[str, Any] | None
    user_id: str | None
    created_at: str
    updated_at: str


def _to_summary(row: WorkspaceRow) -> WorkspaceSummary:
    return WorkspaceSummary(
        id=row.id,
        name=row.name,
        is_default=row.is_default,
        updated_at=row.updated_at.isoformat(),
    )


def _to_record(row: WorkspaceRow) -> WorkspaceRecord:
    return WorkspaceRecord(
        id=row.id,
        name=row.name,
        is_default=row.is_default,
        document=row.document,
        dock_layout=row.dock_layout,
        user_id=row.user_id,
        created_at=row.created_at.isoformat(),
        updated_at=row.updated_at.isoformat(),
    )


class WorkspaceVersionConflict(Exception):
    """El documento cambió en el servidor desde la revisión que envió el cliente."""

    def __init__(self, current_updated_at: str) -> None:
        super().__init__("Workspace was modified by another client")
        self.current_updated_at = current_updated_at


class WorkspaceInvalidRevision(ValueError):
    """La revisión enviada no es un ISO-8601 válido.

    Antes se degradaba a `None`, lo que **desactivaba** la comprobación optimista
    (fail-open): un cliente con una revisión corrupta pisaba cualquier guardado.
    """

    def __init__(self, value: str) -> None:
        super().__init__(f"Invalid workspace revision: {value!r}")
        self.value = value


def parse_timestamp(value: str | None) -> datetime | None:
    """Parsea ISO-8601 tolerando ``Z`` y offsets (el cliente manda ``toISOString``).

    ``None``/vacío significa "sin comprobación"; un valor presente pero ilegible
    lanza ``WorkspaceInvalidRevision`` en vez de desactivar la comprobación.
    """
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise WorkspaceInvalidRevision(value) from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


#: Nombre histórico (el módulo era privado). Se conserva por compatibilidad.
_parse_timestamp = parse_timestamp


class SqlAlchemyWorkspaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self, *, owner_user_id: str) -> list[WorkspaceSummary]:
        stmt = (
            select(WorkspaceRow)
            .where(_owner_visibility_clause(owner_user_id))
            .order_by(WorkspaceRow.is_default.desc(), WorkspaceRow.name.asc())
        )
        result = await self._session.execute(stmt)
        return [_to_summary(row) for row in result.scalars().all()]

    async def get_by_id(self, workspace_id: str) -> WorkspaceRecord | None:
        stmt = select(WorkspaceRow).where(WorkspaceRow.id == workspace_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return _to_record(row) if row else None

    async def get_default(self, *, owner_user_id: str) -> WorkspaceRecord | None:
        stmt = (
            select(WorkspaceRow)
            .where(_owner_visibility_clause(owner_user_id))
            .where(WorkspaceRow.is_default.is_(True))
            .order_by(WorkspaceRow.updated_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row:
            return _to_record(row)
        stmt_any = (
            select(WorkspaceRow)
            .where(_owner_visibility_clause(owner_user_id))
            .order_by(WorkspaceRow.updated_at.desc())
            .limit(1)
        )
        result_any = await self._session.execute(stmt_any)
        fallback = result_any.scalar_one_or_none()
        return _to_record(fallback) if fallback else None

    async def create(
        self,
        *,
        name: str,
        document: dict[str, Any],
        dock_layout: dict[str, Any] | None = None,
        is_default: bool = False,
        user_id: str,
    ) -> WorkspaceRecord:
        now = datetime.now(UTC)
        if is_default:
            await self._clear_default_flag(owner_user_id=user_id)

        row = WorkspaceRow(
            id=new_id(),
            user_id=user_id,
            name=name.strip(),
            document=document,
            dock_layout=dock_layout,
            is_default=is_default,
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return _to_record(row)

    async def update(
        self,
        workspace_id: str,
        *,
        owner_user_id: str,
        name: str | None = None,
        document: dict[str, Any] | None = None,
        dock_layout: dict[str, Any] | None = None,
        is_default: bool | None = None,
        expected_updated_at: str | None = None,
    ) -> WorkspaceRecord | None:
        stmt = select(WorkspaceRow).where(WorkspaceRow.id == workspace_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        # Concurrencia optimista: si el cliente leyó una revisión anterior a la
        # actual, no se escribe (409). Evita que un documento viejo con pestañas
        # ya cerradas pise el guardado bueno de otra pestaña/dispositivo.
        expected_at = parse_timestamp(expected_updated_at)

        values: dict[str, Any] = {}
        if name is not None:
            values["name"] = name.strip()
        if document is not None:
            values["document"] = document
        if dock_layout is not None:
            values["dock_layout"] = dock_layout
        if is_default is not None:
            if is_default:
                await self._clear_default_flag(owner_user_id=owner_user_id, exclude_id=workspace_id)
            values["is_default"] = is_default
        values["updated_at"] = datetime.now(UTC)

        if expected_at is None:
            for key, value in values.items():
                setattr(row, key, value)
            await self._session.flush()
            return _to_record(row)

        # La comprobación y la escritura son UNA sola sentencia: comparar en Python
        # entre SELECT y UPDATE dejaba una ventana en la que dos clientes con la
        # misma revisión pasaban ambos y el último pisaba al primero sin 409.
        conditional = (
            update(WorkspaceRow)
            .where(WorkspaceRow.id == workspace_id)
            .where(WorkspaceRow.updated_at == expected_at)
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        written = cast(
            CursorResult[Any], await self._session.execute(conditional)
        )
        if written.rowcount == 0:
            current_at = await self._session.scalar(
                select(WorkspaceRow.updated_at).where(WorkspaceRow.id == workspace_id)
            )
            if current_at is None:
                return None
            raise WorkspaceVersionConflict(_as_utc(current_at).isoformat())
        await self._session.flush()
        await self._session.refresh(row)
        return _to_record(row)

    async def delete(self, workspace_id: str, *, owner_user_id: str) -> bool:
        stmt = select(WorkspaceRow).where(WorkspaceRow.id == workspace_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return False

        was_default = row.is_default
        await self._session.delete(row)
        await self._session.flush()

        if was_default:
            stmt_next = (
                select(WorkspaceRow)
                .where(_owner_visibility_clause(owner_user_id))
                .order_by(WorkspaceRow.updated_at.desc())
                .limit(1)
            )
            next_result = await self._session.execute(stmt_next)
            next_row = next_result.scalar_one_or_none()
            if next_row:
                next_row.is_default = True
                await self._session.flush()
        return True

    async def count(self, *, owner_user_id: str) -> int:
        stmt = select(WorkspaceRow.id).where(_owner_visibility_clause(owner_user_id))
        result = await self._session.execute(stmt)
        return len(result.scalars().all())

    async def _clear_default_flag(
        self,
        *,
        owner_user_id: str,
        exclude_id: str | None = None,
    ) -> None:
        stmt = update(WorkspaceRow).values(is_default=False).where(
            _owner_visibility_clause(owner_user_id),
        )
        if exclude_id:
            stmt = stmt.where(WorkspaceRow.id != exclude_id)
        await self._session.execute(stmt)
