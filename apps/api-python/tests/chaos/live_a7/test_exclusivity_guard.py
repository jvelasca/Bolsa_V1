"""Contrato de la guarda de exclusividad de ``chaos/live_a7`` (hermético, sin PG ni red).

Fija las dos piezas de las que depende el veredicto de la batería:

* **Identidad de BD** — un nombre compartido (``bolsa_v1``) produce motivo; un nombre
  dedicado (``*_a7`` o ``LIVE_A7_DB_NAME``) no. ``LIVE_A7_ALLOW_SHARED_DB=1`` relaja.
* **Semántica del veredicto** — sin motivo no hace nada; con motivo y sin gate hace
  ``skip`` accionable; con ``LIVE_A7_PG_REQUIRED=1`` falla duro.

Más los predicados puros: dueño de lease de la propia suite vs ajeno (``live-a7-*``) y la
sonda TCP del stack dev (positivo con un socket REAL escuchando, negativo con uno que no
escucha). Nada de esto abre PostgreSQL, así que este fichero no se auto-salta cuando la
guarda salta el resto del paquete.
"""

from __future__ import annotations

import socket

import _exclusivity_guard as guard
import pytest

# ---------------------------------------------------------------------------
# Identidad de la BD
# ---------------------------------------------------------------------------


def test_database_name_reads_the_database_from_both_dsn_forms() -> None:
    assert (
        guard.database_name("postgresql://bolsa:bolsa_dev@localhost:5432/bolsa_v1?schema=public")
        == "bolsa_v1"
    )
    assert (
        guard.database_name("postgresql+psycopg://bolsa:bolsa_dev@localhost:5432/bolsa_v1_a7")
        == "bolsa_v1_a7"
    )
    assert guard.database_name(None) is None
    assert guard.database_name("   ") is None


def test_dedicated_name_is_the_a7_suffix_or_the_declared_one(monkeypatch) -> None:
    monkeypatch.delenv("LIVE_A7_DB_NAME", raising=False)
    assert guard.is_dedicated_database_name("bolsa_v1_a7") is True
    assert guard.is_dedicated_database_name("bolsa_v1") is False
    assert guard.is_dedicated_database_name(None) is False
    # El nombre declarado manda sobre el sufijo (una BD dedicada puede llamarse distinto).
    monkeypatch.setenv("LIVE_A7_DB_NAME", "bolsa_v1_scratch")
    assert guard.is_dedicated_database_name("bolsa_v1_scratch") is True
    assert guard.is_dedicated_database_name("bolsa_v1_a7") is False


def test_a_shared_database_name_is_a_reason_and_a_dedicated_one_is_not(monkeypatch) -> None:
    monkeypatch.delenv("LIVE_A7_ALLOW_SHARED_DB", raising=False)
    monkeypatch.delenv("LIVE_A7_DB_NAME", raising=False)

    shared = guard.shared_db_reason("postgresql://bolsa:bolsa_dev@localhost:5432/bolsa_v1")
    assert shared is not None
    assert "bolsa_v1" in shared
    assert "_a7" in shared  # nombra la BD dedicada que el job a7-gate usa

    assert guard.shared_db_reason("postgresql://bolsa:bolsa_dev@localhost:5432/bolsa_v1_a7") is None
    # Sin DATABASE_URL no se inventa un veredicto verde.
    assert guard.shared_db_reason(None) is not None


