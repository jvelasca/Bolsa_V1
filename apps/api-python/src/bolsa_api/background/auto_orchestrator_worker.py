"""V2.27 / A10 — worker del Auto Orchestrator (env-gated, SIM-only).

Reloj de fondo que invoca ``AutoOrchestrator.run_cycle`` y ``watch_active`` con el
gate de entorno (default **OFF**), siguiendo el patrón de los workers A9:

* ``AUTO_ORCHESTRATOR_ENABLED=1`` — activa el bucle (default OFF, fail-closed).
* ``AUTO_ORCHESTRATOR_INSTRUMENTS`` — allowlist CSV **opcional**: el universo
  canónico es ESTUDIO (lista ``estudio``); si se define, filtra ese universo.
* ``AUTO_ORCHESTRATOR_INTERVAL_SECONDS`` — periodo del bucle (default 3600).
* ``AUTO_ORCHESTRATOR_SHADOW_VALIDATED=1`` — **override manual del operador**. Ya NO
  se cablea en el bucle AUTO (V2.32.1, auditoría P2-02): AUTO promociona solo con
  evidencia shadow ejecutada. El flag queda reservado a herramientas admin/manuales.
* ``AUTO_ORCHESTRATOR_STRATEGY_FAMILY`` — familia por defecto del ESTUDIO.
* ``AUTO_ORCHESTRATOR_LAB_PARAMS`` — override JSON del grid del LAB (opcional).
* ``AUTO_ORCHESTRATOR_MAX_CANDIDATES`` — tope de candidatas por instrumento/ciclo
  (default 3; el TOP3 de ``select_top3`` es aparte).

V2.27 cablea el composition root real: ``resolve_universe`` (ESTUDIO) y
``run_optimize`` (``RunSmaGridOptimizeAndSave``) dejan de ser ``None``, de modo que
el ciclo ESTUDIO → LAB → TOP3 → COACH → PROMOTION → ACTIVE puede ejecutarse de
verdad y con evidencia persistida.

**SIM-only**: este worker no abre venues ni habilita LIVE. La ejecución sigue en el
worker AUTO SIM, cuyo ``DecisionProvider`` puede leer la estrategia ACTIVE del store
(``active_strategy_decider``) sin saltarse RiskGate/SimulationGate.
"""

from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from bolsa_api.api.dependencies import (
    get_cognitive_repository,
    get_hypothesis_belief_repository,
    get_instrument_repository,
    get_list_repository,
    get_ohlcv_repository,
    get_optimization_run_repository,
    get_research_evidence_repository,
    get_research_trial_repository,
)

logger = logging.getLogger(__name__)

