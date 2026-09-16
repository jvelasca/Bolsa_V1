"""Sonda de LONGITUDES de la identidad de fill del AUTO (soporte del audit-pack v2.40.3).

Mide, para engines realistas, si la derivacion **historica** de la clave de fill colapsaba los N
fills de una misma orden y si la derivacion nueva los distingue. Es la medicion que respalda la
tabla de §1 del pack: el colapso no es un caso de borde, depende de la longitud del
``venue_order_id`` namespaced (P1-03) y el presupuesto historico del camino recovery (100) se cruza
**siempre** en el AUTO, tambien con el engine por defecto ``auto-sim``.

Uso: uv run --no-sync python apps/api-python/scripts/a9_identity_length_probe.py
"""

from __future__ import annotations

import re

from bolsa_application.idempotency_key import bounded_idempotency_key
from bolsa_application.simulated_settlement import auto_venue_order_id

_ACCOUNT_ID = "da84acf2-4f00-4aab-ba95-b7ddf9c4b2aa"
_INSTRUMENT_ID = "inst-a9proc-716fd8ea67"
_SIDES = ("buy", "sell")
_FILL_SEQS = (1, 2, 3, 4)
_ENGINES = (
    "auto-sim",  # default del worker (_sim_engine_id)
    "auto-sim-live-eu-01",
    "auto-a9proc-bcc03924",
    "auto-simulado-produccion-eu-west-01",
)

# Presupuestos HISTORICOS (los que usaba la implementacion de 11e2cb83).
_LEGACY_BUDGET_SIM = 120
_LEGACY_BUDGET_RECOVERY = 100


def _slug(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "-", str(value or "").strip()).strip("-") or "unknown"


def _legacy_sim(execution_id: str) -> str:
    return f"sim-fin-{_slug(execution_id)[:_LEGACY_BUDGET_SIM]}"[-128:]


def _legacy_recovery(execution_id: str) -> str:
    return f"recovery-fin-{_slug(execution_id)[:_LEGACY_BUDGET_RECOVERY]}"[-128:]


def _execution_ids(engine_id: str, side: str) -> list[str]:
    venue_order_id = auto_venue_order_id(
        engine_id=engine_id,
        account_id=_ACCOUNT_ID,
        instrument_id=_INSTRUMENT_ID,
        side=side,
        logical_order_id=f"{engine_id}-1-{side}-{_INSTRUMENT_ID}-1",
    )
    return [f"{venue_order_id}#{seq}" for seq in _FILL_SEQS]


def _distinct(keys: list[str]) -> str:
    n = len(set(keys))
    return f"{n}/{len(keys)}" + ("  COLAPSO" if n < len(keys) else "")


def main() -> None:
    header = (
        f"{'engine':34} {'side':4} {'len(exec)':>9} "
        f"{'legacy SIM':>18} {'legacy REC':>18} {'SIM nueva':>9} {'REC nueva':>9}"
    )
    print(header)
    print("-" * len(header))
    for engine_id in _ENGINES:
        for side in _SIDES:
            execution_ids = _execution_ids(engine_id, side)
            legacy_sim = [_legacy_sim(e) for e in execution_ids]
            legacy_rec = [_legacy_recovery(e) for e in execution_ids]
            new_sim = [
                bounded_idempotency_key("sim-fin-", e, legacy_budget=_LEGACY_BUDGET_SIM)
                for e in execution_ids
            ]
            new_rec = [
                bounded_idempotency_key("recovery-fin-", e, legacy_budget=_LEGACY_BUDGET_RECOVERY)
                for e in execution_ids
            ]
            print(
                f"{engine_id:34} {side:4} {len(execution_ids[0]):9} "
                f"{_distinct(legacy_sim):>18} {_distinct(legacy_rec):>18} "
                f"{_distinct(new_sim):>9} {_distinct(new_rec):>9}"
            )


if __name__ == "__main__":
    main()
