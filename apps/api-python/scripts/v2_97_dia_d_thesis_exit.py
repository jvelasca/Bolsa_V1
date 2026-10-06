"""V2.97 · DÍA-D AUTO — QUIRÓFANO DEL ``THESIS_EXIT`` (read-only).

Qué es
------
El diagnóstico del origen de la pérdida (``v2_96``) aisló que el grueso del ``R`` bruto negativo
vive en pocos ciclos cerrados por invalidación de tesis (``THESIS_EXIT``), pese a que el
``STOP_EJECUTADO`` domina en frecuencia con expectancy bruta ~0. Esta sonda abre esos ciclos:
consume los ``K`` ledgers de ciclos que ``v2_94 --cycles --cycle-detail`` dejó por sorteo
(``draw-XX/multi-cycles.json``, esquema ``dia-d-multi-cycle-ledger-v7``) y los pliega para saber
**dónde viven** —estrategia, dirección, año/régimen, edad, geometría (MAE/MFE/captura), calidad de
entrada y coste— con su dispersión entre sorteos y su fragilidad. La capa v5 añade la
**desambiguación ``THESIS_EXIT`` vs ``STOP``**: por qué RUTA se invalidó la tesis (``ruta_mark`` vs
``ruta_mae`` sobre el MAE PERSISTIDO), el primer día en que el nivel se alcanzó y la huella del stop.
Con ``--sequences`` vuelca, además, la SECUENCIA día a día por ciclo (materia prima de la
reconstrucción temporal). La capa v6 añade la **correlación DECISIÓN↔CICLO**: una vez medido que el
mark tocó el stop vigente, lee del MISMO fotograma qué hizo el decider ese tick
(``decisionReasons``/``decisionLabel``) y si el toque se materializó (``filledQty``/``survived``),
clasificando cada toque en ``materializado``/``orden_creada_sin_fill``/``stop_evaluado_sin_orden``/
``stop_evaluado_sin_materializar``/``stop_no_evaluado``/``sin_toque``/``sin_traza``
(``decisionRoute``). La capa v7 SEPARA el caso A (``stop_evaluado_sin_orden``) del caso C
(``orden_creada_sin_fill``) leyendo la existencia del INTENT durable por ciclo (``orderCreated``);
``stop_evaluado_sin_materializar`` queda SÓLO como hueco no medido. Declara la frontera de la
secuencia (``D47-01``:
primer tick D1 completo POST-ENTRADA; el día de entrada no tiene fotograma).

No re-ejecuta el harness: sólo LEE los artefactos ya producidos.

Qué NO es (se declara, no se disfraza)
--------------------------------------
* **NO** sustituye la ventana PAPER: ``P3-2``/``P3-3`` siguen ABIERTAS.
* **NO** decide: descompone la muestra medida; **no** cambia motor ni umbrales.
* **NO** es causal: el motivo crudo es el token colapsado ``thesis_exit``, no la condición que lo
  disparó (recuperarla exigiría capturar el contexto del plan, que hoy no llega al journal).
* **Δ motor = 0:** no toca ningún fichero de motor; consume la costura inerte ya existente.
* Un hueco es ``None``/``NOT_MEASURED``; nunca se rellena con ``0``. El R neto sólo se afirma con
  fricción ``COMPLETE`` (con ``PARTIAL`` es un SUELO y se declara).

Uso::

    uv run --no-sync python apps/api-python/scripts/v2_97_dia_d_thesis_exit.py \\
        --out-dir operability_runs/dia-d-auto-band
"""

from __future__ import annotations

import argparse
import json
import logging
import pathlib
import sys
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]

#: Carpeta de artefactos (no versionada; mismos criterios que ``operability_runs/*``).
_OUT_SUBDIR = pathlib.Path("operability_runs") / "dia-d-auto"
_DRAWS_SUBDIR = pathlib.Path("operability_runs") / "dia-d-auto-band"

logger = logging.getLogger("v2_97_dia_d_thesis_exit")


def _draw_dirs(out_dir: pathlib.Path) -> list[pathlib.Path]:
    """Carpetas ``draw-XX`` presentes, en orden determinista (no se inventa ninguna)."""
    return sorted(path for path in out_dir.glob("draw-*") if path.is_dir())


