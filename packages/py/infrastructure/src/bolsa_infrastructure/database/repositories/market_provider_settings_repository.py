"""Repositorio SQLAlchemy — configuración durable de proveedores de datos.

La tabla ``market_provider_settings`` (migración ``059``) guarda una fila por proveedor del
registro. La **primera lectura siembra** las filas que falten con los valores por defecto
del registro: así la UI siempre encuentra algo que mostrar y la BD no depende de que un
script de arranque se haya ejecutado.

El sembrado es idempotente y concurrible: cada ``INSERT`` va en su propio ``SAVEPOINT`` y
un choque de clave primaria (otro proceso sembró a la vez) se ignora; la lectura posterior
devuelve la fila real, no la que este proceso intentó insertar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_domain.entities.market_provider import (
    MARKET_PROVIDER_SPECS,
    MarketProviderSpec,
    provider_spec,
)
from bolsa_infrastructure.database.models import MarketProviderSettingsRow

__all__ = ["MarketProviderSettingsRecord", "SqlAlchemyMarketProviderSettingsRepository"]


@dataclass(frozen=True, slots=True)
class MarketProviderSettingsRecord:
    id: str
    enabled: bool
    priority: int
    min_interval_seconds: int
    base_url: str | None
    options: dict[str, Any]
    last_check_at: str | None
    last_check_ok: bool | None
    last_check_message: str | None
    updated_at: str


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _record(row: MarketProviderSettingsRow) -> MarketProviderSettingsRecord:
    return MarketProviderSettingsRecord(
        id=row.id,
        enabled=bool(row.enabled),
        priority=int(row.priority),
        min_interval_seconds=int(row.min_interval_seconds),
        base_url=row.base_url or None,
        options=dict(row.options or {}),
        last_check_at=_iso(row.last_check_at),
        last_check_ok=row.last_check_ok,
        last_check_message=row.last_check_message,
        updated_at=row.updated_at.isoformat(),
    )


class SqlAlchemyMarketProviderSettingsRepository:
    """Acceso durable a ``market_provider_settings``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[MarketProviderSettingsRecord]:
        """Configuración de todos los proveedores del registro (sembrando lo que falte)."""
        rows = await self._select_all()
        by_id = {row.id: row for row in rows}
        missing = [spec for spec in MARKET_PROVIDER_SPECS if spec.id not in by_id]
        if missing:
            for spec in missing:
                await self._seed(spec)
            by_id = {row.id: row for row in await self._select_all()}
        ordered = [by_id[spec.id] for spec in MARKET_PROVIDER_SPECS if spec.id in by_id]
        return [_record(row) for row in ordered]

    async def get(self, provider_id: str) -> MarketProviderSettingsRecord | None:
        spec = provider_spec(provider_id)
        if spec is None:
            return None
        stmt = select(MarketProviderSettingsRow).where(MarketProviderSettingsRow.id == spec.id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            await self._seed(spec)
            row = (await self._session.execute(stmt)).scalar_one_or_none()
        return None if row is None else _record(row)

    async def update(
        self,
        provider_id: str,
        *,
        enabled: bool | None = None,
        priority: int | None = None,
        min_interval_seconds: int | None = None,
        base_url: str | None = None,
    ) -> MarketProviderSettingsRecord | None:
        """Actualiza solo los campos declarados (``None`` = no tocar).

        ``base_url`` se distingue de «no declarado» con un centinela explícito en el
        llamante: el caso de uso pasa ``base_url=...`` solo cuando el PATCH la incluye.
        """
        stmt = select(MarketProviderSettingsRow).where(MarketProviderSettingsRow.id == provider_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        if enabled is not None:
            row.enabled = enabled
        if priority is not None:
            row.priority = priority
        if min_interval_seconds is not None:
            row.min_interval_seconds = min_interval_seconds
        if base_url is not None:
            row.base_url = base_url or None
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return _record(row)

    async def clear_base_url(self, provider_id: str) -> MarketProviderSettingsRecord | None:
        """Borra la URL configurada (un PATCH con ``baseUrl: null``)."""
        return await self.update(provider_id, base_url="")

    async def record_check(
        self,
        provider_id: str,
        *,
        ok: bool,
        message: str,
        at: datetime | None = None,
    ) -> MarketProviderSettingsRecord | None:
        """Persiste el resultado de una verificación explícita del proveedor."""
        stmt = select(MarketProviderSettingsRow).where(MarketProviderSettingsRow.id == provider_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        moment = at or datetime.now(UTC)
        row.last_check_at = moment
        row.last_check_ok = bool(ok)
        row.last_check_message = str(message)[:500]
        row.updated_at = moment
        await self._session.flush()
        return _record(row)

    # ── helpers ──────────────────────────────────────────────────────────────

    async def _select_all(self) -> list[MarketProviderSettingsRow]:
        stmt = select(MarketProviderSettingsRow)
        return list((await self._session.execute(stmt)).scalars().all())

    async def _seed(self, spec: MarketProviderSpec) -> None:
        now = datetime.now(UTC)
        row = MarketProviderSettingsRow(
            id=spec.id,
            enabled=spec.default_enabled,
            priority=spec.default_priority,
            min_interval_seconds=spec.default_min_interval_seconds,
            base_url=None,
            options={},
            last_check_at=None,
            last_check_ok=None,
            last_check_message=None,
            updated_at=now,
        )
        try:
            async with self._session.begin_nested():
                self._session.add(row)
                await self._session.flush()
        except IntegrityError:
            # Otro proceso sembró la misma fila entre la lectura y el INSERT: la fila
            # válida es la suya, no la nuestra. La relectura del llamante la resuelve.
            return
