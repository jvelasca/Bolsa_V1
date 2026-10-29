"""Fixtures y utilidades compartidas de los tests de la API.

Incluye el helper de limpieza de cuentas creadas por tests de integración.

Motivo: varias suites crean cuentas reales vía HTTP/Prisma y no las borraban. El residuo
se acumulaba en la BD (se llegaron a medir 89 cuentas basura), aparecía mezclado con datos
reales en la UI (todas cuelgan del owner ``app``) y además rompía el worker de custodia:
una cuenta sin cartera legacy abortaba el job completo.
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
import uuid
import warnings
from collections.abc import Iterator
from pathlib import Path

import pytest

#: La guarda de sesión vive en un módulo hermano para poder probar su lógica sin arrancar
#: una sesión de pytest anidada. ``conftest`` no siempre tiene su directorio en ``sys.path``
#: al importarse, así que se asegura de forma explícita.
_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))
import _day_watch_guard as day_watch_guard  # noqa: E402

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def _load_root_env() -> None:
    """Carga el ``.env`` de la RAÍZ del repo en ``os.environ``.

    ``Settings`` usa ``env_file=".env"``, una ruta RELATIVA al cwd. Al ejecutar pytest desde
    ``apps/api-python`` ese ``.env`` no se encuentra y la BD falla con
    ``fe_sendauth: no password supplied``. Cargarlo aquí (una vez, en import del conftest)
    hace que toda la suite funcione independientemente del cwd desde el que se invoque.
    """
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path, override=False)


_load_root_env()

# La ÚNICA cuenta que los tests NUNCA deben borrar (la siembra el bootstrap de la app).
DEMO_ACCOUNT_ID = "default-account-seed"

#: Fuente ÚNICA (JS) de la identidad de la cuenta operativa de la ventana PAPER (ADR-046).
_WINDOW_FORWARD_MJS = Path(__file__).resolve().parents[3] / "scripts" / "lib" / "window-forward.mjs"
_WINDOW_ACCOUNT_FIELD = re.compile(r"\baccount:\s*'([^']+)'")


def _window_account_id() -> str:
    """Id de la cuenta PAPER leído de ``WINDOW_CONFIG`` en el runner JS (fuente única).

    Fail-soft a ``""`` si el módulo no se puede leer: así la suíte sigue siendo hermética. El
    hueco no queda silencioso porque ``test_window_account_purge_guard.py`` (tripwire) exige que
    el id se resuelva y que coincida con el del JS.
    """
    try:
        source = _WINDOW_FORWARD_MJS.read_text(encoding="utf-8")
    except OSError:
        return ""
    start = source.find("export const WINDOW_CONFIG")
    if start < 0:
        return ""
    match = _WINDOW_ACCOUNT_FIELD.search(source, start)
    return match.group(1).strip() if match else ""


#: Ids que la suíte NUNCA debe borrar: la demo del bootstrap y la cuenta operativa de la
#: ventana PAPER.
#:
#: CAUSA RAÍZ (2026-10-16, medida con testigo controlado): la purga borraba TODA cuenta salvo la
#: demo. Como ADR-046 exige que la cuenta de la ventana sobreviva ≥4 días de calendario,
#: **cualquier `pytest` local sobre la BD compartida destruía la ventana** (volvía a `0/4` y
#: `v2_98` a `INCONCLUSIVE`). Es estado OPERATIVO, no residuo de test: se conserva.
PROTECTED_ACCOUNT_IDS = frozenset({DEMO_ACCOUNT_ID, _window_account_id()} - {""})


def residual_targets(
    all_ids: list[str],
    *,
    protected: frozenset[str] | set[str] = PROTECTED_ACCOUNT_IDS,
) -> list[str]:
    """Ids que la purga PUEDE borrar: todo lo que no sea la demo ni la cuenta de la ventana.

    Regla en UN solo sitio (la usan ``purge_accounts`` y ``purge_all_residuals``) para que no
    vuelva a divergir. Deduplica conservando el orden y descarta ids vacíos/``None``.
    """
    return [
        account_id
        for account_id in dict.fromkeys(all_ids)
        if account_id and account_id not in protected
    ]


# Tablas con FK a ``investment_accounts`` que hay que vaciar por cuenta (hijas primero).
_ACCOUNT_CHILD_TABLES = (
    "core_r_account_state",
    "supervised_f3_account_state",
    "custody_obligation",
    "custody_obligations",
    "execution_policies",
    "position_policies",
    "position_states",
    "pending_orders",
    "mandate_trade_links",
    "mandate_tenures",
    "ledger_entries",
)


async def purge_accounts(session_factory, account_ids: list[str]) -> None:
    """Borra el grafo completo de las cuentas indicadas, respetando el orden de FKs.

    Recibe el ``async_sessionmaker`` de la app (``app.state.session_factory``) y abre su
    propia sesión, para poder invocarse desde un ``finally`` sin depender de sesiones
    abiertas por el test.

    Es el teardown que deben invocar las suites que crean cuentas. Borra hijos
    (``ledger_entries``, ``mandate_tenures``, ``position_states``...), luego los
    ``investment_portfolios`` y sus portfolios legacy asociados, y por último la cuenta.

    Salvaguardas:
    - Ignora las cuentas de ``PROTECTED_ACCOUNT_IDS`` (la demo del bootstrap y la cuenta
      operativa de la ventana PAPER): un test nunca debe borrarlas.
    - Ignora IDs vacíos/duplicados.
    - Además limpia los portfolios legacy que queden huérfanos (los tests los crean en la
      tabla ``portfolios`` y el vínculo puede quedar NULL, de modo que no se arrastran solos).
    """
    from sqlalchemy import text

    targets = residual_targets(account_ids)
    if not targets:
        return

    async with session_factory() as session:
        for account_id in targets:
            portfolio_rows = await session.execute(
                text(
                    "SELECT id, legacy_portfolio_id FROM investment_portfolios "
                    "WHERE account_id = :aid"
                ),
                {"aid": account_id},
            )
            portfolios = [(str(r[0]), r[1]) for r in portfolio_rows]

            for table in _ACCOUNT_CHILD_TABLES:
                await session.execute(
                    text(f"DELETE FROM {table} WHERE account_id = :aid"),
                    {"aid": account_id},
                )

            for portfolio_id, legacy_id in portfolios:
                await session.execute(
                    text("DELETE FROM ledger_entries WHERE portfolio_id = :pid"),
                    {"pid": portfolio_id},
                )
                if legacy_id:
                    await session.execute(
                        text("DELETE FROM positions WHERE portfolio_id = :pid"),
                        {"pid": legacy_id},
                    )
                    await session.execute(
                        text("DELETE FROM transactions WHERE portfolio_id = :pid"),
                        {"pid": legacy_id},
                    )
                await session.execute(
                    text("DELETE FROM investment_portfolios WHERE id = :pid"),
                    {"pid": portfolio_id},
                )

            await session.execute(
                text("DELETE FROM investment_accounts WHERE id = :aid"),
                {"aid": account_id},
            )

        # Portfolios legacy que ya no referencia ningún investment_portfolios (huérfanos).
        orphan_filter = (
            "p.id <> 'default-portfolio-seed' AND NOT EXISTS ("
            "  SELECT 1 FROM investment_portfolios ip WHERE ip.legacy_portfolio_id = p.id"
            ")"
        )
        await session.execute(
            text(
                "DELETE FROM positions WHERE portfolio_id IN "
                f"(SELECT p.id FROM portfolios p WHERE {orphan_filter})"
            )
        )
        await session.execute(
            text(
                "DELETE FROM transactions WHERE portfolio_id IN "
                f"(SELECT p.id FROM portfolios p WHERE {orphan_filter})"
            )
        )
        await session.execute(text(f"DELETE FROM portfolios p WHERE {orphan_filter}"))

        # Perfiles de inversor que quedaron sin cuenta que los referencie.
        await session.execute(
            text(
                "DELETE FROM investor_profiles p WHERE NOT EXISTS ("
                "  SELECT 1 FROM investment_accounts a WHERE a.active_profile_id = p.id"
                ")"
            )
        )
        await session.commit()


class ResidualsUnavailable(RuntimeError):
    """La BD no responde: la limpieza de residuos no se puede (ni se debe) intentar."""


#: Tope de conexión del teardown, en segundos. Corto a propósito: la limpieza final corre
#: al cerrar CUALQUIER sesión de pytest, incluidas las puramente herméticas, así que nunca
#: debe pagar el SYN del sistema. Sin este tope, una `DATABASE_URL` heredada que apunte a
#: un puerto muerto (p. ej. `127.0.0.1:59999`, rango reservado de Windows: el SYN se
#: descarta y no llega ni ECONNREFUSED) costaba ~130 s por sesión.
_PURGE_CONNECT_TIMEOUT_S = 2


async def purge_all_residuals() -> None:
    """Borra TODO residuo de tests: cuentas, portfolios, instrumentos sintéticos y perfiles.

    Es la red de seguridad global (fixture autouse de sesión). No depende de que cada suite
    recuerde limpiar: al terminar la sesión de pytest la BD vuelve al estado sembrado.

    Sobrevive únicamente lo que siembra el bootstrap/seed:
    - ``default-account-seed`` y su ``default-portfolio-seed``.
    - La cuenta operativa de la ventana PAPER (``PROTECTED_ACCOUNT_IDS``): es estado de
      OPERACIÓN de ADR-046, no residuo de test, y debe sobrevivir ≥4 días de calendario.
    - El workspace marcado ``is_default`` (los demás se purgan: ver más abajo).
    - Los instrumentos del catálogo IBEX (los que tienen ``yahoo_symbol`` real, ``*.MC``).

    Los instrumentos sintéticos de tests se reconocen por su id ``inst-*`` (familias
    ``a11``, ``a13``, ``a14``, ``a9proc``, ``g190``...) y por símbolos ``INV*``/``dbg-*``.

    Lanza ``ResidualsUnavailable`` si la BD no responde. Es un estado legítimo (jobs
    offline, sin PostgreSQL): si la BD está caída ninguna suite pudo escribir residuo, así
    que no hay nada que limpiar y el teardown no debe convertirlo en un fallo.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError

    _load_root_env()
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    engine = create_engine(get_settings(), connect_timeout=_PURGE_CONNECT_TIMEOUT_S)
    try:
        factory = create_session_factory(engine)
        try:
            async with factory() as session:
                await session.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            raise ResidualsUnavailable(type(exc).__name__) from exc

        async with factory() as session:
            all_accounts = (
                (await session.execute(text("SELECT id FROM investment_accounts"))).scalars().all()
            )
            # La protección (demo + ventana PAPER) se aplica en Python con la MISMA regla que
            # usa `purge_accounts` (una sola fuente de verdad: `residual_targets`).
            residual_accounts = residual_targets([str(row) for row in all_accounts])
            await session.commit()

        if residual_accounts:
            await purge_accounts(factory, residual_accounts)

        async with factory() as session:
            # Instrumentos sintéticos + sus barras.
            synthetic = "(id LIKE 'inst-%' OR symbol LIKE 'INV%' OR id LIKE 'dbg-%')"
            await session.execute(
                text(
                    "DELETE FROM ohlcv_bars WHERE instrument_id IN "
                    f"(SELECT id FROM instruments WHERE {synthetic})"
                )
            )
            await session.execute(text(f"DELETE FROM instruments WHERE {synthetic}"))
            # Workspaces de test (la semilla `default` se conserva). La guarda de
            # `DeleteWorkspace` decide por CONTEO (`count <= 1` ⇒ 400 al borrar el
            # default); sin esta purga, el residuo de workspaces de sesiones previas
            # dejaba el conteo > 1 y borrar el default **dejaba de vetarse** (204 en vez
            # de 400) — la causa real del rojo intermitente de `test_workspaces.py`, que
            # el agujero de `OBS-19` ocultaba. `workspaces` no tiene FKs entrantes.
            await session.execute(text("DELETE FROM workspaces WHERE is_default = false"))
            await session.commit()
    finally:
        await engine.dispose()