def test_the_explicit_override_releases_only_the_database_name_criterion(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_A7_ALLOW_SHARED_DB", "1")
    assert guard.shared_db_reason("postgresql://u:p@localhost:5432/bolsa_v1") is None


# ---------------------------------------------------------------------------
# Evidencia de contención por lease
# ---------------------------------------------------------------------------


def test_only_this_suite_workers_are_recognised_as_own() -> None:
    assert guard.is_test_worker("live-a7-c3a-ab12cd") is True
    assert guard.is_foreign_worker("live-a7-c3a-ab12cd") is False
    # El recovery del stack dev se identifica como ``live-recovery-<pid>``.
    assert guard.is_foreign_worker("live-recovery-4242") is True
    # Un dueño vacío NO es evidencia de un worker ajeno (no se inventa contención).
    assert guard.is_foreign_worker(None) is False
    assert guard.is_foreign_worker("") is False


class _FakeResult:
    def __init__(self, rows: list[tuple[str, str | None, object]]) -> None:
        self._rows = rows

    def all(self) -> list[tuple[str, str | None, object]]:
        return self._rows


class _FakeSession:
    """Sesión mínima que solo satisface ``execute(...).all()`` (sin PG)."""

    def __init__(self, rows: list[tuple[str, str | None, object]]) -> None:
        self._rows = rows

    async def execute(self, _stmt: object) -> _FakeResult:
        return _FakeResult(self._rows)

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _FakeFactory:
    def __init__(self, rows: list[tuple[str, str | None, object]]) -> None:
        self._rows = rows

    def __call__(self) -> _FakeSession:
        return _FakeSession(self._rows)


async def test_a_foreign_fresh_claim_is_reported_as_contention() -> None:
    reason = await guard.foreign_claim_reason(
        _FakeFactory([("c3a-deadbeef", "live-recovery-4242", None)])
    )
    assert reason is not None
    assert "worker ajeno" in reason
    assert "live-recovery-4242" in reason  # nombra al consumidor real
    assert "c3a-deadbeef" in reason  # y la fila que se le adelantó


async def test_this_suite_workers_do_not_count_as_contention() -> None:
    assert (
        await guard.foreign_claim_reason(
            _FakeFactory([("c3a-deadbeef", "live-a7-c3a-ab12cd", None)])
        )
        is None
    )


async def test_an_unreadable_claim_query_is_not_turned_into_a_skip() -> None:
    class _BrokenFactory:
        def __call__(self) -> object:
            raise RuntimeError("sin conexión")

    # No poder verificar NO se convierte en evidencia de contención: el escenario
    # diagnosticará con su propio lease en vez de saltarse en silencio.
    assert await guard.foreign_claim_reason(_BrokenFactory()) is None


# ---------------------------------------------------------------------------
# Sonda del stack dev (TCP real, loopback, sin servicios del proyecto)
# ---------------------------------------------------------------------------


def test_probe_ports_reports_listening_ports_and_ignores_closed_ones() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    silent = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listening_port = listener.getsockname()[1]
        # Bound pero SIN listen (y sin backlog): connect se rechaza de forma determinista.
        silent.bind(("127.0.0.1", 0))
        silent_port = silent.getsockname()[1]

        alive = guard.probe_ports((("vivo", listening_port), ("callado", silent_port)), timeout=0.5)
        assert alive == [f"vivo :{listening_port}"]
    finally:
        listener.close()
        silent.close()


# ---------------------------------------------------------------------------
# Veredicto: skip accionable en local, fallo duro con el gate del CI
# ---------------------------------------------------------------------------


def test_without_a_reason_the_verdict_does_nothing(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_A7_PG_REQUIRED", "1")
    guard.require_exclusive(None)  # no lanza: precondición cumplida


def test_a_reason_skips_with_an_actionable_message(monkeypatch) -> None:
    monkeypatch.delenv("LIVE_A7_PG_REQUIRED", raising=False)
    with pytest.raises(pytest.skip.Exception) as caught:
        guard.require_exclusive("DATABASE_URL apunta a 'bolsa_v1'")
    message = str(caught.value)
    assert "no exclusiva" in message
    assert "bolsa_v1_a7" in message  # el arreglo concreto
    assert "LIVE_A7_ALLOW_SHARED_DB=1" in message  # la salida explícita
    assert "scheduler_worker" in message  # el consumidor real de la fila
    assert "NO certifica" in message  # un verde con skips no es el veredicto del sello
    assert "LIVE_A7_PG_REQUIRED=1" in message  # el gate que lo convierte en fallo


def test_with_the_ci_gate_a_broken_precondition_fails_hard(monkeypatch) -> None:
    monkeypatch.setenv("LIVE_A7_PG_REQUIRED", "1")
    with pytest.raises(AssertionError) as caught:
        guard.require_exclusive("DATABASE_URL apunta a 'bolsa_v1'")
    assert "live_a7 C3 required but" in str(caught.value)