def _load_ledgers(out_dir: pathlib.Path, *, limit: int | None) -> list[Any]:
    """Carga los ledgers de ciclos por sorteo (fail-closed si falta alguno)."""
    ledgers: list[Any] = []
    for directory in _draw_dirs(out_dir):
        if limit is not None and len(ledgers) >= limit:
            break
        cycles_path = directory / "multi-cycles.json"
        if not cycles_path.is_file():
            raise RuntimeError(
                f"{directory.name}: falta {cycles_path.name} "
                "(¿se corrió v2_94 con --cycles?); ABORTO"
            )
        ledgers.append(json.loads(cycles_path.read_text(encoding="utf-8")))
    if not ledgers:
        raise RuntimeError(f"no hay sorteos en {out_dir}; ABORTO")
    return ledgers


# ── Presentación (nunca un 0 inventado donde hay hueco) ──────────────────────────


def _fmt(value: Any, spec: str = "+.4f") -> str:
    """Formatea un número o ``n/d`` si es un hueco declarado (nunca un ``0`` inventado)."""
    return "n/d" if value is None else format(float(value), spec)


def _disp(value: Any, spec: str = "+.4f") -> str:
    """``mean [min, max]`` de una dispersión, o ``n/d`` sin muestra."""
    if not isinstance(value, dict):
        return "n/d"
    return f"{_fmt(value.get('mean'), spec)} [{_fmt(value.get('min'), spec)}, {_fmt(value.get('max'), spec)}]"


def _fold_line(label_key: str, block: dict[str, Any], width: int = 22) -> str:
    """Una línea de un cubo: etiqueta, ciclos, expectancy bruta, MAE/media y fragilidad."""
    gross = (block["realizedRGross"]["expectancyR"] or {})
    mae = (block["excursion"]["maeR"].get("mean") if block.get("excursion") else None)
    fragility = block["fragility"]
    return (
        f"{str(block[label_key]):<{width}} {block['drawsWithCell']:>2}/{block['drawsTotal']:<2} "
        f"n={block['cycles']:>3}  exp {_fmt(gross.get('mean'))}  "
        f"MAE {_fmt(mae)}  {','.join(fragility['reasons']) or '-'}"
    )


def _print_text(artifact: dict[str, Any]) -> None:
    coverage = artifact["coverage"]
    print()
    print(f"DÍA-D AUTO · QUIRÓFANO THESIS_EXIT · K = {artifact['draws']} sorteos")
    print("=" * 100)
    print(f"años pedidos              {coverage['yearsRequested']}")
    print(
        f"detalle capturado         {'sí' if coverage.get('detailCaptured') else 'NO'} · "
        f"ciclos THESIS_EXIT {coverage.get('cyclesTotal')} · con fricción COMPLETE "
        f"{coverage.get('cyclesWithCompleteFriction')}"
    )
    print()
    print("GLOBAL")
    print("-" * 100)
    print(_fold_line("label", artifact["global"]))
    for axis, label_key in (
        ("byStrategy", "strategy"),
        ("byDirection", "direction"),
        ("byYear", "year"),
        ("byRegime", "regime"),
        ("byOperationalRegime", "operationalRegime"),
        ("byAgeBucket", "ageBucket"),
    ):
        print()
        print(axis.upper())
        print("-" * 100)
        for block in artifact[axis]:
            print(_fold_line(label_key, block))
    disambiguation = (artifact["global"] or {}).get("disambiguation") or {}
    if disambiguation:
        print()
        print("DESAMBIGUACIÓN THESIS_EXIT vs STOP (capa v5)")
        print("-" * 100)
        print(f"ruta                      {disambiguation.get('route')}")
        print(f"ruta x MAE alcanzó nivel  {disambiguation.get('routeByMaeReached')}")
        candidate = disambiguation.get("structuralStopCandidate") or {}
        print(
            f"candidato a stop tocado   {candidate.get('count')} de {candidate.get('measured')} "
            f"({_fmt(candidate.get('share'), '.3f')})"
        )
        changed = disambiguation.get("stopChanged") or {}
        breakeven = disambiguation.get("breakevenReached") or {}
        print(
            f"stop cambió / break-even  {changed.get('count')} / {breakeven.get('count')} "
            f"(medidos {changed.get('measured')})"
        )
        first = disambiguation.get("daysToFirstTouch") or {}
        print(
            f"días hasta el primer toque media {_fmt(first.get('mean'), '.2f')} · "
            f"mediana {_fmt(first.get('median'), '.2f')} · medidos {first.get('measured')}"
        )
    correlation = (artifact["global"] or {}).get("decisionCorrelation") or {}
    if correlation:
        print()
        print("CORRELACIÓN DECISIÓN↔CICLO (capa v7: A/C separadas)")
        print("-" * 100)
        print(f"ruta de decisión          {correlation.get('route')}")
        print(f"ruta x stop candidato     {correlation.get('routeByStructuralStopCandidate')}")
        for key, label in (
            ("stopEvaluatedOnTouch", "stop evaluado en toque"),
            ("deciderRanOnTouch", "decider corrió en toque"),
            ("stopFiredNotFilled", "stop disparó sin fill"),
        ):
            block = correlation.get(key) or {}
            print(
                f"{label:<25} {block.get('count')} de {block.get('measured')} "
                f"({_fmt(block.get('share'), '.3f')})"
            )
        touch = correlation.get("stopTouchDays") or {}
        print(
            f"días con toque del stop   media {_fmt(touch.get('mean'), '.2f')} · "
            f"mediana {_fmt(touch.get('median'), '.2f')} · medidos {touch.get('measured')}"
        )
        print(f"frontera de la secuencia  {correlation.get('timelineStartsAt')}")
    print()
    print(f"motivos crudos            {artifact['rawReasonTokens']}")
    concentration = artifact["concentration"]
    print(
        f"concentración             símbolos {concentration['distinctSymbols']} · "
        f"top símbolo {concentration['topSymbol']} "
        f"({_fmt(concentration['topSymbolShare'], '.2f')}) · "
        f"top semana {concentration['topWeek']} "
        f"({_fmt(concentration['topWeekShare'], '.2f')})"
    )
    if artifact.get("limits"):
        print()
        print("LÍMITES DECLARADOS")
        for item in artifact["limits"]:
            print(f"  - {item}")