def _purge_residuals_once() -> None:
    """Ejecuta una pasada de ``purge_all_residuals`` sin tumbar la sesión.

    Fail-soft deliberado: una purga que falla solo avisa (``warnings.warn``), nunca
    convierte una sesión de tests en error. Sin BD ⇒ ``ResidualsUnavailable`` ⇒ aviso.
    """
    try:
        asyncio.run(purge_all_residuals())
    except ResidualsUnavailable as exc:
        # Estado legítimo (jobs offline sin PostgreSQL): se avisa, no se falla.
        warnings.warn(
            f"[conftest] limpieza de residuos omitida: la BD no responde ({exc}). "
            "Si esperabas PostgreSQL, revisa DATABASE_URL (una variable heredada puede "
            "tener prioridad sobre el .env de la raíz).",
            stacklevel=2,
        )
    except Exception as exc:  # nunca debe tumbar la sesión de tests por la purga
        warnings.warn(
            f"[conftest] limpieza de residuos FALLÓ: {type(exc).__name__}: {exc}. "
            "Quedarán cuentas/instrumentos de test en la BD.",
            stacklevel=2,
        )


@pytest.fixture(scope="session", autouse=True)
def _cleanup_residuals_around_session() -> Iterator[None]:
    """Red de seguridad global: limpia residuos ANTES y DESPUÉS de la sesión.

    Varias suites crean cuentas/instrumentos reales y no los borran (se llegaron a medir 89
    cuentas y 127 instrumentos sintéticos acumulados). En vez de confiar en que cada suite
    recuerde limpiar, se purga todo lo que no sea la semilla.

    Purga ANTES de arrancar (residuo de una pasada anterior interrumpida que dejó la purga
    final sin ejecutar — la causa del rojo intermitente de ``test_workspaces_crud``: un
    workspace residual hacía que el conteo > 1 y el veto del default dejara de ser 400) y
    DESPUÉS (residuo de esta pasada, también si algún test falla).

    El aviso es un ``warnings.warn`` y no un ``print`` a propósito: pytest captura la
    salida, así que un ``print`` en el teardown es INVISIBLE.
    """
    _purge_residuals_once()
    yield
    _purge_residuals_once()


