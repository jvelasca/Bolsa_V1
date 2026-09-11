"""V2.27 / A10 — worker del Auto Orchestrator (env-gated, SIM-only).

Reloj de fondo que invoca ``AutoOrchestrator.run_cycle`` y ``watch_active`` con el
gate de entorno (default **OFF**), siguiendo el patrón de los workers A9:

* ``AUTO_ORCHESTRATOR_ENABLED=1`` — activa el bucle (default OFF, fail-closed).
* ``AUTO_ORCHESTRATOR_INSTRUMENTS`` — allowlist CSV **opcional**: el universo
  canónico es ESTUDIO (lista ``estudio``); si se define, **intersecta** ese universo.
  V2.35.1 (auditoría P1-01): nunca lo sustituye — sin ESTUDIO ``ok`` no se opera.
* ``AUTO_ORCHESTRATOR_INTERVAL_SECONDS`` — periodo del bucle (default 3600).
* ``AUTO_ORCHESTRATOR_SHADOW_VALIDATED=1`` — **override manual del operador**. Ya NO
  se cablea en el bucle AUTO (V2.32.1, auditoría P2-02): AUTO promociona solo con
  evidencia shadow ejecutada. El flag queda reservado a herramientas admin/manuales.
* ``AUTO_ORCHESTRATOR_FORWARD=1`` — **forward paper de la ACTIVE** (V2.33/A13, default
  OFF). Con ON, tras cada ciclo se ejecuta y persiste la evidencia forward de la ACTIVE
  sobre mercado nuevo posterior a la promoción (``AUTO_ORCHESTRATOR_FORWARD_WINDOW_BARS``,
  default 400).
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
from dataclasses import dataclass
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
# V2.34/A14: gramática controlada de Discovery (compone REGIME/TREND/MOMENTUM/TRIGGER/
# EXIT sobre el mismo presupuesto global). OFF por defecto: con OFF el discovery es
# byte-idéntico al de A13 (solo familias del catálogo).
AUTO_ORCHESTRATOR_GRAMMAR = "AUTO_ORCHESTRATOR_GRAMMAR"
AUTO_ORCHESTRATOR_GRAMMAR_MAX_COMPONENTS = "AUTO_ORCHESTRATOR_GRAMMAR_MAX_COMPONENTS"
AUTO_ORCHESTRATOR_GRAMMAR_MAX_VARIANTS = "AUTO_ORCHESTRATOR_GRAMMAR_MAX_VARIANTS"
# V2.32/A12: ventana de barras del replay shadow (evidencia del Promotion Gate).
AUTO_ORCHESTRATOR_SHADOW_WINDOW_BARS = "AUTO_ORCHESTRATOR_SHADOW_WINDOW_BARS"
_SHADOW_WINDOW_BARS_DEFAULT = 250
# V2.33/A13: forward paper de la ACTIVE sobre mercado nuevo post-promoción. OFF por
# defecto (rollout explícito y reversible): sin ON no se ejecuta ni persiste forward.
AUTO_ORCHESTRATOR_FORWARD = "AUTO_ORCHESTRATOR_FORWARD"
AUTO_ORCHESTRATOR_FORWARD_WINDOW_BARS = "AUTO_ORCHESTRATOR_FORWARD_WINDOW_BARS"
_FORWARD_WINDOW_BARS_DEFAULT = 400
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


def grammar_enabled() -> bool:
    """V2.34/A14: ¿el discovery amplía el catálogo con la gramática controlada? (OFF).

    OFF por defecto: con OFF ``discover_for_instrument`` recibe ``grammar_budget=None``
    y su salida es byte-idéntica a la de A13.
    """
    return _truthy(os.getenv(AUTO_ORCHESTRATOR_GRAMMAR))


def _int_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _discovery_budget() -> Any:
    """Presupuesto del discovery (anti-explosión combinatoria), override por env."""
    from bolsa_application.discovery_catalog import DiscoveryBudget

    return DiscoveryBudget(
        max_trials_total=_int_env(AUTO_ORCHESTRATOR_DISCOVERY_MAX_TRIALS, 48),
        max_per_family=_int_env(AUTO_ORCHESTRATOR_DISCOVERY_MAX_PER_FAMILY, 8),
        max_candidates=_int_env(AUTO_ORCHESTRATOR_DISCOVERY_MAX_CANDIDATES, 24),
    )


def _grammar_budget(discovery_budget: Any) -> Any:
    """Presupuesto de la gramática (A14), envolviendo el presupuesto global del discovery."""
    from bolsa_application.discovery_grammar import GrammarBudget

    return GrammarBudget(
        base=discovery_budget,
        max_components=_int_env(AUTO_ORCHESTRATOR_GRAMMAR_MAX_COMPONENTS, 3),
        max_per_component_variant=_int_env(AUTO_ORCHESTRATOR_GRAMMAR_MAX_VARIANTS, 4),
    )


@dataclass(slots=True)
class GrammarObservabilityCounters:
    """V2.35/A15 — contadores acumulados de la gramática en este proceso del worker.

    Solo lectura/observabilidad: no participa en ninguna decisión. Se alimentan de los
    resúmenes que devuelve ``discover_for_instrument_with_summary`` y permiten gobernar
    el rollout de ``AUTO_ORCHESTRATOR_GRAMMAR`` (cuánto aporta la gramática frente al
    catálogo) sin necesidad de persistir nada en DB (sin migración).

    V2.35.1 (auditoría P2-02): este tipo es el acumulador **de proceso** (desde el
    arranque del worker). El resumen por ciclo se emite con ``CycleGrammarCounters``,
    que se reinicia al principio de cada iteración del bucle.
    """

    discovery_calls: int = 0
    grammar_discovery_calls: int = 0
    catalog_candidates: int = 0
    grammar_candidates: int = 0
    total_candidates: int = 0
    trials_used: int = 0
    warmup_skipped: int = 0


@dataclass(slots=True)
class CycleGrammarCounters:
    """V2.35.1 (auditoría P2-02) — contadores de gramática de **un solo ciclo**.

    Mismos campos que ``GrammarObservabilityCounters`` pero efímeros: el bucle crea una
    instancia nueva al inicio de cada iteración y ``cycle_summary`` reporta solo lo
    ocurrido en ese ciclo (antes se imprimían totales de proceso bajo un nombre de
    ciclo). Solo lectura/observabilidad: no participa en ninguna decisión.
    """

    discovery_calls: int = 0
    grammar_discovery_calls: int = 0
    catalog_candidates: int = 0
    grammar_candidates: int = 0
    total_candidates: int = 0
    trials_used: int = 0
    warmup_skipped: int = 0


_PROCESS_COUNTERS = GrammarObservabilityCounters()
_CYCLE_COUNTERS = CycleGrammarCounters()


def grammar_counters() -> GrammarObservabilityCounters:
    """Contadores observados de la gramática (acumulados desde el arranque del proceso).

    Se mantiene por compatibilidad: sigue devolviendo el acumulador de proceso. El
    llamante no debe mutarlos: es un resumen de solo lectura para tests/inspección.
    """
    return _PROCESS_COUNTERS


def process_grammar_counters() -> GrammarObservabilityCounters:
    """V2.35.1 (P2-02): alias explícito del acumulador de proceso (mismo objeto)."""
    return _PROCESS_COUNTERS


def cycle_grammar_counters() -> CycleGrammarCounters:
    """V2.35.1 (P2-02): contadores del ciclo en curso (se reinician por iteración)."""
    return _CYCLE_COUNTERS


def _reset_cycle_counters() -> CycleGrammarCounters:
    """V2.35.1 (P2-02): reinicia los contadores de ciclo (una vez por iteración).

    Devuelve la instancia nueva para que el bucle pueda loguearla; el módulo guarda la
    misma referencia en ``_CYCLE_COUNTERS`` (así ``_record_discovery_summary`` siempre
    acumula en el ciclo vigente).
    """
    global _CYCLE_COUNTERS
    _CYCLE_COUNTERS = CycleGrammarCounters()
    return _CYCLE_COUNTERS


def _accumulate(counters: CycleGrammarCounters | GrammarObservabilityCounters, summary: Any) -> None:
    """Suma un resumen de discovery en ``counters`` (proceso o ciclo, observabilidad)."""
    counters.discovery_calls += 1
    if bool(getattr(summary, "grammar_enabled", False)):
        counters.grammar_discovery_calls += 1
    counters.catalog_candidates += int(getattr(summary, "catalog_candidates", 0))
    counters.grammar_candidates += int(getattr(summary, "grammar_candidates", 0))
    counters.total_candidates += int(getattr(summary, "total_candidates", 0))
    counters.trials_used += int(getattr(summary, "trials_used", 0))
    if not bool(getattr(summary, "bar_count_ok", True)):
        counters.warmup_skipped += 1


def _record_discovery_summary(summary: Any) -> None:
    """Acumula el resumen de un discovery en proceso **y** en el ciclo vigente.

    V2.35.1 (P2-02): mismo resumen, dos vistas. El acumulador de proceso
    (``_PROCESS_COUNTERS``) es monótono desde el arranque; el de ciclo
    (``_CYCLE_COUNTERS``) se reinicia al inicio de cada iteración del bucle. Solo
    observabilidad: no altera el discovery ni sus decisiones.
    """
    _accumulate(_PROCESS_COUNTERS, summary)
    _accumulate(_CYCLE_COUNTERS, summary)


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


def forward_enabled() -> bool:
    """V2.33/A13: ¿el AUTO ejecuta el forward paper de la ACTIVE? (default OFF).

    OFF por defecto: rollout explícito y reversible. Con OFF no se lee ni se persiste
    evidencia forward; el comportamiento es idéntico al de V2.32.1.
    """
    return _truthy(os.getenv(AUTO_ORCHESTRATOR_FORWARD))


def _forward_window_bars() -> int:
    """Ventana (en barras) del forward paper; override por env, default 400."""
    raw = (os.getenv(AUTO_ORCHESTRATOR_FORWARD_WINDOW_BARS) or "").strip()
    if not raw:
        return _FORWARD_WINDOW_BARS_DEFAULT
    try:
        value = int(raw)
    except ValueError:
        return _FORWARD_WINDOW_BARS_DEFAULT
    return value if value > 0 else _FORWARD_WINDOW_BARS_DEFAULT


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
    """``discovery(instrument_id)`` síncrono (función pura, sin DB/red).

    V2.34/A14: si ``AUTO_ORCHESTRATOR_GRAMMAR`` está ON, se pasa un ``GrammarBudget``
    que amplía el catálogo con la gramática controlada, consumiendo el MISMO
    presupuesto global. Con OFF el runner es idéntico al de A13.

    V2.35/A15: se usa ``discover_for_instrument_with_summary`` para emitir una línea
    de observabilidad por instrumento (catálogo vs gramática, presupuesto y cupos) y
    acumular contadores de proceso y de ciclo (``grammar_counters`` /
    ``cycle_grammar_counters``). Solo lectura: no altera el discovery ni sus decisiones.
    """
    from bolsa_application.strategy_discovery_engine import (
        discover_for_instrument_with_summary,
    )

    grammar_budget = _grammar_budget(budget) if grammar_enabled() else None
    enabled = grammar_budget is not None

    def _discover(instrument_id: str) -> tuple[Any, ...]:
        candidates, summary = discover_for_instrument_with_summary(
            instrument_id=instrument_id,
            budget=budget,
            grammar_budget=grammar_budget,
        )
        _record_discovery_summary(summary)
        logger.info(
            "auto_orchestrator discovery instrument=%s grammar_enabled=%s "
            "catalog=%s grammar=%s total=%s trials=%s catalog_cap=%s grammar_cap=%s "
            "bar_count_ok=%s",
            instrument_id,
            summary.grammar_enabled,
            summary.catalog_candidates,
            summary.grammar_candidates,
            summary.total_candidates,
            summary.trials_used,
            summary.catalog_cap,
            summary.grammar_cap,
            summary.bar_count_ok,
        )
        return candidates

    # V2.35/A15: se guarda el flag efectivo en el closure para que el bucle pueda
    # distinguir OFF/ON sin releer el entorno (el gate se evaluó al componer).
    _discover.grammar_enabled = enabled  # type: ignore[attr-defined]
    return _discover


def _bar_source(bars: tuple[Any, ...]) -> str | None:
    """``source`` del dataset de barras (H2): el de la primera barra que lo exponga.

    Todas las barras de una misma lectura comparten fuente; si ninguna lo expone, se
    devuelve ``None`` (no se inventa identidad).
    """
    for bar in bars:
        value = bar.get("source") if isinstance(bar, dict) else getattr(bar, "source", None)
        if value:
            return str(value)
    return None


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


def _make_forward_runner(session_factory: Any) -> Any:
    """``run_forward(instrument_id)`` async: ejecuta y persiste el forward de la ACTIVE.

    V2.33/A13. Para el instrumento dado:

    1. Lee la ACTIVE (y su ``promoted_at``) del lifecycle store.
    2. Lee barras OHLCV de PG (ventana amplia).
    3. Ejecuta el forward **solo** sobre barras posteriores a la promoción y persiste la
       evidencia. Sin barras nuevas ⇒ evidencia fail-closed (``forward_sin_barras``), que
       también se persiste para que la ausencia quede auditada.

    Fail-closed: sin ACTIVE o sin definición ejecutable no hay forward; un fallo de
    lectura no se convierte en aprobación (se loguea y se continúa).
    """

    async def _run_forward(instrument_id: str) -> Any:
        from bolsa_application.paper_forward_phase import (
            PaperForwardConfig,
            run_paper_forward,
        )
        from bolsa_application.strategy_lifecycle_store import (
            PostgresStrategyLifecycleStore,
        )
        from bolsa_domain.entities.strategy_lifecycle import PaperForwardPolicy

        try:
            async with session_factory() as session:
                store = PostgresStrategyLifecycleStore(session)
                record = await store.get_active(instrument_id=instrument_id)
                if record is None:
                    return None
                active = record.active
                from bolsa_api.api.dependencies import get_ohlcv_repository

                repo = get_ohlcv_repository(session)
                bars = tuple(
                    await repo.get_bars(
                        instrument_id, limit=LAB_BAR_LIMIT_DEFAULT + _forward_window_bars()
                    )
                    or ()
                )
        except Exception:  # noqa: BLE001 — sin datos no hay evidencia; no se inventa.
            logger.exception("auto_orchestrator forward read failed for %s", instrument_id)
            return None

        result = run_paper_forward(
            active=active,
            bars=bars,
            policy=PaperForwardPolicy(),
            config=PaperForwardConfig(
                promoted_at=active.promoted_at,
                window_bars=_forward_window_bars(),
                # H2 (auditoría V2.32.1): identidad del dataset en el fingerprint. El
                # repositorio lee la ventana diaria del instrumento; la fuente se toma
                # de las barras (todas comparten `source`). `adjusted` no es derivable
                # de forma fiable aquí ⇒ se deja ausente (no se inventa identidad).
                instrument_id=instrument_id,
                timeframe="1d",
                source=_bar_source(bars),
            ),
            as_of=f"forward:{instrument_id}",
        )
        try:
            async with session_factory() as session:
                store = PostgresStrategyLifecycleStore(session)
                await store.save_forward_result(result)
        except Exception:  # noqa: BLE001 — persistir no debe tumbar el ciclo.
            logger.exception("auto_orchestrator forward persist failed for %s", instrument_id)
        return result

    return _run_forward


async def _instruments_for_cycle(
    orchestrator: Any,
    *,
    allowlist: tuple[str, ...],
) -> tuple[str, ...]:
    """Instrumentos a orquestar: ESTUDIO canónico, con CSV como allowlist opcional.

    V2.35.1 (auditoría P1-01): ESTUDIO es **obligatorio** para el AUTO. Sin universo
    canónico ``ok`` y no vacío **no se opera** (``()``): ni ``unavailable``, ni
    ``empty``, ni error, ni ausencia de resolver convierten la allowlist en universo.
    La allowlist ``AUTO_ORCHESTRATOR_INSTRUMENTS`` **solo intersecta** ESTUDIO; nunca
    lo sustituye. Fail-closed: el bucle no muere, simplemente no orquesta ese ciclo.
    """
    resolver = getattr(orchestrator, "resolve_universe", None)
    if not callable(resolver):
        logger.warning(
            "auto_orchestrator: orquestador sin resolve_universe (universo ESTUDIO "
            "obligatorio) — no se orquesta nada."
        )
        return ()

    try:
        resolution = await resolver()
    except Exception:  # noqa: BLE001 — resolver caído ⇒ no se opera (fail-closed).
        logger.exception(
            "auto_orchestrator: fallo resolviendo el universo ESTUDIO — no se opera."
        )
        return ()

    if resolution is None:
        logger.warning(
            "auto_orchestrator: universo ESTUDIO no resuelto (None) — no se opera."
        )
        return ()

    status = str(getattr(resolution, "status", "") or "")
    if status != "ok":
        logger.info(
            "auto_orchestrator: universo ESTUDIO status=%s — no se opera "
            "(la allowlist no sustituye al universo; allowlist=%s).",
            status,
            allowlist,
        )
        return ()

    ids = tuple(str(i) for i in (getattr(resolution, "instrument_ids", None) or []) if i)
    if not ids:
        return ()
    if allowlist:
        # El CSV actúa como filtro/allowlist cuando está configurado.
        filtered = tuple(i for i in ids if i in set(allowlist))
        return filtered
    return ids


async def auto_orchestrator_loop(
    orchestrator: Any,
    *,
    interval_seconds: float | None = None,
    forward_runner: Any = None,
) -> None:
    """Bucle del orquestador: corre el ciclo, mide el forward y vigila la activa."""
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
                "auto_orchestrator activo pero sin instrumentos — el universo ESTUDIO "
                "es obligatorio (%s no lo sustituye); no se orquesta nada.",
                AUTO_ORCHESTRATOR_INSTRUMENTS,
            )
        cycle_id = _new_cycle_id()
        # V2.35.1 (P2-02): se reinician los contadores de ciclo al principio de cada
        # iteración (antes de orquestar instrumentos) para que ``cycle_summary`` reporte
        # SOLO este ciclo. Los acumulados de proceso siguen intactos y monótonos.
        _reset_cycle_counters()
        for instrument_id in watch:
            try:
                # V2.32.1 (auditoría P2-05): run_id por ciclo (no constante) para que
                # reintentos/re-LAB/shadow sean distinguibles en la trazabilidad.
                result = await orchestrator.run_cycle(
                    instrument_id=instrument_id,
                    run_id=f"orchestrator:{instrument_id}:{cycle_id}",
                )
                logger.info(
                    "auto_orchestrator cycle instrument=%s status=%s promoted=%s "
                    "catalog=%s grammar=%s lab_grammar=%s shadow=%s shadow_grammar=%s",
                    instrument_id,
                    result.status,
                    result.promoted,
                    getattr(result, "catalog_candidates", 0),
                    getattr(result, "grammar_candidates", 0),
                    getattr(result, "lab_grammar_evaluated", 0),
                    getattr(result, "shadow_started", 0),
                    getattr(result, "shadow_grammar_started", 0),
                )
                # V2.33/A13: forward paper de la ACTIVE sobre mercado nuevo posterior a
                # la promoción. Solo con la fase habilitada (default OFF) y sin ACTIVE
                # no hace nada; un fallo del forward no tumba el ciclo (fail-closed).
                if forward_runner is not None:
                    try:
                        forward = await forward_runner(instrument_id)
                        if forward is not None:
                            logger.info(
                                "auto_orchestrator forward instrument=%s passed=%s "
                                "round_trips=%s bars=%s",
                                instrument_id,
                                forward.passed,
                                forward.round_trips,
                                forward.bars_used,
                            )
                    except Exception:  # noqa: BLE001 — el forward no rompe la vigilancia.
                        logger.exception(
                            "auto_orchestrator forward failed for %s", instrument_id
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
        # V2.35/A15 — resumen agregado por ciclo (observabilidad de la gramática).
        # V2.35.1 (P2-02): ``cycle_summary`` reporta SOLO el ciclo vigente (contadores
        # reiniciados al inicio de la iteración); ``process_summary`` conserva los
        # acumulados desde el arranque del worker. Con la gramática OFF, los campos de
        # gramática no crecen; ambas líneas son traza explícita del rollout sin alterar
        # ninguna decisión.
        cycle = cycle_grammar_counters()
        process = process_grammar_counters()
        logger.info(
            "auto_orchestrator cycle_summary cycle_id=%s instruments=%s "
            "grammar_discoveries=%s catalog_candidates=%s grammar_candidates=%s "
            "total_candidates=%s warmup_skipped=%s",
            cycle_id,
            len(watch),
            cycle.grammar_discovery_calls,
            cycle.catalog_candidates,
            cycle.grammar_candidates,
            cycle.total_candidates,
            cycle.warmup_skipped,
        )
        logger.info(
            "auto_orchestrator process_summary cycle_id=%s "
            "discovery_calls=%s grammar_discoveries=%s catalog_candidates=%s "
            "grammar_candidates=%s total_candidates=%s warmup_skipped=%s",
            cycle_id,
            process.discovery_calls,
            process.grammar_discovery_calls,
            process.catalog_candidates,
            process.grammar_candidates,
            process.total_candidates,
            process.warmup_skipped,
        )
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
    # V2.33/A13: forward paper de la ACTIVE (default OFF). Con OFF no se ejecuta ni
    # persiste evidencia forward; el comportamiento es idéntico a V2.32.1.
    forward_runner = (
        _make_forward_runner(session_factory)
        if session_factory is not None and forward_enabled()
        else None
    )
    return asyncio.create_task(
        auto_orchestrator_loop(
            orchestrator,
            interval_seconds=interval_seconds,
            forward_runner=forward_runner,
        )
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
    from bolsa_application.strategy_shadow_phase import ShadowReplayConfig

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
            # H2 (auditoría V2.32.1): identidad de dataset en el fingerprint del shadow.
            # El provider lee la ventana diaria (TimeFrame.D1); el instrument_id se
            # resuelve por fallback desde el finalista. `source`/`adjusted` no son
            # derivables aquí de forma fiable ⇒ se dejan ausentes (no se inventa).
            shadow_config=ShadowReplayConfig(timeframe="1d"),
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
