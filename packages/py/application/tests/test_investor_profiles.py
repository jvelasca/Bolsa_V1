"""Casos de uso ART-PROFILE — asignación con dueño, bootstrap compartido y guard de borrado.

Store en memoria (sin PG): aísla las ramas del caso de uso que no son SQL.
La integración real (permisos por JWT, 409 y roundtrip HTTP) vive en
``apps/api-python/tests/test_investor_profiles_assign.py``.
"""

from __future__ import annotations

from typing import Any

import pytest

from bolsa_application.investor_profiles import (
    DEFAULT_PROFILE_NAME,
    AssignInvestorProfileToAccount,
    DeleteInvestorProfile,
    EnsureAccountInvestorProfile,
    EnsureDefaultInvestorProfile,
    EnsureDefaultsForAccounts,
)
from bolsa_domain.entities.investor_profile import InvestorProfileRecord


class FakeStore:
    """Store mínimo que registra llamadas (mismo contrato que el puerto)."""

    def __init__(self) -> None:
        self.profiles: dict[str, InvestorProfileRecord] = {}
        self.assigned: dict[str, str | None] = {}
        self.assign_calls: list[tuple[str, str | None, str | None]] = []
        self.deleted: list[str] = []
        self._seq = 0

    def add(
        self,
        *,
        profile_id: str,
        name: str,
        user_id: str | None,
        template: str = "moderate",
    ) -> InvestorProfileRecord:
        record = InvestorProfileRecord(
            id=profile_id,
            name=name,
            version="1.0.0",
            horizon="swing",
            objectives=("growth",),
            risk_tolerance="moderate",
            experience="intermediate",
            suggested_policy_template_id=template,
            selected_policy_template_id=template,
            updated_by="user",
            created_at="2026-10-30T00:00:00Z",
            updated_at="2026-10-30T00:00:00Z",
            user_id=user_id,
        )
        self.profiles[profile_id] = record
        return record

    async def list_profiles(
        self, *, user_id: str | None = None
    ) -> list[InvestorProfileRecord]:
        # Igual que el repositorio: ``user_id=None`` no filtra.
        if user_id is None:
            return list(self.profiles.values())
        return [p for p in self.profiles.values() if p.user_id == user_id]

    async def get(self, profile_id: str) -> InvestorProfileRecord | None:
        return self.profiles.get(profile_id)

    async def create(self, **kwargs: Any) -> InvestorProfileRecord:
        self._seq += 1
        profile_id = kwargs.get("profile_id") or f"PROF-NEW-{self._seq}"
        return self.add(
            profile_id=profile_id,
            name=str(kwargs["name"]),
            user_id=kwargs.get("user_id"),
            template=str(kwargs.get("selected_policy_template_id") or "moderate"),
        )

    async def update(self, profile_id: str, **kwargs: object) -> InvestorProfileRecord | None:
        return self.profiles.get(profile_id)

    async def delete_if_unused(self, profile_id: str) -> tuple[bool, tuple[str, ...]]:
        """Mismo contrato que el repositorio: nunca desasigna cuentas."""
        users = await self.accounts_using(profile_id)
        if users:
            return (False, tuple(name for _account_id, name in users))
        self.deleted.append(profile_id)
        return (self.profiles.pop(profile_id, None) is not None, ())

    async def assign_to_account(
        self,
        account_id: str,
        profile_id: str | None,
        *,
        owner_user_id: str | None = None,
    ) -> str | None:
        self.assign_calls.append((account_id, profile_id, owner_user_id))
        self.assigned[account_id] = profile_id
        return profile_id

    async def accounts_using(self, profile_id: str) -> list[tuple[str, str]]:
        return [
            (account_id, f"Cuenta {account_id}")
            for account_id, active in self.assigned.items()
            if active == profile_id
        ]

    async def get_for_account(self, account_id: str) -> InvestorProfileRecord | None:
        profile_id = self.assigned.get(account_id)
        return None if profile_id is None else self.profiles.get(profile_id)

    async def save_observed(
        self, profile_id: str, observed: dict[str, Any]
    ) -> InvestorProfileRecord | None:
        return self.profiles.get(profile_id)


@pytest.mark.asyncio
async def test_assign_propagates_owner_to_store() -> None:
    store = FakeStore()
    store.add(profile_id="P-1", name="Mío", user_id="user-a")

    result = await AssignInvestorProfileToAccount(store).execute(
        "ACC-1", "P-1", owner_user_id="user-a"
    )

    assert result == "P-1"
    assert store.assign_calls == [("ACC-1", "P-1", "user-a")]


@pytest.mark.asyncio
async def test_unassign_passes_none_profile() -> None:
    store = FakeStore()

    result = await AssignInvestorProfileToAccount(store).execute(
        "ACC-1", None, owner_user_id="user-a"
    )

    assert result is None
    assert store.assign_calls == [("ACC-1", None, "user-a")]