#: Campos de la desambiguación v5 que viajan al volcado de secuencias (identidad estable).
_DISAMBIGUATION_KEYS = (
    "cycleId",
    "symbol",
    "entryDay",
    "exitDay",
    "realizedR",
    "thesisExitRoute",
    "levelR",
    "markAtExitR",
    "minMarkR",
    "persistedMaeR",
    "persistedMaeAtExitR",
    "firstTouchDay",
    "markFirstTouchDay",
    "daysToFirstTouch",
    "touchBeforeExit",
    "stopChanged",
    "breakevenReached",
    "stopAboveLevel",
    "structuralStopCandidate",
    # Capa v6/v7 (DÍA-D-3g/3h): correlación decisión↔ciclo + existencia de orden (A/C separadas).
    "decisionRoute",
    "stopTouchDays",
    "stopEvaluatedOnTouch",
    "deciderRanOnTouch",
    "stopFiredNotFilled",
    "timelineStartsAt",
)


def _build_sequences_payload(ledgers: list[Any]) -> dict[str, Any]:
    """Secuencia día a día de cada ``THESIS_EXIT`` (una fila por sorteo y ciclo).

    La unidad es el CICLO POR SORTEO: el MISMO ciclo aparece en los ``K`` sorteos del venue, así
    que el total es ``observaciones``, **no** ``K`` operaciones independientes. Se declara la
    identidad única (símbolo + entrada + salida) para que la distinción nunca se pierda.
    """
    records: list[dict[str, Any]] = []
    unique: set[tuple[str, str, str]] = set()
    per_draw: dict[str, int] = {}
    for draw_index, ledger in enumerate(ledgers):
        count = 0
        for row in ledger.get("cycles") or ():
            if str(row.get("exitMechanism") or "") != "THESIS_EXIT":
                continue
            unique.add(
                (
                    str(row.get("symbol") or ""),
                    str(row.get("entryDay") or ""),
                    str(row.get("exitDay") or ""),
                )
            )
            record = {key: row.get(key) for key in _DISAMBIGUATION_KEYS}
            record["draw"] = draw_index
            record["sequence"] = row.get("sequence")
            records.append(record)
            count += 1
        per_draw[str(draw_index)] = count
    return {
        "kind": "DIA_D_AUTO_THESIS_STOP_SEQUENCES",
        "schemaVersion": "dia-d-thesis-stop-sequences-v2",
        "readOnly": True,
        "basis": "entryDay",
        "mechanism": "THESIS_EXIT",
        "draws": len(ledgers),
        "thesisExitObservations": len(records),
        "uniqueCycleIdentities": len(unique),
        "cyclesPerDraw": per_draw,
        "limits": [
            "La unidad es el CICLO POR SORTEO: el mismo ciclo aparece en los K sorteos del venue; "
            "el total es OBSERVACIONES, no K operaciones financieras independientes.",
            "La secuencia es el estado CAPTURADO al inicio de cada tick (mark/stop vigente/MAE "
            "persistido); firstTouchDay es la fecha de la OBSERVACION, no el instante intrabar.",
            "Advisory read-only: no cambia el motor, los umbrales, TOP_N ni la allocation.",
        ],
        "records": records,
    }


