"""Declaración de lo que AUTO tiene ENCENDIDO (y con qué números).

Qué cierra: la auditoría externa de 2026-11-08 encontró que ``pnpm dev`` no activa AUTO y
que el gobernador de drawdown y el veto por ATR real nacen apagados, sin que ninguna de
esas variables esté en ``.env.example``. Operar sin saber qué está activo es la peor
combinación posible: el motor se comporta de una forma que nadie declaró.

Este módulo es un LECTOR: no cambia ninguna decisión. Devuelve un diccionario con los
interruptores efectivos y los números asociados, más una lista de avisos legibles. Se
publica en ``/health`` (bloque ``auto_runtime``) y al arrancar el worker en el log.

Regla: un valor ausente se declara como ``None``/``False`` con su default real; nunca se
presenta como «configurado» algo que nadie configuró.
"""

from __future__ import annotations

import os
from typing import Any

from bolsa_application.flags import env_finite_float, env_flag

__all__ = ["auto_runtime_snapshot"]

#: Nombres de entorno (los mismos que consumen el worker y ``auto_v2_entry``).
ENV_WORKER = "AUTO_SIMULATION_WORKER_ENABLED"
ENV_V2 = "AUTO_ENGINE_SIM_V2"
ENV_REAL_PRICE = "AUTO_ENGINE_SIM_REAL_PRICE"
ENV_GOVERNOR = "AUTO_ENGINE_SIM_V2_GOVERNOR"
ENV_ATR_REQUIRED = "AUTO_ENGINE_SIM_V2_ATR_REQUIRED"
ENV_ACCOUNT_MAX_DD = "AUTO_ENGINE_SIM_V2_ACCOUNT_MAX_DD_PCT"
ENV_ENGINE_ID = "AUTO_ENGINE_SIM_ENGINE_ID"
ENV_EQUITY = "AUTO_ENGINE_SIM_V2_EQUITY"


def _cost_model_snapshot() -> dict[str, Any] | None:
    """Coste del sizing tal como lo resuelve el motor; ``None`` si está desactivado."""
    try:
        from bolsa_application.auto_v2_entry import tunables_from_env

        model = tunables_from_env().cost_model
    except Exception:  # noqa: BLE001 — un health no debe caerse por un import roto.
        return None
    if model is None:
        return None
    return {
        "commissionBps": model.commission_bps,
        "spreadBps": model.spread_bps,
        "slippageBps": model.slippage_bps,
        "gapBps": model.gap_bps,
    }


def auto_runtime_snapshot() -> dict[str, Any]:
    """Interruptores efectivos de AUTO + avisos. Puro: solo lee entorno."""
    worker = env_flag(ENV_WORKER, default=False)
    v2 = env_flag(ENV_V2, default=False)
    real_price = env_flag(ENV_REAL_PRICE, default=False)
    governor = env_flag(ENV_GOVERNOR, default=False)
    atr_required = env_flag(ENV_ATR_REQUIRED, default=False)
    account_max_dd = env_finite_float(ENV_ACCOUNT_MAX_DD, default=None, minimum=0.0)
    engine_id = (os.getenv(ENV_ENGINE_ID) or "").strip() or None
    equity = env_finite_float(ENV_EQUITY, default=None, minimum=0.0)
    cost_model = _cost_model_snapshot()

    warnings: list[str] = []
    if not worker:
        warnings.append(
            "AUTO apagado: AUTO_SIMULATION_WORKER_ENABLED no está en el entorno (default OFF)."
        )
    else:
        if not v2:
            warnings.append(
                "AUTO encendido SIN motor V2 (AUTO_ENGINE_SIM_V2=0 por defecto): opera el "
                "camino legacy, no el pipeline de decisión medido."
            )
        if not real_price:
            warnings.append(
                "AUTO encendido SIN precio real (AUTO_ENGINE_SIM_REAL_PRICE=0 por defecto): "
                "el camino hermético usa flat_price_script y fabrica 100.0. Lo que se ve no "
                "es el mercado."
            )
        if not governor:
            warnings.append(
                "Gobernador de drawdown APAGADO (AUTO_ENGINE_SIM_V2_GOVERNOR=0 por defecto): "
                "no escala ni veta por caída de equity."
            )
        if not atr_required:
            warnings.append(
                "Veto por ATR REAL apagado (AUTO_ENGINE_SIM_V2_ATR_REQUIRED=0 por defecto): "
                "un ATR sintético (2 % del precio) puede dimensionar el stop."
            )
        if account_max_dd is None:
            warnings.append(
                "Sin corte de drawdown de cuenta pico-valle "
                "(AUTO_ENGINE_SIM_V2_ACCOUNT_MAX_DD_PCT vacío = OFF)."
            )
        if cost_model is None:
            warnings.append(
                "Modelo de coste del sizing DESACTIVADO: el riesgo presupuestado no cubre "
                "comisión/spread/slippage."
            )
        if engine_id is None:
            warnings.append(
                "AUTO_ENGINE_SIM_ENGINE_ID ausente: con composición PostgreSQL el arranque "
                "falla (EngineIdentityMissingError) por diseño."
            )

    return {
        "workerEnabled": worker,
        "v2Enabled": v2,
        "realPrice": real_price,
        "syntheticFlatPrice": worker and not real_price,
        "governorEnabled": governor,
        "atrRequired": atr_required,
        "accountMaxDrawdownPct": account_max_dd,
        "costModel": cost_model,
        "engineId": engine_id,
        "equity": equity,
        "warnings": warnings,
    }