#: Interruptor del proveedor de precio REAL del motor AUTO.
#:
#: La suite NO hereda la configuración de la ventana PAPER: el proceso padre puede tener
#: ``AUTO_ENGINE_SIM_REAL_PRICE=1`` (es lo que inyecta el runner en el hijo de la ventana) y,
#: si se cuela en pytest, ``AutoSimRuntime`` compone ``OhlcvPriceSource`` sobre instrumentos
#: sintéticos que NO tienen barras ⇒ ``precio AUSENTE`` y HOLD fail-closed en tests que
#: inyectan ``price_script`` (medido el 2026-10-23: ``inst-gd2-*`` y el E2E del productor V2).
#: Ese rojo es una fuga de entorno de test, no un defecto del worker. El default es OFF
#: (idéntico al default de producto) y cada test que quiera precio REAL lo enciende EXPLÍCITA
#: y localmente (``monkeypatch``) o en el ``env`` del subproceso.
_AUTO_REAL_PRICE_ENV = "AUTO_ENGINE_SIM_REAL_PRICE"


@pytest.fixture(autouse=True)
def _isolate_auto_real_price_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Aísla el interruptor de precio real: OFF por defecto en TODA la suite.

    ``monkeypatch`` restaura el valor previo al terminar cada test, así que el pin no
    contamina la sesión y un test puede encenderlo dentro de su cuerpo sin pelear con esto.
    """
    monkeypatch.setenv(_AUTO_REAL_PRICE_ENV, "0")


#: Interruptor de la sonda de proveedores al arrancar la API.
#:
#: En producto está ON (es lo que puebla ``market_provider_settings.last_check_*`` al
#: reiniciar). La suite la apaga: decenas de tests entran en el ``lifespan`` y una sonda
#: real haría peticiones de red y escribiría estado compartido en la BD, convirtiendo una
#: suite hermética en una dependiente de Yahoo. Los tests que prueban la sonda la encienden
#: explícitamente y sustituyen el monitor.
_PROVIDER_HEALTH_PROBE_ENV = "PROVIDER_HEALTH_PROBE_ON_STARTUP"


@pytest.fixture(autouse=True)
def _isolate_provider_health_startup_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sonda de proveedores al arrancar: OFF por defecto en la suite."""
    monkeypatch.setenv(_PROVIDER_HEALTH_PROBE_ENV, "0")
    from bolsa_infrastructure.config import get_settings

    get_settings.cache_clear()


