"""AUTO-20B (V2.63) — completitud del volcado de material y passthrough del manifest (PURO).

Los dos casos que NO necesitan PostgreSQL y que sostienen el contrato del exportador:

* **Fail-closed de la paginación.** ``--limit`` ya no trunca en silencio: el exportador pagina
  las reservas por ``offset`` y solo declara completitud cuando una página trae menos de
  ``limit``. Si una página llena no aporta ids nuevos (el ``offset`` no avanza), la lectura NO
  puede afirmar completitud y el volcado se bloquea (``exit 2``) en vez de emitir un JSON sesgado.
* **Passthrough del manifest.** El ``material_manifest`` que el exportador publica en el JSON
  tiene que llegar al informe de calibración como bloque ``material`` (metadata de ENTRADA): no
  basta con que viaje en el fichero, el battery debe PROPAGARLO.

Hermético: sin PG, sin red, sin reloj real, sin broker. El E2E contra PostgreSQL real (misma
cadena, con oráculo independiente y test same-material) vive en
``test_auto_v63_auto20b_export_e2e_pg.py`` y se certifica en el job PG con gate fail-if-skipped.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

if sys.platform == "win32":  # psycopg async no soporta ProactorEventLoop.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "paper_cycles_export.py"
_BATTERY = Path(__file__).resolve().parents[3] / "scripts" / "research" / "auto_replay_battery.py"


def _load_exporter() -> Any:
    spec = importlib.util.spec_from_file_location("auto20b_paper_cycles_export", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── Fail-closed de la paginación ────────────────────────────────────────────────────


class _OffsetIgnoringStore:
    """Doble que SIEMPRE devuelve la misma página llena: simula un ``offset`` que no avanza."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows
        self.calls = 0

    async def list_by_cycle_ids(
        self, account_id: str | None, cycle_ids: Any, *, limit: int = 500, offset: int = 0
    ) -> list[Any]:
        self.calls += 1
        return list(self._rows[:limit])


class _HonestStore:
    """Doble que respeta ``offset``: paginación completa sin saturar."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    async def list_by_cycle_ids(
        self, account_id: str | None, cycle_ids: Any, *, limit: int = 500, offset: int = 0
    ) -> list[Any]:
        return list(self._rows[offset : offset + limit])


def _fake_reservation(reservation_id: str) -> Any:
    from types import SimpleNamespace

    return SimpleNamespace(reservation_id=reservation_id)


def test_a_page_that_never_advances_is_declared_as_saturated() -> None:
    """Fail-closed: una página llena sin ids nuevos ⇒ ``saturado=True`` (el exportador sale 2)."""
    module = _load_exporter()
    store = _OffsetIgnoringStore([_fake_reservation(f"RES-{i}") for i in range(4)])

    rows, saturated = asyncio.run(
        module._read_all_reservations(store, "acc", ["cyc"], page_size=4)
    )

    assert saturated is True
    assert len(rows) == 4, "se conserva lo leído, pero NO se declara completo"
    assert store.calls == 2, "parada en la primera página repetida, sin bucle infinito"


def test_pagination_reads_the_whole_universe_across_pages() -> None:
    """La paginación honesta recupera TODO; una página corta prueba la completitud."""
    module = _load_exporter()
    rows = [_fake_reservation(f"RES-{i}") for i in range(5)]

    read, saturated = asyncio.run(
        module._read_all_reservations(_HonestStore(rows), "acc", ["cyc"], page_size=2)
    )

    assert saturated is False
    assert [row.reservation_id for row in read] == [f"RES-{i}" for i in range(5)]


def test_an_exact_multiple_page_size_still_terminates_complete() -> None:
    """Si el total es múltiplo exacto de la página, la página vacía final prueba la completitud."""
    module = _load_exporter()
    rows = [_fake_reservation(f"RES-{i}") for i in range(4)]

    read, saturated = asyncio.run(
        module._read_all_reservations(_HonestStore(rows), "acc", ["cyc"], page_size=2)
    )

    assert saturated is False
    assert len(read) == 4


# ── Passthrough del manifest en el battery ──────────────────────────────────────────


def _load_battery() -> Any:
    spec = importlib.util.spec_from_file_location("auto20b_replay_battery", _BATTERY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_battery_propagates_the_exported_manifest_to_the_calibration_report(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """AUTO-20B: el ``material_manifest`` del JSON llega al informe como bloque ``material``.

    Es la segunda mitad del contrato del exportador: no basta con que el manifest viaje en el
    JSON; el battery tiene que PROPAGARLO como metadata de ENTRADA para que el informe pueda
    decir de qué universo salió. Si dejara de pasarlo, el informe volvería a no declarar nada.
    """
    battery = _load_battery()
    cycles = [
        {
            "cycleId": f"cyc-battery-{index}",
            "strategyVersion": "orb-a20b",
            "pnl": "1.0",
            "closedAt": f"2026-09-2{index}T10:00:00Z",
            "riskAmount": "0.5",
        }
        for index in range(1, 7)
    ]
    manifest = {
        "account": "acc-battery",
        "closedCycles": len(cycles),
        "cyclesWithRisk": len(cycles),
        "cyclesWithoutRisk": 0,
        "riskBasis": "reservation_reserved_risk",
        "fingerprint": "sha256:battery-material",
        "fingerprintMethod": "material_fingerprint_v1",
    }
    path = tmp_path / "material.json"
    path.write_text(
        json.dumps(
            {"note": "material REAL de prueba", "material_manifest": manifest, "cycles": cycles}
        ),
        encoding="utf-8",
    )

    code = battery.main(["--walk-forward", "--cycles", str(path), "--resamples", "50"])

    assert code == 0
    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert payload["material"] == manifest
    # La nota y la huella se DECLARAN por stderr (nunca dentro del informe JSON).
    assert "sha256:battery-material" in captured.err
    assert "material REAL de prueba" not in captured.out
