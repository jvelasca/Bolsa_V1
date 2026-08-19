"""Casos de uso — catálogo ART-PROFILE + asignación a cuenta."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from bolsa_analytics.cognitive.investor_profile import DeclaredInvestorProfile
from bolsa_analytics.cognitive.observe_profile import (
    BehaviorTradeSample,
    observe_investor_profile,
    observed_to_dict,
)
from bolsa_analytics.cognitive.suggest_policy import suggest_policy_template_from_declared
from bolsa_domain.entities.investor_profile import InvestorProfileRecord


class InvestorProfileStore(Protocol):
    """Puerto / almacén de Investor Profile."""
    async def list_profiles(self, *, user_id: str | None = None) -> list[InvestorProfileRecord]: ...
    async def get(self, profile_id: str) -> InvestorProfileRecord | None: ...
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
    ) -> InvestorProfileRecord: ...
    async def update(self, profile_id: str, **kwargs: object) -> InvestorProfileRecord | None: ...
    async def delete(self, profile_id: str) -> bool: ...
    async def assign_to_account(
        self, account_id: str, profile_id: str | None
    ) -> str | None: ...
    async def get_for_account(self, account_id: str) -> InvestorProfileRecord | None: ...
    async def save_observed(
        self, profile_id: str, observed: dict[str, Any]
    ) -> InvestorProfileRecord | None: ...


class ListInvestorProfiles:
    """Lista Investor Profiles."""
    def __init__(self, store: InvestorProfileStore) -> None:
        self._store = store

    async def execute(self, *, user_id: str | None = None) -> list[InvestorProfileRecord]:
        return await self._store.list_profiles(user_id=user_id)


class GetInvestorProfile:
    """Obtiene Investor Profile."""
    def __init__(self, store: InvestorProfileStore) -> None:
        self._store = store

    async def execute(self, profile_id: str) -> InvestorProfileRecord | None:
        return await self._store.get(profile_id)


class CreateInvestorProfile:
    """Crea Investor Profile."""
    def __init__(self, store: InvestorProfileStore) -> None:
        self._store = store

    async def execute(self, **kwargs: object) -> InvestorProfileRecord:
        return await self._store.create(**kwargs)  # type: ignore[arg-type]


class UpdateInvestorProfile:
    """Actualiza Investor Profile."""
    def __init__(self, store: InvestorProfileStore) -> None:
        self._store = store

    async def execute(self, profile_id: str, **kwargs: object) -> InvestorProfileRecord | None:
        return await self._store.update(profile_id, **kwargs)


class DeleteInvestorProfile:
    """Elimina Investor Profile."""
    def __init__(self, store: InvestorProfileStore) -> None:
        self._store = store

    async def execute(self, profile_id: str) -> bool:
        return await self._store.delete(profile_id)


class AssignInvestorProfileToAccount:
    """Asigna Investor Profile To Account."""
    def __init__(self, store: InvestorProfileStore) -> None:
        self._store = store

    async def execute(self, account_id: str, profile_id: str | None) -> str | None:
        return await self._store.assign_to_account(account_id, profile_id)


class GetAccountInvestorProfile:
    """Obtiene Account Investor Profile."""
    def __init__(self, store: InvestorProfileStore) -> None:
        self._store = store

    async def execute(self, account_id: str) -> InvestorProfileRecord | None:
        return await self._store.get_for_account(account_id)


class EnsureDefaultInvestorProfile:
    """Crea perfil moderate + lo asigna si la cuenta no tiene active_profile_id."""

    def __init__(self, store: InvestorProfileStore) -> None:
        self._store = store

    async def execute(self, account_id: str, account_name: str) -> InvestorProfileRecord:
        existing = await self._store.get_for_account(account_id)
        if existing is not None:
            return existing
        profile = await self._store.create(
            name=f"Perfil · {account_name}".strip()[:80] or "Perfil por defecto",
            horizon="swing",
            objectives=["growth"],
            risk_tolerance="moderate",
            experience="intermediate",
            suggested_policy_template_id="moderate",
            selected_policy_template_id="moderate",
            notes="Creado automáticamente al abrir la cuenta",
        )
        await self._store.assign_to_account(account_id, profile.id)
        return profile


@dataclass(frozen=True, slots=True)
class DeclaredProfileInput:
    """Perfil declarado por el wizard al abrir la cuenta (sin depender del DTO HTTP)."""

    name: str | None = None
    horizon: str = "swing"
    objectives: list[str] = field(default_factory=lambda: ["growth"])
    risk_tolerance: str = "moderate"
    experience: str = "intermediate"
    max_acceptable_loss_pct: float | None = None
    notes: str | None = None
    suggested_policy_template_id: str | None = None
    selected_policy_template_id: str | None = None


class EnsureAccountInvestorProfile:
    """Wizard ART-PROFILE al crear cuenta: crea perfil, asigna existente o default (3 ramas)."""

    def __init__(self, store: InvestorProfileStore) -> None:
        self._store = store

    async def execute(
        self,
        *,
        account_id: str,
        account_name: str,
        declared: DeclaredProfileInput | None = None,
        active_profile_id: str | None = None,
    ) -> InvestorProfileRecord:
        if declared is not None:
            suggested = (
                declared.suggested_policy_template_id
                or suggest_policy_template_from_declared(
                    risk_tolerance=declared.risk_tolerance,
                    horizon=declared.horizon,
                    experience=declared.experience,
                )
            )
            selected = declared.selected_policy_template_id or suggested
            profile_name = (declared.name or "").strip() or f"Perfil · {account_name}".strip()[:80]
            profile = await CreateInvestorProfile(self._store).execute(  # type: ignore[arg-type]
                name=profile_name,
                horizon=declared.horizon,
                objectives=list(declared.objectives),
                risk_tolerance=declared.risk_tolerance,
                experience=declared.experience,
                max_acceptable_loss_pct=declared.max_acceptable_loss_pct,
                notes=declared.notes or "Creado con la cuenta (asistente Nueva demo)",
                suggested_policy_template_id=suggested,
                selected_policy_template_id=selected,
            )
        elif active_profile_id:
            existing = await self._store.get(active_profile_id)
            if existing is None:
                raise ValueError("Perfil inversor no encontrado")
            profile = existing
        else:
            profile = await EnsureDefaultInvestorProfile(self._store).execute(
                account_id, account_name
            )
        await self._store.assign_to_account(account_id, profile.id)
        return profile


class EnsureDefaultsForAccounts:
    """Bootstrap: garantiza perfil activo en cada cuenta (cuentas previas al catálogo)."""

    def __init__(self, store: InvestorProfileStore) -> None:
        self._store = store

    async def execute(
        self,
        accounts: list[tuple[str, str]],
    ) -> list[InvestorProfileRecord]:
        """accounts = [(account_id, account_name), ...]"""
        ensured: list[InvestorProfileRecord] = []
        for account_id, account_name in accounts:
            ensured.append(
                await EnsureDefaultInvestorProfile(self._store).execute(account_id, account_name)
            )
        return ensured


def _samples_from_memory_payloads(
    memories: list[dict[str, Any]],
) -> list[BehaviorTradeSample]:
    """Heurística: Decision Memory → muestras de conducta (sin reescribir Declared)."""
    samples: list[BehaviorTradeSample] = []
    for m in memories:
        outcome = str(m.get("outcome") or "")
        reasons = [str(r) for r in (m.get("reasons") or [])]
        text = " ".join(reasons).lower()
        breach = any(
            k in text
            for k in ("maxrisk", "risk", "concentration", "leverage", "blacklist", "veto")
        )
        if outcome == "accepted":
            samples.append(
                BehaviorTradeSample(
                    side="buy",
                    holding_hours=48.0,
                    risk_pct_of_equity=0.6,
                    followed_stop=True,
                    policy_breach=False,
                )
            )
        elif outcome == "rejected":
            samples.append(
                BehaviorTradeSample(
                    side="buy",
                    holding_hours=2.0,
                    risk_pct_of_equity=2.5 if breach else 1.0,
                    followed_stop=not breach,
                    policy_breach=breach,
                    impulsivity_flag=breach,
                )
            )
    return samples


class RefreshObservedProfile:
    """Calcula Observed desde Decision Memory y lo persiste en observed_json."""

    def __init__(self, store: InvestorProfileStore) -> None:
        self._store = store

    async def execute(
        self,
        profile_id: str,
        *,
        memory_payloads: list[dict[str, Any]] | None = None,
    ) -> InvestorProfileRecord | None:
        profile = await self._store.get(profile_id)
        if profile is None:
            return None
        declared = DeclaredInvestorProfile(
            horizon=profile.horizon,  # type: ignore[arg-type]
            objectives=profile.objectives,
            risk_tolerance=profile.risk_tolerance,  # type: ignore[arg-type]
            experience=profile.experience,  # type: ignore[arg-type]
            max_acceptable_loss_pct=profile.max_acceptable_loss_pct,
            notes=profile.notes,
        )
        samples = _samples_from_memory_payloads(memory_payloads or [])
        observed = observe_investor_profile(declared, samples)
        return await self._store.save_observed(profile_id, observed_to_dict(observed))