#: Interruptor del vigía de ventana (``window_day_watch_worker``).
#:
#: Está **on-by-default** en producto, y cualquier proceso que arranque
#: ``bolsa_api.workers.scheduler_worker`` (los PG que lanzan el worker real por
#: ``subprocess``) deja un latido en ``operability_runs/window-runs/day-watch.json`` y
#: añade una línea a ``day-watch.jsonl``. Ese directorio **no está trackeado**, así que
#: ``git status`` no lo detecta: el banco de pruebas ensuciaba artefactos del repo sin
#: que nadie lo viera (medido el 2026-10-26: la auditoría citaba una marca de tiempo que
#: ya no existía porque las pruebas la habían reescrito).
_WINDOW_DAY_WATCH_ENABLED_ENV = "WINDOW_DAY_WATCH_ENABLED"
_WINDOW_DAY_WATCH_DIR_ENV = "WINDOW_DAY_WATCH_DIR"

#: Identidad de esta corrida de pytest. Viaja en el entorno (también a los subprocesos) y
#: el latido la declara como ``runId``: así se puede atribuir una reescritura a la suite.
_PYTEST_RUN_ID = f"pytest-{uuid.uuid4().hex}"

#: Directorio de los latidos del repo (no trackeado por git).
_DAY_WATCH_REPO_DIR = (
    Path(__file__).resolve().parents[3] / "operability_runs" / "window-runs"
)


