"""Repositorio catálogo ART-PROFILE."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from bolsa_domain.entities.investor_profile import InvestorProfileRecord
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_infrastructure.database.models import InvestmentAccountRow, InvestorProfileRow
from bolsa_infrastructure.ids import new_id


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _map(row: InvestorProfileRow) -> InvestorProfileRecord:
    return InvestorProfileRecord(
        id=row.id,
        name=row.name,
        version=row.version,
        horizon=row.horizon,
        objectives=tuple(str(x) for x in (row.objectives or [])),
        risk_tolerance=row.risk_tolerance,
        experience=row.experience,
        suggested_policy_template_id=row.suggested_policy_template_id,
        selected_policy_template_id=row.selected_policy_template_id,
        updated_by=row.updated_by,
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
        user_id=row.user_id,
        max_acceptable_loss_pct=(
            None if row.max_acceptable_loss_pct is None else float(row.max_acceptable_loss_pct)
        ),
        notes=row.notes,
        observed=dict(row.observed_json) if row.observed_json else None,
    )


class SqlAlchemyInvestorProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_profiles(self, *, user_id: str | None = None) -> list[InvestorProfileRecord]:
        stmt = select(InvestorProfileRow).order_by(InvestorProfileRow.updated_at.desc())
        if user_id is not None:
            stmt = stmt.where(InvestorProfileRow.user_id == user_id)
        result = await self._session.execute(stmt)
        return [_map(row) for row in result.scalars().all()]

    async def get(self, profile_id: str) -> InvestorProfileRecord | None:
        row = await self._session.get(InvestorProfileRow, profile_id)
        return None if row is None else _map(row)

    async def create(
        self,
        *,
        name: str,
        horizon: str,
        objectives: list[str],
        risk_tolerance: str,
        experience: str,
        suggested_policy_template_id: str,
        selected_policy_template_id: str,
        max_acceptable_loss_pct: float | None = None,
        notes: str | None = None,
        user_id: str | None = None,
        profile_id: str | None = None,
        version: str = "1.0.0",
    ) -> InvestorProfileRecord:
        now = datetime.now(UTC)
        row = InvestorProfileRow(
            id=profile_id or f"PROF-{new_id()[:12]}",
            name=name.strip() or "Perfil sin nombre",
            version=version,
            user_id=user_id,
            horizon=horizon,
            objectives=list(objectives),
            risk_tolerance=risk_tolerance,
            experience=experience,
            max_acceptable_loss_pct=(
                None if max_acceptable_loss_pct is None else Decimal(str(max_acceptable_loss_pct))
            ),
            notes=notes,
            suggested_policy_template_id=suggested_policy_template_id,
            selected_policy_template_id=selected_policy_template_id,
            observed_json=None,
            updated_by="user",
            created_at=now,
            updated_at=now,
        )
        self._session.add(row)
        await self._session.flush()
        return _map(row)

    async def update(
        self,
        profile_id: str,
        *,
        name: str | None = None,
        horizon: str | None = None,
        objectives: list[str] | None = None,
        risk_tolerance: str | None = None,
        experience: str | None = None,
        suggested_policy_template_id: str | None = None,
        selected_policy_template_id: str | None = None,
        max_acceptable_loss_pct: float | None | object = ...,
        notes: str | None | object = ...,
        bump_version: bool = True,
    ) -> InvestorProfileRecord | None:
        row = await self._session.get(InvestorProfileRow, profile_id)
        if row is None:
            return None
        if name is not None:
            row.name = name.strip() or row.name
        if horizon is not None:
            row.horizon = horizon
        if objectives is not None:
            row.objectives = list(objectives)
        if risk_tolerance is not None:
            row.risk_tolerance = risk_tolerance
        if experience is not None:
            row.experience = experience
        if suggested_policy_template_id is not None:
            row.suggested_policy_template_id = suggested_policy_template_id
        if selected_policy_template_id is not None:
            row.selected_policy_template_id = selected_policy_template_id
        if max_acceptable_loss_pct is not ...:
            row.max_acceptable_loss_pct = (
                None
                if max_acceptable_loss_pct is None
                else Decimal(str(max_acceptable_loss_pct))
            )
        if notes is not ...:
            row.notes = notes  # type: ignore[assignment]
        if bump_version:
            parts = row.version.split(".")
            try:
                patch = int(parts[-1]) + 1 if parts else 1
                row.version = (
                    f"{'.'.join(parts[:-1])}.{patch}" if len(parts) > 1 else f"1.0.{patch}"
                )
            except ValueError:
                row.version = f"{row.version}.1"
        row.updated_by = "user"
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return _map(row)

    async def delete(self, profile_id: str) -> bool:
        row = await self._session.get(InvestorProfileRow, profile_id)
        if row is None:
            return False
        # Desasignar cuentas
        await self._session.execute(
            update(InvestmentAccountRow)
            .where(InvestmentAccountRow.active_profile_id == profile_id)
            .values(active_profile_id=None)
        )
        await self._session.delete(row)
        await self._session.flush()
        return True

    async def assign_to_account(
        self, account_id: str, profile_id: str | None
    ) -> str | None:
        account = await self._session.get(InvestmentAccountRow, account_id)
        if account is None:
            raise ValueError("Cuenta no encontrada")
        if profile_id is not None:
            profile = await self._session.get(InvestorProfileRow, profile_id)
            if profile is None:
                raise ValueError("Perfil no encontrado")
        account.active_profile_id = profile_id
        account.updated_at = datetime.now(UTC)
        await self._session.flush()
        return account.active_profile_id

    async def get_for_account(self, account_id: str) -> InvestorProfileRecord | None:
        account = await self._session.get(InvestmentAccountRow, account_id)
        if account is None or not account.active_profile_id:
            return None
        return await self.get(account.active_profile_id)

    async def save_observed(
        self,
        profile_id: str,
        observed: dict[str, Any],
    ) -> InvestorProfileRecord | None:
        """Persiste Observed (system_observation). Nunca toca Declared."""
        row = await self._session.get(InvestorProfileRow, profile_id)
        if row is None:
            return None
        row.observed_json = dict(observed)
        row.updated_by = "system_observation"
        row.updated_at = datetime.now(UTC)
        await self._session.flush()
        return _map(row)