@pytest.mark.asyncio
async def test_default_profile_is_shared_per_user_and_idempotent() -> None:
    store = FakeStore()
    use_case = EnsureDefaultInvestorProfile(store)

    first = await use_case.execute("ACC-1", "Cuenta 1", user_id="user-a")
    second = await use_case.execute("ACC-2", "Cuenta 2", user_id="user-a")

    assert first.id == second.id
    assert first.name == DEFAULT_PROFILE_NAME
    assert first.user_id == "user-a"
    assert len(store.profiles) == 1
    assert store.assigned == {"ACC-1": first.id, "ACC-2": first.id}
    assert [call[2] for call in store.assign_calls] == ["user-a", "user-a"]


@pytest.mark.asyncio
async def test_default_profile_never_reuses_other_tenants_profile() -> None:
    store = FakeStore()
    # Perfil con el mismo nombre, pero de otro usuario: no debe reutilizarse.
    store.add(profile_id="P-AJENO", name=DEFAULT_PROFILE_NAME, user_id="user-b")

    profile = await EnsureDefaultInvestorProfile(store).execute(
        "ACC-1", "Cuenta 1", user_id="user-a"
    )

    assert profile.id != "P-AJENO"
    assert profile.user_id == "user-a"


@pytest.mark.asyncio
async def test_existing_account_profile_is_kept() -> None:
    store = FakeStore()
    store.add(profile_id="P-1", name="Propio", user_id="user-a")
    store.assigned["ACC-1"] = "P-1"

    profile = await EnsureDefaultInvestorProfile(store).execute(
        "ACC-1", "Cuenta 1", user_id="user-a"
    )

    assert profile.id == "P-1"
    assert store.assign_calls == []


@pytest.mark.asyncio
async def test_ensure_defaults_for_accounts_propagates_owner() -> None:
    store = FakeStore()

    ensured = await EnsureDefaultsForAccounts(store).execute(
        [("ACC-1", "Cuenta 1"), ("ACC-2", "Cuenta 2")], user_id="user-a"
    )

    assert len({p.id for p in ensured}) == 1
    assert all(call[2] == "user-a" for call in store.assign_calls)


@pytest.mark.asyncio
async def test_delete_profile_in_use_is_blocked() -> None:
    store = FakeStore()
    store.add(profile_id="P-1", name="Compartido", user_id="user-a")
    store.assigned["ACC-1"] = "P-1"

    result = await DeleteInvestorProfile(store).execute("P-1")

    assert result.deleted is False
    assert result.in_use_by == ("Cuenta ACC-1",)
    assert store.deleted == []
    assert "P-1" in store.profiles


@pytest.mark.asyncio
async def test_delete_unused_profile() -> None:
    store = FakeStore()
    store.add(profile_id="P-1", name="Libre", user_id="user-a")

    result = await DeleteInvestorProfile(store).execute("P-1")

    assert result.deleted is True
    assert result.in_use_by == ()
    assert store.deleted == ["P-1"]


@pytest.mark.asyncio
async def test_delete_delegates_guard_to_store_without_reading_accounts_first() -> None:
    """El guard es del store: el caso de uso no puede reintroducir el TOCTOU.

    Un store que ve la cuenta libre antes y ocupada al borrar (asignación concurrente)
    debe devolver ``in_use_by`` y no borrar. Si el caso de uso volviera a consultar
    ``accounts_using`` por su cuenta, ``delete_if_unused`` nunca se llamaría y el
    resultado sería un borrado silencioso.
    """

    class RacingStore(FakeStore):
        async def accounts_using(self, profile_id: str) -> list[tuple[str, str]]:
            return []

        async def delete_if_unused(self, profile_id: str) -> tuple[bool, tuple[str, ...]]:
            return (False, ("Cuenta concurrente",))

    store = RacingStore()
    store.add(profile_id="P-1", name="Carrera", user_id="user-a")

    result = await DeleteInvestorProfile(store).execute("P-1")

    assert result.deleted is False
    assert result.in_use_by == ("Cuenta concurrente",)
    assert store.deleted == []
    assert "P-1" in store.profiles


@pytest.mark.asyncio
async def test_wizard_rejects_foreign_profile() -> None:
    store = FakeStore()
    store.add(profile_id="P-AJENO", name="Ajeno", user_id="user-b")

    with pytest.raises(ValueError, match="no encontrado"):
        await EnsureAccountInvestorProfile(store).execute(
            account_id="ACC-1",
            account_name="Cuenta 1",
            active_profile_id="P-AJENO",
            user_id="user-a",
        )

    assert store.assign_calls == []