@pytest.fixture(autouse=True)
def _isolate_window_day_watch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Apaga el vigía y manda su estado a un temporal, en TODA la suite.

    Dos capas, a propósito:

    - ``WINDOW_DAY_WATCH_ENABLED=0``: ningún tick, ni en el proceso de test ni en los
      subprocesos que heredan ``os.environ``.
    - ``WINDOW_DAY_WATCH_DIR=<tmp_path>``: si un test lo enciende a propósito (el suyo lo
      hace, pasando además ``directory=``), el latido y el lock caen fuera del repo.

    Además se propaga ``BOLSA_DAY_WATCH_RUN_ID`` para que cualquier escritura que logre
    escapar sea atribuible a esta corrida (ver ``_guard_window_day_watch_artifacts``).

    ``monkeypatch`` restaura el entorno al terminar cada test, así que un test puede
    encender el vigía localmente sin contaminar al siguiente.
    """
    monkeypatch.setenv(_WINDOW_DAY_WATCH_ENABLED_ENV, "0")
    monkeypatch.setenv(_WINDOW_DAY_WATCH_DIR_ENV, str(tmp_path / "window-day-watch"))
    monkeypatch.setenv("BOLSA_DAY_WATCH_RUN_ID", _PYTEST_RUN_ID)


@pytest.fixture(scope="session", autouse=True)
def _guard_window_day_watch_artifacts() -> Iterator[None]:
    """Comprueba al terminar que la suite no reescribió ``day-watch.*`` del repositorio.

    No basta con que el contenido sea semánticamente igual: una reescritura demuestra que
    alguien tocó estado del repo, y con él la reproducibilidad de cualquier cita de esas
    cifras. La atribución es determinista: el latido declara el ``runId`` del proceso que lo
    escribió, y este proceso inyecta el suyo en el entorno (los hijos lo heredan).

    - escritor con **nuestro** ``runId`` ⇒ **falla**: la suite ensució el árbol.
    - escritor **sin** ``runId`` (o con otro) ⇒ **avisa** y se declara que la guarda no
      puede concluir: un stack de desarrollo vivo escribe el mismo fichero cada pocos
      minutos, y convertirlo en rojo haría el banco inservible.
    """
    before = day_watch_guard.fingerprint(_DAY_WATCH_REPO_DIR)
    yield
    after = day_watch_guard.fingerprint(_DAY_WATCH_REPO_DIR)
    changed = [
        name
        for name in day_watch_guard.DAY_WATCH_ARTIFACTS
        if before[name] != after[name]
    ]
    if not changed:
        return

    detail = "\n".join(
        f"  {name}: antes={before[name]} después={after[name]}" for name in changed
    )
    found = day_watch_guard.writers(before, _DAY_WATCH_REPO_DIR)
    if day_watch_guard.polluted_by(_PYTEST_RUN_ID, found):
        pytest.fail(
            "el test escribió estado del repo; aísla WINDOW_DAY_WATCH_DIR o desactiva el "
            "vigía (WINDOW_DAY_WATCH_ENABLED=0) en el proceso que arranca el scheduler.\n"
            f"{detail}\n  escritores={sorted(found)} nuestro={_PYTEST_RUN_ID}",
            pytrace=False,
        )
    warnings.warn(
        "day-watch.* cambió durante la suite, pero ningún escritor trae el runId de pytest "
        f"({_PYTEST_RUN_ID}): escritores={sorted(found) or 'sin runId'}. La guarda NO puede "
        "concluir sobre la higiene del árbol mientras haya un stack de desarrollo vivo "
        "escribiendo el latido.\n"
        f"{detail}",
        stacklevel=1,
    )


# ── Wiring de logging para las suites de redacción de credenciales (G6) ────────────────
#: Loggers que `install_log_redact()` muta (root + estos nombres).
_REDACT_TOUCHED_LOGGERS = ("bolsa_api", "uvicorn", "uvicorn.error", "uvicorn.access")


@pytest.fixture
def logging_redact_state() -> Iterator[None]:
    """Snapshot/restore del wiring de logging mutado por `install_log_redact()`.

    `install_log_redact()` adjunta `RedactFilter` a root, `bolsa_api`, uvicorn, sus handlers
    y `logging.lastResort`. Sin restaurar, el filtro sobrevive a la prueba y puede alterar
    la salida capturada por otras suites (pytest-randomly varía el orden de ejecución).
    """
    loggers = [
        logging.getLogger(),
        *(logging.getLogger(name) for name in _REDACT_TOUCHED_LOGGERS),
    ]
    snapshots = [
        (
            log,
            list(log.filters),
            list(log.handlers),
            log.propagate,
            [(handler, list(handler.filters)) for handler in log.handlers],
        )
        for log in loggers
    ]
    last_resort_filters = list(logging.lastResort.filters)
    try:
        yield
    finally:
        for log, filters, handlers, propagate, handler_filters in snapshots:
            log.filters[:] = filters
            log.handlers[:] = handlers
            log.propagate = propagate
            for handler, filters_snapshot in handler_filters:
                handler.filters[:] = filters_snapshot
        logging.lastResort.filters[:] = last_resort_filters
