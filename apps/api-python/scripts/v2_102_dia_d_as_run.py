"""V2.102 · DÍA-D retrospectivo **as-run** (ADR-049).

Qué es
------
El método DÍA-D existente (``v2_89``–``v2_97``) rejuega **el motor** desde un día pasado ``D``.
Este CLI rejuega **la operativa que realmente llevábamos**: parte del estado durable real en
``D`` (posiciones abiertas, stops, targets, engine) y lo deja correr hasta hoy, comparando lo
que de verdad pasó (brazo ``as_run``, con los fills durables) contra brazos contrafactuales:

* ``hold_structural`` — mantener hasta stop estructural o target.
* ``cash`` — no hacer nada.
* ``engine_params`` — el motor con los parámetros vigentes declarados.
* ``candidate`` — la candidata en evaluación, si el llamante la aporta.

Pregunta que responde: *«Si en D hubiéramos seguido exactamente la operativa que llevábamos,
¿qué habría pasado hasta hoy, y qué aportó o costó cada decisión?»*.

Qué NO es
---------
* **NO escribe en PostgreSQL**: sólo lee posiciones, fills y barras.
* **NO reconstruye el estado a ojo**: lo lee del ledger durable y declara la fuente.
* **NO rellena huecos con 0**: un brazo no medible se declara ``NOT_MEASURED`` con motivo.
* **NO promete rentabilidad**: mide la muestra. Con muestra insuficiente lo dice.

Uso::

    uv run --no-sync python apps/api-python/scripts/v2_102_dia_d_as_run.py \\
        --at 2026-09-30 --account-id <cuenta> --json --out operability_runs/dia-d-as-run/<cuenta>/as-run-2026-09-30.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import pathlib
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_DOTENV = _REPO_ROOT / ".env"

logger = logging.getLogger("v2_102_dia_d_as_run")

_PHASE = "V2.102 DIA-D AS-RUN"
_BUMP = "2.11.189-beta"


class _JsonlProgress:
    """Progreso observable para la UI (una línea JSON por fase). Best-effort."""

    def __init__(self, path: str | None, *, truncate: bool = True) -> None:
        self._path = pathlib.Path(path) if path else None
        self._start = time.monotonic()
        if self._path is not None and truncate:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self._path.unlink()
            except FileNotFoundError:
                pass

    def emit(self, phase: str, *, done: int = 0, total: int = 0, message: str | None = None) -> None:
        if self._path is None:
            return
        event = {
            "phase": phase,
            "done": int(done),
            "total": int(total),
            "message": message,
            "at": datetime.now(UTC).isoformat(),
            "elapsedSeconds": round(time.monotonic() - self._start, 2),
        }
        try:
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
                handle.flush()
        except OSError:  # pragma: no cover — progreso best-effort
            logger.debug("no se pudo escribir el progreso JSONL en %s", self._path)


def _day_bounds(day: str) -> tuple[datetime, datetime]:
    start = datetime.fromisoformat(f"{day}T00:00:00+00:00")
    return start, start + timedelta(days=1)


def _normalize_day(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.strip()[:10]).strftime("%Y-%m-%d")
    except ValueError:
        return None


# ── lecturas read-only del estado durable ───────────────────────────────────


async def _read_legs(
    factory: Any, *, account_id: str, day: str
) -> tuple[list[Any], str, list[str]]:
    """Lee las posiciones vivas en ``D`` del ledger durable.

    Prioriza ``sim_auto_positions`` (estado operativo del motor AUTO, por símbolo). Si no hay
    filas, cae a ``position_states`` (estado P1 por instrumento). La fuente se declara y las
    aproximaciones se listan en ``limits``.
    """
    from sqlalchemy import select

    from bolsa_application.dia_d_as_run import AsRunLeg
    from bolsa_infrastructure.database.models.tables import (
        PositionStateRow,
        SimAutoPositionRow,
    )

    _start, end = _day_bounds(day)
    limits: list[str] = []
    async with factory() as session:
        sim_rows = (
            await session.execute(
                select(SimAutoPositionRow)
                .where(
                    SimAutoPositionRow.account_id == account_id,
                    SimAutoPositionRow.quantity > 0,
                    SimAutoPositionRow.opened_at < end,
                )
                .order_by(SimAutoPositionRow.symbol.asc())
            )
        ).scalars().all()

        if sim_rows:
            legs: list[AsRunLeg] = []
            for row in sim_rows:
                plan = row.position_state if isinstance(row.position_state, dict) else {}
                entry = _num(row.entry_price) or _num(row.avg_price) or _num(plan.get("actualEntry"))
                stop = _num(row.stop_price) or _num(plan.get("currentStop")) or _num(plan.get("initialStop"))
                target1 = _num(plan.get("target1"))
                target2 = _num(plan.get("target2"))
                if entry is None:
                    limits.append(f"entry_not_measured:{row.symbol}")
                    continue
                legs.append(
                    AsRunLeg(
                        instrument_id=str(row.symbol),
                        direction=_direction(plan.get("direction")),
                        quantity=float(row.quantity),
                        entry=entry,
                        structural_stop=stop,
                        target1=target1,
                        target2=target2,
                    )
                )
            limits.append(
                "Estado inicial leído de sim_auto_positions con opened_at < D+1 y quantity > 0: "
                "no se conoce la fecha de cierre dentro de D, así que una posición cerrada ese "
                "mismo día puede aparecer como abierta (aproximación declarada)."
            )
            return legs, "sim_auto_positions", limits

        state_rows = (
            await session.execute(
                select(PositionStateRow)
                .where(
                    PositionStateRow.account_id == account_id,
                    PositionStateRow.status != "CLOSED",
                    PositionStateRow.created_at < end,
                )
                .order_by(PositionStateRow.instrument_id.asc())
            )
        ).scalars().all()

    legs = []
    for row in state_rows:
        plan = row.position_state if isinstance(row.position_state, dict) else {}
        entry = _num(row.actual_entry) or _num(plan.get("actualEntry"))
        stop = _num(row.current_stop) or _num(row.initial_stop) or _num(plan.get("currentStop"))
        quantity = _num(row.remaining_quantity) or _num(row.quantity)
        if entry is None or quantity is None:
            limits.append(f"state_not_measured:{row.instrument_id}")
            continue
        legs.append(
            AsRunLeg(
                instrument_id=str(row.instrument_id),
                direction=_direction(row.direction or plan.get("direction")),
                quantity=quantity,
                entry=entry,
                structural_stop=stop,
                target1=_num(plan.get("target1")),
                target2=_num(plan.get("target2")),
            )
        )
    if state_rows:
        limits.append(
            "Estado inicial leído de position_states con status <> CLOSED y created_at < D+1: "
            "una posición cerrada dentro de D puede aparecer como abierta (aproximación declarada)."
        )
    return legs, "position_states", limits


async def _read_fills(
    factory: Any, *, account_id: str, day: str, to_day: str
) -> tuple[list[Any], int]:
    """Fills durables estrictamente posteriores a ``D`` y hasta ``to_day`` inclusive."""
    from sqlalchemy import select

    from bolsa_application.dia_d_as_run import AsRunFill
    from bolsa_infrastructure.database.models.tables import SimFillFinanceContextRow

    start, _end = _day_bounds(day)
    _to_start, to_end = _day_bounds(to_day)
    async with factory() as session:
        rows = (
            await session.execute(
                select(
                    SimFillFinanceContextRow.created_at,
                    SimFillFinanceContextRow.instrument_id,
                    SimFillFinanceContextRow.side,
                    SimFillFinanceContextRow.quantity,
                    SimFillFinanceContextRow.price,
                )
                .where(
                    SimFillFinanceContextRow.account_id == account_id,
                    SimFillFinanceContextRow.created_at > start,
                    SimFillFinanceContextRow.created_at < to_end,
                )
                .order_by(SimFillFinanceContextRow.created_at.asc())
            )
        ).all()

    fills = [
        AsRunFill(
            timestamp=str(at.isoformat())[:10] if isinstance(at, datetime) else str(at)[:10],
            instrument_id=str(instrument_id),
            side=str(side).lower(),
            quantity=float(quantity),
            price=float(price),
        )
        for at, instrument_id, side, quantity, price in rows
    ]
    return fills, len(rows)


async def _read_bars(
    factory: Any, instruments: list[str], *, from_day: str, to_day: str
) -> dict[str, list[Any]]:
    """Barras D1 posteriores a ``from_day`` y hasta ``to_day`` por instrumento o símbolo."""
    from sqlalchemy import select

    from bolsa_domain.entities.ohlcv_bar import OhlcvBar
    from bolsa_infrastructure.database.models.tables import InstrumentRow, OhlcvBarRow

    if not instruments:
        return {}

    start, _end = _day_bounds(from_day)
    _to_start, to_end = _day_bounds(to_day)

    async with factory() as session:
        # Resolver instrumentos: la clave pedida puede ser el id o el símbolo.
        catalog = (
            await session.execute(
                select(InstrumentRow.id, InstrumentRow.symbol).where(
                    (InstrumentRow.id.in_(instruments)) | (InstrumentRow.symbol.in_(instruments))
                )
            )
        ).all()
        id_by_key: dict[str, str] = {}
        for instrument_id, symbol in catalog:
            id_by_key[str(instrument_id)] = str(instrument_id)
            id_by_key[str(symbol)] = str(instrument_id)

        resolved_ids = sorted(set(id_by_key.get(key, key) for key in instruments))
        rows = (
            await session.execute(
                select(
                    OhlcvBarRow.instrument_id,
                    OhlcvBarRow.timestamp,
                    OhlcvBarRow.open,
                    OhlcvBarRow.high,
                    OhlcvBarRow.low,
                    OhlcvBarRow.close,
                    OhlcvBarRow.volume,
                )
                .where(
                    OhlcvBarRow.instrument_id.in_(resolved_ids),
                    OhlcvBarRow.timeframe == "1d",
                    OhlcvBarRow.timestamp > start,
                    OhlcvBarRow.timestamp < to_end,
                )
                .order_by(OhlcvBarRow.timestamp.asc())
            )
        ).all()

    by_id: dict[str, list[OhlcvBar]] = {}
    for instrument_id, timestamp, open_, high, low, close, volume in rows:
        key = str(instrument_id)
        by_id.setdefault(key, []).append(
            OhlcvBar(
                timestamp=str(timestamp.isoformat())[:10],
                open=float(open_),
                high=float(high),
                low=float(low),
                close=float(close),
                volume=int(volume),
            )
        )

    # Reindexar por la clave que usan las patas/fills (id o símbolo).
    result: dict[str, list[OhlcvBar]] = {}
    for key in instruments:
        resolved = id_by_key.get(key, key)
        result[key] = by_id.get(resolved, [])
    return result


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _direction(value: Any) -> str:
    return "short" if str(value or "").strip().lower() == "short" else "long"


def _atomic_write(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = pathlib.Path(handle.name)
    temp_path.replace(path)


def _seal(artifact: dict[str, Any]) -> dict[str, Any]:
    """Recalcula el hash sobre el artefacto COMPLETO (incluida su ``meta``)."""
    from bolsa_application.dia_d_as_run import artifact_hash

    body = {key: value for key, value in artifact.items() if key != "hash"}
    body["hash"] = artifact_hash(body)
    return body


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from dotenv import load_dotenv

    progress = _JsonlProgress(getattr(args, "progress_jsonl", None))
    progress.emit("starting", message=f"D={args.at}")

    load_dotenv(_DOTENV, override=False)
    from bolsa_application.dia_d_as_run import (
        AsRunExecutionModel,
        build_as_run_artifact,
        verify_bars_manifest,
    )
    from bolsa_application.dia_d_certification import certify_artifact
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine(settings)
    factory = create_session_factory(engine)

    try:
        day = _normalize_day(args.at)
        if day is None:
            raise RuntimeError(f"día inválido: {args.at!r}")
        to_day = _normalize_day(args.to) or datetime.now(UTC).strftime("%Y-%m-%d")
        if to_day < day:
            raise RuntimeError(f"el fin de ventana {to_day} es anterior al día D {day}")
        account_id = str(args.account_id or "").strip()
        if not account_id:
            raise RuntimeError("el método as-run requiere cuenta")

        candidate_as_of = _normalize_day(args.candidate_as_of)
        declared_universe = sorted(
            {
                item.strip()
                for item in (getattr(args, "universe_instrument", None) or [])
                if item and item.strip()
            }
        )

        progress.emit("reading_state", message="posiciones durables en D")
        legs, state_source, limits = await _read_legs(factory, account_id=account_id, day=day)

        progress.emit("reading_fills", done=len(legs))
        fills, fill_rows = await _read_fills(
            factory, account_id=account_id, day=day, to_day=to_day
        )

        instruments = sorted(
            {leg.instrument_id for leg in legs}
            | {fill.instrument_id for fill in fills}
            | set(declared_universe)
        )
        progress.emit("reading_bars", total=len(instruments))
        bars = await _read_bars(
            factory, instruments, from_day=day, to_day=to_day
        )
        progress.emit("reading_bars", done=len(bars), total=len(instruments), message="barras cargadas")

        # Modelo de ejecución declarado: si no se pasan componentes, ``cost_bps`` es el
        # round-trip y el deslizamiento queda en 0 (compatibilidad con la medición anterior).
        if any(
            value is not None
            for value in (args.commission_bps, args.slippage_bps, args.spread_bps)
        ):
            execution = AsRunExecutionModel(
                commission_bps=float(args.commission_bps or 0.0),
                slippage_bps=float(args.slippage_bps or 0.0),
                spread_bps=float(args.spread_bps or 0.0),
                max_participation_pct=args.max_participation_pct,
                gap_policy=args.gap_policy,
            )
        else:
            execution = AsRunExecutionModel(
                commission_bps=float(args.cost_bps) / 2.0,
                max_participation_pct=args.max_participation_pct,
                gap_policy=args.gap_policy,
            )

        limits.extend(
            [
                "Método DESCRIPTIVO, no causal: explica la muestra, no predice el futuro.",
                "El brazo as_run usa los fills durables de la ventana; sin venta emparejada el "
                "ciclo no se mide y se declara.",
                "Los brazos hold/candidate usan las barras D1 posteriores a D; un hueco de "
                "barras se declara por instrumento y nunca se rellena con 0.",
                "Un gap adverso se ejecuta al open real de la barra; el stop teórico solo se "
                "usa si la barra abre dentro del rango.",
                "La cota de liquidez puede diferir un cierre al open de la barra siguiente; si "
                "no hay barra que absorba la cantidad se declara liquidity_insufficient.",
            ]
        )
        if not declared_universe:
            limits.append(
                "Universo de D no declarado: se deriva de patas y barras cargadas, así que la "
                "certificación lo marca NOT_EVALUATED (declara --universe-instrument para "
                "acreditarlo)."
            )

        params = {
            "engineStopMultiplier": args.engine_stop_multiplier,
            "engineTargetMultiplier": args.engine_target_multiplier,
            "universe": str(args.universe),
            "execution": execution.to_dict(),
        }

        artifact = build_as_run_artifact(
            day=day,
            account_id=account_id,
            legs=legs,
            fills=fills,
            bars_by_instrument=bars,
            execution=execution,
            engine_stop_multiplier=args.engine_stop_multiplier,
            engine_target_multiplier=args.engine_target_multiplier,
            universe=str(args.universe),
            to_day=to_day,
            state_source=state_source,
            bars_source="postgres:ohlcv_bars",
            bars_timeframe="1d",
            strategy_version=args.strategy_version or None,
            mandate_version=args.mandate_version or None,
            params=params,
            bump=_BUMP,
            limits=limits,
            candidate_as_of=candidate_as_of,
            universe_instruments=declared_universe or None,
        )
        artifact["status"] = "measured" if artifact.get("measured") else "not_measured"
        if getattr(args, "verify_bars", False):
            # Auto-verificación del manifest: si la huella declarada no es la de las barras
            # leídas, el artefacto no se publica (mejor fallar que certificar una huella rota).
            mismatches = verify_bars_manifest(
                artifact["audit"]["data"]["barsManifest"], bars
            )
            if mismatches:
                raise RuntimeError(
                    "barsManifest no coincide con las barras leídas: " + ", ".join(mismatches)
                )
        artifact["meta"] = {
            "bump": _BUMP,
            "phase": _PHASE,
            "nature": "INVESTIGACION",
            "generatedAt": datetime.now(UTC).isoformat(),
            "day": day,
            "toDay": to_day,
            "account": account_id,
            "stateSource": state_source,
            "legs": len(legs),
            "fills": fill_rows,
            "instrumentsWithBars": sorted(key for key, rows in bars.items() if rows),
            "limits": limits,
        }
        artifact = _seal(artifact)
        # La certificación es una función pura del sobre de auditoría: se calcula al final y
        # se sella con el resto. No dice si el resultado es bueno; dice si el método es válido.
        artifact["certification"] = certify_artifact(artifact).to_dict()
        artifact = _seal(artifact)
        return artifact
    finally:
        await engine.dispose()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DÍA-D retrospectivo as-run (ADR-049): rejuega la operativa realmente ejecutada."
    )
    parser.add_argument("--at", required=True, help="Día D (YYYY-MM-DD)")
    parser.add_argument("--account-id", default="", help="Cuenta cuyo estado durable se rejuega")
    parser.add_argument("--to", default=None, help="Fin de ventana (por defecto, hoy)")
    parser.add_argument(
        "--cost-bps",
        type=float,
        default=32.0,
        help="Coste round-trip declarado en puntos básicos (32 bps por defecto)",
    )
    parser.add_argument(
        "--engine-stop-multiplier", type=float, default=None, help="Multiplicador ATR del stop vigente"
    )
    parser.add_argument(
        "--engine-target-multiplier", type=float, default=None, help="Multiplicador del target vigente"
    )
    parser.add_argument(
        "--commission-bps",
        type=float,
        default=None,
        help="Comisión por lado en bps (si se declara, manda sobre --cost-bps)",
    )
    parser.add_argument(
        "--slippage-bps", type=float, default=None, help="Deslizamiento por lado en bps"
    )
    parser.add_argument("--spread-bps", type=float, default=None, help="Spread por ida y vuelta en bps")
    parser.add_argument(
        "--max-participation-pct",
        type=float,
        default=0.10,
        help="Cota de participación sobre el volumen de la barra (0-1)",
    )
    parser.add_argument(
        "--gap-policy",
        default="open",
        choices=("open", "theoretical"),
        help="Ejecución de gaps: open real (por defecto) o precio teórico del stop",
    )
    parser.add_argument(
        "--candidate-as-of",
        default=None,
        help="Fecha point-in-time de la candidata (<= D). Sin ella no se mide la candidata.",
    )
    parser.add_argument("--strategy-version", default="", help="Versión de estrategia declarada")
    parser.add_argument("--mandate-version", default="", help="Versión de mandato declarada")
    parser.add_argument("--universe", default="watch", help="Etiqueta del universo rejugado")
    parser.add_argument(
        "--universe-instrument",
        action="append",
        default=[],
        help=(
            "Instrumento del universo DECLARADO de D (repetible). Sin esto el universo se "
            "deriva de patas y barras y la certificación lo marca NOT_EVALUATED."
        ),
    )
    parser.add_argument(
        "--verify-bars",
        action="store_true",
        help="Re-verifica barsManifest contra las barras leídas y aborta si no coincide",
    )
    parser.add_argument("--out", default="", help="Ruta del artefacto JSON")
    parser.add_argument("--progress-jsonl", default="", help="Ruta del JSONL de progreso")
    parser.add_argument("--json", action="store_true", help="Imprime el artefacto por stdout")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _parse_args(argv)
    try:
        artifact = asyncio.run(_run(args))
    except Exception as exc:  # noqa: BLE001 — CLI de evidencia: fallo explícito
        logger.error("DÍA-D as-run falló: %s", exc)
        return 1

    out = (args.out or "").strip()
    if out:
        _atomic_write(pathlib.Path(out), artifact)
    if args.json or not out:
        print(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