def _use_utf8_console() -> None:
    """Fuerza UTF-8 en stdout/stderr: la salida lleva «↔» y acentos (consola cp1252 la rompería)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):  # pragma: no cover — consola real de Windows.
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        default=str(_DRAWS_SUBDIR),
        help="carpeta de los K sorteos de v2_94 (draw-XX/multi-cycles.json)",
    )
    parser.add_argument("--draws", type=int, default=None, help="tope de sorteos a leer (por defecto, todos)")
    parser.add_argument("--json", action="store_true", help="emite el artefacto como JSON")
    parser.add_argument("--out", default=None, help="ruta del JSON del quirófano")
    parser.add_argument(
        "--sequences",
        action="store_true",
        help="volca la secuencia día a día de cada THESIS_EXIT (capa v5) además del quirófano",
    )
    parser.add_argument(
        "--sequences-out",
        default=None,
        help="ruta del JSON de secuencias (por defecto, junto al quirófano)",
    )
    args = parser.parse_args(argv)

    _use_utf8_console()

    if args.draws is not None and int(args.draws) < 1:
        print("# uso incorrecto: --draws debe ser >= 1", file=sys.stderr)
        return 1

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")

    from bolsa_application.dia_d_thesis_exit import (
        DEFAULT_LIMITS,
        build_thesis_exit_artifact,
    )

    out_dir = pathlib.Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = _REPO_ROOT / out_dir

    try:
        ledgers = _load_ledgers(out_dir, limit=int(args.draws) if args.draws else None)
    except Exception as error:  # noqa: BLE001 — sin sorteos no hay evidencia: se DECLARA.
        print(f"# BLOQUEADO: no se pudo leer los sorteos ({type(error).__name__}: {error})", file=sys.stderr)
        return 2

    artifact = build_thesis_exit_artifact(
        draw_ledgers=ledgers,
        meta={
            "bump": "2.11.70-beta",
            "phase": "V2.97 DIA-D AUTO THESIS EXIT",
            "nature": "INVESTIGACION",
            "drawsDir": str(out_dir),
        },
        limits=list(DEFAULT_LIMITS),
    )

    payload = json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    years = (artifact.get("coverage") or {}).get("yearsRequested") or []
    first_year = str(years[0]) if years else "all"
    last_year = str(years[-1]) if years else "all"
    default_name = f"thesis-exit-{first_year}_{last_year}.json"
    out_path = pathlib.Path(args.out) if args.out else _REPO_ROOT / _OUT_SUBDIR / default_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(payload + "\n", encoding="utf-8")

    sequences_path: pathlib.Path | None = None
    if args.sequences:
        sequences = _build_sequences_payload(ledgers)
        sequences_payload = json.dumps(
            sequences, indent=2, sort_keys=True, ensure_ascii=False, default=str
        )
        if args.sequences_out:
            sequences_path = pathlib.Path(args.sequences_out)
        else:
            sequences_path = _REPO_ROOT / _OUT_SUBDIR / (
                f"thesis-stop-sequences-{first_year}_{last_year}.json"
            )
        sequences_path.parent.mkdir(parents=True, exist_ok=True)
        sequences_path.write_text(sequences_payload + "\n", encoding="utf-8")

    if args.json:
        print(payload)
    else:
        _print_text(artifact)
        print()
        print(f"quirófano                  {out_path}")
        if sequences_path is not None:
            print(f"secuencias                 {sequences_path}")
        print(f"sorteos leídos             {len(ledgers)} de {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
