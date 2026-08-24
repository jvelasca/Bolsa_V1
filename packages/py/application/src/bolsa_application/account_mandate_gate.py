"""DS-03 — Account OperatingMandate gate (pure helpers).

Evalúa mandato operativo server-side desde ``mandate_tenures`` (ADR-020 M1b).
La adopción UI (``strategy-adoption``) es proyección cliente; el gate usa el
tenure abierto (`effective_to IS NULL`) por ``(account_id, instrument_id)``.

@see docs/engineering/decision-spine-cadena-2026-08-24.md DS-03
@see docs/adr/020-operating-mandate-tenure.md
"""

from __future__ import annotations

from typing import Protocol

from bolsa_infrastructure.database.repositories.mandate_repository import (
    MandateTenureRecord,
    SqlAlchemyMandateRepository,
)


def open_mandate_from_tenures(
    tenures: list[MandateTenureRecord],
    instrument_id: str,
) -> tuple[bool, str | None]:
    """Tenure abierto más reciente para ``instrument_id`` → ``(has_open, strategy_id)``."""
    open_rows = [
        t
        for t in tenures
        if t.instrument_id == instrument_id and t.effective_to is None
    ]
    if not open_rows:
        return False, None
    latest = max(open_rows, key=lambda t: t.effective_from)
    return True, latest.strategy_definition_id


def account_mandate_veto_reason(
    *,
    has_open_tenure: bool,
    require: bool = False,
    mandate_strategy_id: str | None = None,
    proposal_strategy_id: str | None = None,
) -> str | None:
    """Devuelve reason de VETO DS-03, o None si el mandato permite la apertura.

    - ``require=False`` → gate off (compat tests / wiring legado).
    - ``require=True`` sin tenure abierto → ``account_mandate:no_open_tenure``.
    - Mismatch solo cuando ambos strategy IDs están presentes (AUTO).
    """
    if not require:
        return None
    if not has_open_tenure:
        return "account_mandate:no_open_tenure"
    proposal = (proposal_strategy_id or "").strip()
    mandate = (mandate_strategy_id or "").strip()
    if proposal and mandate and proposal != mandate:
        return f"account_mandate:strategy_mismatch:proposal={proposal}:mandate={mandate}"
    return None


class AccountMandateLookup(Protocol):
    """Puerto mínimo DS-03 — tenure abierto por cuenta×instrumento."""

    async def get_open_mandate_for_instrument(
        self,
        account_id: str,
        instrument_id: str,
    ) -> tuple[bool, str | None]:
        """``(has_open_tenure, strategy_definition_id)``. Lanza si infra falla."""
        ...


class SqlAlchemyAccountMandateLookup:
    """Adapter sobre ``SqlAlchemyMandateRepository`` para el spine."""

    def __init__(self, repo: SqlAlchemyMandateRepository) -> None:
        self._repo = repo

    async def get_open_mandate_for_instrument(
        self,
        account_id: str,
        instrument_id: str,
    ) -> tuple[bool, str | None]:
        tenures = await self._repo.list_tenures(account_id, instrument_id=instrument_id)
        return open_mandate_from_tenures(tenures, instrument_id)
