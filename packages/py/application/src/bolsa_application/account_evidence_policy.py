"""Política de EVIDENCIA de rentabilidad por cuenta (umbrales fijados ANTES de medir).

Qué cierra: demostrar rentabilidad con backtests DÍA D exige decidir de antemano qué cuenta
como «rentable». Si el umbral se escoge mirando el resultado, la prueba no vale. Esta política
es el contrato por cuenta: número de fechas D, operaciones mínimas, % de ventanas positivas,
retorno neto mínimo, drawdown máximo, exceso sobre comprar y mantener, reserva fuera de
muestra y costes MÍNIMOS obligatorios.

Semántica fail-closed:

* **Sin fila ⇒ defaults estrictos** (``is_default=True``): la ausencia nunca relaja un umbral.
* Un valor fuera de rango NO se corrige en silencio: ``validate`` lo rechaza.
* Los costes mínimos impiden que un backtest «gratis» (0 bps) pase por evidencia.

Convenciones del repo (patrón ``auto_engine_intent_store``): Protocol + gemelo in-memory,
imports de fila perezosos, ``ON CONFLICT`` y ``autocommit`` explícito.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Protocol

__all__ = [
    "AccountEvidencePolicy",
    "AccountEvidencePolicyStore",
    "InMemoryAccountEvidencePolicyStore",
    "PostgresAccountEvidencePolicyStore",
    "default_evidence_policy",
    "policy_from_dict",
    "validate_policy",
]


@dataclass(frozen=True, slots=True)
class AccountEvidencePolicy:
    account_id: str
    min_windows: int = 30
    min_trades_total: int = 100
    min_positive_window_pct: float = 60.0
    min_net_return_pct: float = 0.0
    max_drawdown_pct: float = 15.0
    min_excess_vs_buy_hold_pct: float = 0.0
    holdout_pct: float = 30.0
    min_commission_bps: float = 5.0
    min_slippage_bps: float = 5.0
    min_spread_bps: float = 2.0
    updated_at: str | None = None
    actor: str | None = None
    version: int = 1
    is_default: bool = False

    @property
    def min_round_trip_cost_bps(self) -> float:
        """Coste mínimo ida+vuelta: comisión y slippage por lado, spread completo."""
        return 2.0 * (self.min_commission_bps + self.min_slippage_bps) + self.min_spread_bps

    def to_dict(self) -> dict[str, Any]:
        return {
            "accountId": self.account_id,
            "minWindows": self.min_windows,
            "minTradesTotal": self.min_trades_total,
            "minPositiveWindowPct": self.min_positive_window_pct,
            "minNetReturnPct": self.min_net_return_pct,
            "maxDrawdownPct": self.max_drawdown_pct,
            "minExcessVsBuyHoldPct": self.min_excess_vs_buy_hold_pct,
            "holdoutPct": self.holdout_pct,
            "minCommissionBps": self.min_commission_bps,
            "minSlippageBps": self.min_slippage_bps,
            "minSpreadBps": self.min_spread_bps,
            "minRoundTripCostBps": self.min_round_trip_cost_bps,
            "updatedAt": self.updated_at,
            "actor": self.actor,
            "version": self.version,
            "isDefault": self.is_default,
        }


def default_evidence_policy(account_id: str) -> AccountEvidencePolicy:
    return AccountEvidencePolicy(account_id=account_id, is_default=True)


_FIELDS: dict[str, tuple[str, float, float, bool]] = {
    # nombre → (alias camelCase, mínimo, máximo, entero)
    "min_windows": ("minWindows", 5, 1000, True),
    "min_trades_total": ("minTradesTotal", 30, 100000, True),
    "min_positive_window_pct": ("minPositiveWindowPct", 50, 100, False),
    "min_net_return_pct": ("minNetReturnPct", 0, 1000, False),
    "max_drawdown_pct": ("maxDrawdownPct", 1, 50, False),
    "min_excess_vs_buy_hold_pct": ("minExcessVsBuyHoldPct", 0, 1000, False),
    "holdout_pct": ("holdoutPct", 20, 60, False),
    "min_commission_bps": ("minCommissionBps", 1, 200, False),
    "min_slippage_bps": ("minSlippageBps", 1, 200, False),
    "min_spread_bps": ("minSpreadBps", 0, 200, False),
}


def validate_policy(policy: AccountEvidencePolicy) -> list[str]:
    """Violaciones de rango. Vacía ⇒ válida. Un no finito siempre es violación."""
    problems: list[str] = []
    for name, (alias, low, high, integer) in _FIELDS.items():
        value = getattr(policy, name)
        if isinstance(value, bool) or not isinstance(value, int | float):
            problems.append(f"{alias}:not_a_number")
            continue
        if not math.isfinite(value):
            problems.append(f"{alias}:not_finite")
            continue
        if integer and int(value) != value:
            problems.append(f"{alias}:not_integer")
            continue
        if value < low or value > high:
            problems.append(f"{alias}:out_of_range[{low},{high}]")
    return problems


def policy_from_dict(account_id: str, data: dict[str, Any]) -> AccountEvidencePolicy:
    """Aplica solo las claves presentes sobre los defaults y lanza si el resultado no es válido."""
    base = default_evidence_policy(account_id)
    changes: dict[str, Any] = {}
    for name, (alias, _low, _high, integer) in _FIELDS.items():
        if alias in data and data[alias] is not None:
            raw = data[alias]
            if integer and isinstance(raw, float) and raw.is_integer():
                raw = int(raw)
            changes[name] = raw
    policy = replace(base, is_default=False, **changes)
    problems = validate_policy(policy)
    if problems:
        raise ValueError("invalid evidence policy: " + ", ".join(problems))
    return policy


def _to_iso(value: Any) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else str(value.isoformat())


def _to_instant(value: Any) -> Any:
    from datetime import UTC, datetime

    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _row_to_policy(row: Any) -> AccountEvidencePolicy:
    return AccountEvidencePolicy(
        account_id=str(row.account_id),
        min_windows=int(row.min_windows),
        min_trades_total=int(row.min_trades_total),
        min_positive_window_pct=float(row.min_positive_window_pct),
        min_net_return_pct=float(row.min_net_return_pct),
        max_drawdown_pct=float(row.max_drawdown_pct),
        min_excess_vs_buy_hold_pct=float(row.min_excess_vs_buy_hold_pct),
        holdout_pct=float(row.holdout_pct),
        min_commission_bps=float(row.min_commission_bps),
        min_slippage_bps=float(row.min_slippage_bps),
        min_spread_bps=float(row.min_spread_bps),
        updated_at=_to_iso(row.updated_at),
        actor=row.actor,
        version=int(row.version or 1),
    )


class AccountEvidencePolicyStore(Protocol):
    async def load(self, account_id: str) -> AccountEvidencePolicy:
        """La política de la cuenta o los defaults estrictos si no hay fila."""
        ...

    async def save(self, policy: AccountEvidencePolicy) -> bool:
        """Alta/actualización idempotente; ``True`` si insertó."""
        ...


class InMemoryAccountEvidencePolicyStore:
    def __init__(self) -> None:
        self._rows: dict[str, AccountEvidencePolicy] = {}

    async def load(self, account_id: str) -> AccountEvidencePolicy:
        return self._rows.get(account_id) or default_evidence_policy(account_id)

    async def save(self, policy: AccountEvidencePolicy) -> bool:
        problems = validate_policy(policy)
        if problems:
            raise ValueError("invalid evidence policy: " + ", ".join(problems))
        existing = self._rows.get(policy.account_id)
        version = 1 if existing is None else existing.version + 1
        self._rows[policy.account_id] = replace(policy, version=version, is_default=False)
        return existing is None


class PostgresAccountEvidencePolicyStore:
    def __init__(self, session: Any, *, autocommit: bool = True) -> None:
        self._session = session
        self._autocommit = autocommit

    async def load(self, account_id: str) -> AccountEvidencePolicy:
        import sqlalchemy as sa
        from bolsa_infrastructure.database.models.tables import AccountEvidencePolicyRow

        row = (
            await self._session.execute(
                sa.select(AccountEvidencePolicyRow).where(
                    AccountEvidencePolicyRow.account_id == account_id
                )
            )
        ).scalar_one_or_none()
        return default_evidence_policy(account_id) if row is None else _row_to_policy(row)

    async def save(self, policy: AccountEvidencePolicy) -> bool:
        import sqlalchemy as sa
        from bolsa_infrastructure.database.models.tables import AccountEvidencePolicyRow
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        problems = validate_policy(policy)
        if problems:
            raise ValueError("invalid evidence policy: " + ", ".join(problems))
        values = {
            "account_id": policy.account_id,
            "min_windows": policy.min_windows,
            "min_trades_total": policy.min_trades_total,
            "min_positive_window_pct": policy.min_positive_window_pct,
            "min_net_return_pct": policy.min_net_return_pct,
            "max_drawdown_pct": policy.max_drawdown_pct,
            "min_excess_vs_buy_hold_pct": policy.min_excess_vs_buy_hold_pct,
            "holdout_pct": policy.holdout_pct,
            "min_commission_bps": policy.min_commission_bps,
            "min_slippage_bps": policy.min_slippage_bps,
            "min_spread_bps": policy.min_spread_bps,
            "actor": policy.actor,
            "updated_at": _to_instant(policy.updated_at),
            "version": 1,
        }
        result = await self._session.execute(
            pg_insert(AccountEvidencePolicyRow)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["account_id"])
            .returning(AccountEvidencePolicyRow.account_id)
        )
        inserted = result.scalars().first() is not None
        if not inserted:
            update_values = {k: v for k, v in values.items() if k not in ("account_id", "version")}
            update_values["version"] = AccountEvidencePolicyRow.version + 1
            await self._session.execute(
                sa.update(AccountEvidencePolicyRow)
                .where(AccountEvidencePolicyRow.account_id == policy.account_id)
                .values(**update_values)
            )
        if self._autocommit:
            await self._session.commit()
        return inserted