AUTO_ORCHESTRATOR_ENABLED = "AUTO_ORCHESTRATOR_ENABLED"
AUTO_ORCHESTRATOR_INSTRUMENTS = "AUTO_ORCHESTRATOR_INSTRUMENTS"
AUTO_ORCHESTRATOR_INTERVAL_SECONDS = "AUTO_ORCHESTRATOR_INTERVAL_SECONDS"
AUTO_ORCHESTRATOR_SHADOW_VALIDATED = "AUTO_ORCHESTRATOR_SHADOW_VALIDATED"
# V2.27: familia por defecto del ESTUDIO, override JSON del grid del LAB, y tope de
# candidatas por instrumento/ciclo (el universo ESTUDIO es la fuente canónica).
AUTO_ORCHESTRATOR_STRATEGY_FAMILY = "AUTO_ORCHESTRATOR_STRATEGY_FAMILY"
AUTO_ORCHESTRATOR_LAB_PARAMS = "AUTO_ORCHESTRATOR_LAB_PARAMS"
AUTO_ORCHESTRATOR_MAX_CANDIDATES = "AUTO_ORCHESTRATOR_MAX_CANDIDATES"
# V2.31/A11 (P1-01): motor de descubrimiento. OFF por defecto (rollout explícito y
# reversible): con OFF se conserva la candidata única por familia fija (V2.29).
AUTO_ORCHESTRATOR_DISCOVERY = "AUTO_ORCHESTRATOR_DISCOVERY"
AUTO_ORCHESTRATOR_DISCOVERY_MAX_TRIALS = "AUTO_ORCHESTRATOR_DISCOVERY_MAX_TRIALS"
AUTO_ORCHESTRATOR_DISCOVERY_MAX_PER_FAMILY = "AUTO_ORCHESTRATOR_DISCOVERY_MAX_PER_FAMILY"
AUTO_ORCHESTRATOR_DISCOVERY_MAX_CANDIDATES = "AUTO_ORCHESTRATOR_DISCOVERY_MAX_CANDIDATES"
# V2.32/A12: ventana de barras del replay shadow (evidencia del Promotion Gate).
AUTO_ORCHESTRATOR_SHADOW_WINDOW_BARS = "AUTO_ORCHESTRATOR_SHADOW_WINDOW_BARS"
_SHADOW_WINDOW_BARS_DEFAULT = 250
# V2.32.1 (auditoría P1-01): ventana de barras del LAB (grid default). El provider
# shadow lee ``LAB_BAR_LIMIT_DEFAULT + shadow_window`` para que el hold-out exista de
# verdad (el orquestador reserva las últimas ``shadow_window`` barras al shadow).
LAB_BAR_LIMIT_DEFAULT = 400
# V2.32.1 (auditoría 2b): umbrales predictivos calibrados de la vigilancia AUTO.
AUTO_ORCHESTRATOR_HEALTH_MIN_EDGE = "AUTO_ORCHESTRATOR_HEALTH_MIN_EDGE"
AUTO_ORCHESTRATOR_HEALTH_MIN_WFE = "AUTO_ORCHESTRATOR_HEALTH_MIN_WFE"
AUTO_ORCHESTRATOR_HEALTH_MIN_DSR = "AUTO_ORCHESTRATOR_HEALTH_MIN_DSR"
AUTO_ORCHESTRATOR_HEALTH_MIN_CREDIBILITY = "AUTO_ORCHESTRATOR_HEALTH_MIN_CREDIBILITY"


def _truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


def orchestrator_enabled() -> bool:
    """Gate del bucle (default OFF, fail-closed)."""
    return _truthy(os.getenv(AUTO_ORCHESTRATOR_ENABLED))


