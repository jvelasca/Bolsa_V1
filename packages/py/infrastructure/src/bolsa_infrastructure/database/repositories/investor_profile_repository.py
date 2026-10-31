"""Repositorio catálogo ART-PROFILE."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from bolsa_domain.entities.investor_profile import InvestorProfileRecord
from bolsa_domain.errors import AccountClosedError
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

    async def delete_if_unused(self, profile_id: str) -> tuple[bool, tuple[str, ...]]:
        """Borra el perfil SOLO si ninguna cuenta lo tiene asignado.

        La comprobación y el ``DELETE`` viven en la misma transacción y bajo el mismo
        bloqueo de fila (``SELECT … FOR UPDATE`` sobre el perfil). Cualquier asignación
        concurrente del mismo perfil pasa por ese lock, así que no puede colarse entre
        el recuento y el borrado:

        * si el borrado gana, la asignación espera el lock, relee y no encuentra el
          perfil → ``ValueError("Perfil no encontrado")`` (404), sin escribir nada;
        * si la asignación gana, el borrado espera el lock, relee y ve la cuenta → no
          borra y devuelve los nombres para el 409 ``profile_in_use``.

        Además la FK ``ON DELETE RESTRICT`` es el backstop: ni un ``DELETE`` en SQL
        crudo puede dejar una cuenta apuntando a un perfil inexistente. Este método
        **nunca** desasigna cuentas (la desasignación es un ``PUT`` explícito).
        """
        row = await self._lock_profile(profile_id)
        if row is None:
            return (False, ())
        users = await self.accounts_using(profile_id)
        if users:
            return (False, tuple(name for _account_id, name in users))
        try:
            async with self._session.begin_nested():
                await self._session.delete(row)
                await self._session.flush()
        except IntegrityError:
            # Asignación concurrente justo después del recuento: la FK RESTRICT aborta
            # el borrado. Se devuelven las cuentas para que la ruta responda 409.
            users = await self.accounts_using(profile_id)
            return (False, tuple(name for _account_id, name in users))
        return (True, ())

    async def assign_to_account(
        self,
        account_id: str,
        profile_id: str | None,
        *,
        owner_user_id: str | None = None,
    ) -> str | None:
        account = await self._session.get(InvestmentAccountRow, account_id)
        if account is None:
            raise ValueError("Cuenta no encontrada")
        if owner_user_id is not None and account.user_id != owner_user_id:
            # Cuenta ajena: mismo error que «no existe» para no filtrar su existencia.
            raise ValueError("Cuenta no encontrada")
        # CTA-D5: una cuenta cerrada es registro histórico. Cambiar (o quitar) su perfil
        # reescribiría una asignación que ya no está en operación; el cierre preserva el
        # vínculo (y por eso sigue bloqueando el borrado del perfil, AUD-03).
        if account.status == "closed":
            raise AccountClosedError()
        if profile_id is not None:
            # Se bloquea la fila del perfil igual que en ``delete_if_unused``: asignar y
            # borrar el mismo perfil se serializan sobre esa fila. Si el borrado ganó,
            # la relectura no lo encuentra → 404 en vez de un error de FK.
            profile = await self._lock_profile(profile_id)
            if profile is None or (
                owner_user_id is not None and profile.user_id != owner_user_id
            ):
                # Un perfil de otro usuario (o huérfano, user_id NULL) es invisible: 404.
                raise ValueError("Perfil no encontrado")
        account.active_profile_id = profile_id
        account.updated_at = datetime.now(UTC)
        await self._session.flush()
        return account.active_profile_id

    async def _lock_profile(self, profile_id: str) -> InvestorProfileRow | None:
        """``SELECT … FOR UPDATE`` sobre el perfil (serializa asignación y borrado)."""
        result = await self._session.execute(
            select(InvestorProfileRow)
            .where(InvestorProfileRow.id == profile_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def accounts_using(self, profile_id: str) -> list[tuple[str, str]]:
        """Cuentas con ``active_profile_id`` = ``profile_id``: (id, nombre), ordenadas."""
        result = await self._session.execute(
            select(InvestmentAccountRow.id, InvestmentAccountRow.name)
            .where(InvestmentAccountRow.active_profile_id == profile_id)
            .order_by(InvestmentAccountRow.name)
        )
        return [(str(row[0]), str(row[1])) for row in result.all()]

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