def instrument_watch() -> tuple[str, ...]:
    raw = (os.getenv(AUTO_ORCHESTRATOR_INSTRUMENTS) or "").strip()
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _interval_seconds(default: float = 3600.0) -> float:
    raw = (os.getenv(AUTO_ORCHESTRATOR_INTERVAL_SECONDS) or "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def shadow_validated() -> bool:
    """V2.32.1: override manual del operador del Promotion Gate (default OFF).

    Ya NO es la autoridad ni se cablea en el bucle AUTO: la autoridad es la evidencia
    ejecutada por el replay shadow. Se conserva para herramientas admin/manuales y
    para que la auditoría distinga "aprobado por evidencia" de "aprobado por override".
    """
    return _truthy(os.getenv(AUTO_ORCHESTRATOR_SHADOW_VALIDATED))


def discovery_enabled() -> bool:
    """V2.31/A11: ¿el AUTO descubre estrategias en el search space curado? (OFF)."""
    return _truthy(os.getenv(AUTO_ORCHESTRATOR_DISCOVERY))


def _discovery_budget() -> Any:
    """Presupuesto del discovery (anti-explosión combinatoria), override por env."""
    from bolsa_application.discovery_catalog import DiscoveryBudget

    def _int_env(name: str, default: int) -> int:
        raw = (os.getenv(name) or "").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            return default
        return value if value > 0 else default

    return DiscoveryBudget(
        max_trials_total=_int_env(AUTO_ORCHESTRATOR_DISCOVERY_MAX_TRIALS, 48),
        max_per_family=_int_env(AUTO_ORCHESTRATOR_DISCOVERY_MAX_PER_FAMILY, 8),
        max_candidates=_int_env(AUTO_ORCHESTRATOR_DISCOVERY_MAX_CANDIDATES, 24),
    )


def _shadow_window_bars() -> int:
    """Ventana (en barras) del replay shadow; override por env, default 250."""
    raw = (os.getenv(AUTO_ORCHESTRATOR_SHADOW_WINDOW_BARS) or "").strip()
    if not raw:
        return _SHADOW_WINDOW_BARS_DEFAULT
    try:
        value = int(raw)
    except ValueError:
        return _SHADOW_WINDOW_BARS_DEFAULT
    return value if value > 0 else _SHADOW_WINDOW_BARS_DEFAULT


def _new_cycle_id() -> str:
    """Identidad única por ciclo AUTO (UTC timestamp + sufijo aleatorio corto).

    V2.32.1 (auditoría P2-05): permite distinguir ciclos, reintentos, re-LAB y shadow
    en la trazabilidad (antes todos compartían ``orchestrator:{instrument}``).
    """
    now = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{now}-{uuid.uuid4().hex[:8]}"


def _health_thresholds() -> Any:
    """Umbrales de vigilancia del AUTO (V2.32.1, auditoría 2b).

    Los predictivos (edge/wfe/dsr/credibilidad) usan ``None`` por defecto en el
    dataclass (honesto: "sin configurar"), así que el AUTO fija aquí valores
    conservadores explícitos para que la vigilancia no sea ciega. Ajustables por env
    ``AUTO_ORCHESTRATOR_HEALTH_*``; ``AUTO_ORCHESTRATOR_HEALTH_*`` no fijado conserva
    el default calibrado.
    """
    from bolsa_application.strategy_vigilance_phase import HealthThresholds

    return HealthThresholds(
        min_edge=_float_env(AUTO_ORCHESTRATOR_HEALTH_MIN_EDGE, 0.0),
        min_wfe=_float_env(AUTO_ORCHESTRATOR_HEALTH_MIN_WFE, 0.0),
        min_dsr=_float_env(AUTO_ORCHESTRATOR_HEALTH_MIN_DSR, 0.0),
        min_credibility=_float_env(AUTO_ORCHESTRATOR_HEALTH_MIN_CREDIBILITY, 0.1),
    )


def _float_env(name: str, default: float) -> float:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _make_discovery_runner(budget: Any) -> Any:
    """``discovery(instrument_id)`` síncrono (función pura, sin DB/red)."""
    from bolsa_application.strategy_discovery_engine import discover_for_instrument

    def _discover(instrument_id: str) -> tuple[Any, ...]:
        return discover_for_instrument(instrument_id=instrument_id, budget=budget)

    return _discover


def _make_shadow_bars_provider(session_factory: Any) -> Any:
    """``shadow_bars(instrument_id)`` async: barras OHLCV para el replay shadow.

    V2.32/A12: abre una sesión por llamada (mismo patrón que el resto del worker) y
    lee la ventana diaria del instrumento. Un fallo de lectura devuelve vacío: sin
    barras no hay evidencia y el Promotion Gate queda fail-closed (no se inventa).

    V2.32.1 (auditoría P1-01): se lee una ventana **más amplia** que la del LAB
    (``LAB_BAR_LIMIT_DEFAULT + shadow_window``) para que exista un hold-out estricto
    real: el orquestador reserva las últimas ``shadow_window`` barras para el shadow y
    deja el resto para el LAB, sin solape temporal.
    """

    async def _shadow_bars(instrument_id: str) -> tuple[Any, ...]:
        from bolsa_api.api.dependencies import get_ohlcv_repository

        try:
            async with session_factory() as session:
                repo = get_ohlcv_repository(session)
                bars = await repo.get_bars(
                    instrument_id,
                    limit=LAB_BAR_LIMIT_DEFAULT + _shadow_window_bars(),
                )
                return tuple(bars or ())
        except Exception:  # noqa: BLE001 — sin evidencia no se aprueba nada.
            logger.exception("auto_orchestrator shadow bars read failed for %s", instrument_id)
            return ()

    return _shadow_bars


async def _instruments_for_cycle(
    orchestrator: Any,
    *,
    allowlist: tuple[str, ...],
) -> tuple[str, ...]:
    """Instrumentos a orquestar: ESTUDIO canónico, con CSV como allowlist opcional.

    V2.27: el universo ESTUDIO es la fuente principal. Si el orquestador no expone
    ``resolve_universe`` (modo hermético/test) o el universo no está disponible, se
    cae a la allowlist ``AUTO_ORCHESTRATOR_INSTRUMENTS`` (comportamiento previo). Un
    universo ``empty``/``unavailable`` nunca inventa candidatas: fail-closed.
    """
    resolver = getattr(orchestrator, "resolve_universe", None)
    if not callable(resolver):
        return allowlist

    try:
        resolution = await resolver()
    except Exception:  # noqa: BLE001 — resolver caído ⇒ allowlist, no se inventa nada.
        logger.exception("auto_orchestrator: fallo resolviendo el universo ESTUDIO.")
        return allowlist

    if resolution is None:
        # Sin resolver cableado (modo hermético/test): comportamiento previo.
        return allowlist

    status = str(getattr(resolution, "status", "") or "")
    if status != "ok":
        logger.info(
            "auto_orchestrator: universo ESTUDIO status=%s — sin orquestación por "
            "universo (allowlist=%s).",
            status,
            allowlist,
        )
        return allowlist

    ids = tuple(str(i) for i in (getattr(resolution, "instrument_ids", None) or []) if i)
    if not ids:
        return allowlist
    if allowlist:
        # El CSV actúa como filtro/allowlist cuando está configurado.
        filtered = tuple(i for i in ids if i in set(allowlist))
        return filtered
    return ids


async def auto_orchestrator_loop(
    orchestrator: Any,
    *,
    interval_seconds: float | None = None,
) -> None:
    """Bucle del orquestador: corre el ciclo y vigila la activa por instrumento."""
    period = interval_seconds if interval_seconds is not None else _interval_seconds()
    allowlist = instrument_watch()
    # V2.32.1 (auditoría P2-02): AUTO promociona SOLO por evidencia. El override del
    # operador (`AUTO_ORCHESTRATOR_SHADOW_VALIDATED`) deja de cablearse en el camino
    # autónomo: no existe ruta NO EVIDENCE → OVERRIDE → PROMOTION. El override queda
    # reservado a herramientas manuales/admin (fuera del bucle AUTO).
    while True:
        watch = await _instruments_for_cycle(orchestrator, allowlist=allowlist)
        if not watch:
            logger.warning(
                "auto_orchestrator activo pero sin instrumentos (universo ESTUDIO no "
                "disponible y %s vacío) — no se orquesta nada.",
                AUTO_ORCHESTRATOR_INSTRUMENTS,
            )
        cycle_id = _new_cycle_id()
        for instrument_id in watch:
            try:
                # V2.32.1 (auditoría P2-05): run_id por ciclo (no constante) para que
                # reintentos/re-LAB/shadow sean distinguibles en la trazabilidad.
                result = await orchestrator.run_cycle(
                    instrument_id=instrument_id,
                    run_id=f"orchestrator:{instrument_id}:{cycle_id}",
                )
                logger.info(
                    "auto_orchestrator cycle instrument=%s status=%s promoted=%s",
                    instrument_id,
                    result.status,
                    result.promoted,
                )
                # Vigilancia de la activa. V2.28/A10 (P1-02 real): las métricas
                # observadas de la ejecución SIM las aporta el propio orquestador vía
                # ``observed_metrics`` (fills atribuidos a la versión). Aquí ya no se
                # pasa ``metrics={}``: sin evidencia observada suficiente, la vigilancia
                # no degrada por ruido (guarda de muestra mínima en el dominio).
                await orchestrator.watch_active(
                    instrument_id=instrument_id,
                    as_of=result.status,
                )
            except Exception:  # noqa: BLE001 — un fallo por instrumento no tumba el bucle.
                logger.exception("auto_orchestrator cycle failed for %s", instrument_id)
        await asyncio.sleep(period)


def start_auto_orchestrator(
    session_factory: Any = None,
    *,
    orchestrator: Any = None,
    interval_seconds: float | None = None,
) -> asyncio.Task[None] | None:
    """Starter env-gated para ``_event_loop_starters`` (default OFF, SIM).

    Con ``session_factory`` compone el store Postgres del lifecycle; sin él permite un
    ``orchestrator`` inyectado (hermético). Sin ninguno de los dos no arranca nada.
    """
    if not orchestrator_enabled():
        logger.info(
            "AutoOrchestrator (%s) desactivado — SIM-ONLY por defecto.",
            AUTO_ORCHESTRATOR_ENABLED,
        )
        return None
    if orchestrator is None:
        if session_factory is None:
            logger.warning(
                "auto_orchestrator habilitado sin session_factory ni orchestrator: "
                "no se arranca (evita un orquestador sin store)."
            )
            return None
        orchestrator = _default_orchestrator(session_factory)
    return asyncio.create_task(
        auto_orchestrator_loop(orchestrator, interval_seconds=interval_seconds)
    )


def _default_orchestrator(session_factory: Any) -> Any:
    """Compone el orquestador real: store + ESTUDIO + LAB reales (SIM-only).

    V2.27: el ciclo deja de ser una maqueta. Se cablean los dos puertos que
    ``AutoOrchestrator`` ya admitía pero que la composición real no proporcionaba:

    * ``resolve_universe`` — universo canónico ESTUDIO (lista ``estudio``) vía
      ``resolve_estudio_universe``; sustituye a ``AUTO_ORCHESTRATOR_INSTRUMENTS``
      como fuente principal (el CSV queda como allowlist opcional en el bucle).
    * ``run_optimize`` — LAB real ``RunSmaGridOptimizeAndSave`` mediante
      ``LabOptimizeRunner``; persiste el ``optimization_run`` de cada ciclo para
      que la evidencia sea auditable.

    Cada uso abre su propia sesión (patrón "una sesión por operación"), de modo que
    el orquestador no retiene una ``AsyncSession`` de larga vida.

    **SIM-only**: no se compone ninguna dependencia de LIVE. El único consumidor de
    la estrategia ACTIVE sigue siendo el worker AUTO SIM, detrás de sus gates.
    """
    from bolsa_application.auto_orchestrator import AutoOrchestrator, OrchestratorDeps
    from bolsa_application.orchestrator_lab_runner import LabOptimizeRunner
    from bolsa_application.strategy_lifecycle_store import PostgresStrategyLifecycleStore
    from bolsa_application.strategy_observed_metrics_provider import (
        make_observed_metrics_provider,
    )

    class _SessionScopedStore:
        """Store que abre una sesión por operación (imports diferidos)."""

        def __getattr__(self, name: str) -> Any:
            async def _call(*args: Any, **kwargs: Any) -> Any:
                async with session_factory() as session:
                    store = PostgresStrategyLifecycleStore(session)
                    return await getattr(store, name)(*args, **kwargs)

            return _call

    def _build_lab_use_case(session: Any) -> Any:
        """LAB real ``RunSmaGridOptimizeAndSave`` para una sesión dada (SIM-only)."""
        from bolsa_application.optimization_runs import RunSmaGridOptimizeAndSave
        from bolsa_application.optimize import RunSmaGridOptimize

        return RunSmaGridOptimizeAndSave(
            RunSmaGridOptimize(
                get_instrument_repository(session),
                get_ohlcv_repository(session),
            ),
            get_optimization_run_repository(session),
            get_research_trial_repository(session),
            get_cognitive_repository(session),
            get_research_evidence_repository(session),
            get_hypothesis_belief_repository(session),
        )

    return AutoOrchestrator(
        OrchestratorDeps(
            store=_SessionScopedStore(),
            resolve_universe=_estudio_universe_resolver(session_factory),
            run_optimize=LabOptimizeRunner(session_factory, _build_lab_use_case),
            strategy_family=_default_family(),
            params=_default_grid_params(),
            max_candidates=_max_candidates(),
            candidate_id_factory=_candidate_id_factory,
            # V2.28 / A10 (P1-02 real): vigilancia con métricas OBSERVADAS de la ejecución
            # SIM atribuida a la versión activa (fills con strategy_version_id).
            observed_metrics=make_observed_metrics_provider(session_factory),
            # V2.31/A11 (P1-01): discovery del search space curado (flag OFF por defecto).
            discovery=(
                _make_discovery_runner(_discovery_budget()) if discovery_enabled() else None
            ),
            # V2.32.1 (auditoría 2b): vigilancia con umbrales predictivos CALIBRADOS. Sin
            # esto, ``HealthThresholds()`` no degrada por edge/wfe/dsr/credibilidad
            # (``None`` = sin configurar), honesto pero ciego. El AUTO fija valores
            # conservadores por defecto, ajustables por env.
            health_thresholds=_health_thresholds(),
            # V2.32/A12: evidencia shadow ejecutada (barras OHLCV del instrumento) sobre
            # un hold-out ESTRICTO del LAB (V2.32.1, auditoría P1-01). Sin override:
            # AUTO promociona solo con evidencia (P2-02).
            shadow_bars=_make_shadow_bars_provider(session_factory),
            shadow_require_holdout=True,
        )
    )


class _SessionScopedEstudioList:
    """``EstudioListPort`` real: abre una sesión por ``execute`` (lista ``estudio``).

    ``resolve_estudio_universe`` solo necesita un objeto con ``execute(list_id)``;
    este adaptador materializa el puerto con ``GetInstrumentList`` y una sesión
    propia por llamada, sin retener sesiones de larga vida.
    """

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    async def execute(self, list_id: str) -> Any:
        from bolsa_application.lists import GetInstrumentList

        async with self._session_factory() as session:
            return await GetInstrumentList(get_list_repository(session)).execute(list_id)


def _estudio_universe_resolver(session_factory: Any) -> Any:
    """``resolve_universe`` real: universo canónico ESTUDIO (fail-closed)."""
    from bolsa_application.orchestrator_universe import make_estudio_universe_resolver

    return make_estudio_universe_resolver(_SessionScopedEstudioList(session_factory))


def _candidate_id_factory(instrument_id: str, index: int) -> str:
    """Id determinista y reproducible para una candidata del ESTUDIO."""
    return f"auto-{instrument_id}-estudio-{index}"


def _default_family() -> str:
    """Familia por defecto del ESTUDIO (familias-first: SMA/RSI/MACD)."""
    raw = (os.getenv(AUTO_ORCHESTRATOR_STRATEGY_FAMILY) or "").strip()
    if raw:
        return raw
    from bolsa_application.optimize import STRATEGY_FAMILY_SMA

    return STRATEGY_FAMILY_SMA


def _default_grid_params() -> dict[str, Any]:
    """Grid del LAB: defaults por familia en código, con override JSON por env."""
    raw = (os.getenv(AUTO_ORCHESTRATOR_LAB_PARAMS) or "").strip()
    if not raw:
        return {}
    import json

    try:
        parsed = json.loads(raw)
    except ValueError:
        logger.warning(
            "%s no es JSON válido — se ignoran overrides de grid.", AUTO_ORCHESTRATOR_LAB_PARAMS
        )
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _max_candidates() -> int:
    """Tope de candidatas por instrumento y ciclo.

    El orquestador filtra el universo por instrumento ANTES de aplicar este tope
    (``build_estudio_candidates(instrument_id=...)``), así que ya no puede dejar
    instrumentos inalcanzables. El TOP3 sigue fijo en 3 dentro de ``select_top3``.
    """
    raw = (os.getenv(AUTO_ORCHESTRATOR_MAX_CANDIDATES) or "").strip()
    if not raw:
        return 3
    try:
        value = int(raw)
    except ValueError:
        return 3
    return value if value > 0 else 3
