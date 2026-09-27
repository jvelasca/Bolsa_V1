#!/usr/bin/env python3
"""V2.83 · AUTO-MATERIAL-11 — AUTO WINDOW AUDIT (auditoría read-only de la ventana PAPER).

Qué resuelve: ``v2.81``/``v2.82`` dejaron la ventana ≥4 días como **operación del propietario** y el
capturador ``v2_80_market_window.py`` ya publica la serie diaria, el funnel, el ``unresolved_age`` y el
informe HTML. Esta herramienta añade la lectura **acumulada** que faltaba —la fila ``TOTAL`` y las
**tasas de operabilidad**— para poder auditar un ``operability_runs/`` ya producido y demostrar DÓNDE
funciona y DÓNDE se atasca el AUTO, en lugar de leer un ``0 cycles`` como un todo.

No decide nada: es **READ-ONLY** sobre un bundle YA generado. NO abre PostgreSQL, NO abre el motor, NO
recalcula el gate ni cambia un umbral, NO escribe ``evidence_runs/`` ni ``evidence_validations/`` ni el
journal durable. Sólo AGREGA (``bolsa_application.operability_audit``).

Uso (desde la raíz del repo; el bundle lo produce el runbook de la ventana)::

    # Auditar el bundle de la ventana (tabla D1..Dn + TOTAL + funnel + tasas + avisos):
    uv run --no-sync python apps/api-python/scripts/v2_83_window_audit.py \\
        --window operability_runs/operability-window.json --render

    # Sin evidencia en el bundle, `--forward` rellena SOLO los huecos declarados (orders/par A/B):
    uv run --no-sync python apps/api-python/scripts/v2_83_window_audit.py \\
        --window operability_runs/operability-window.json \\
        --forward 'operability_runs/forward-market-*.json' --render \\
        --out operability_runs/operability-audit.json

Códigos de salida: ``0`` si se leyó al menos un día; ``2`` si no hay material legible (se declara por
stderr) **o** si los argumentos son inválidos: ``argparse`` sale con ``2`` en el uso incorrecto, así que
el código NO distingue «sin material» de «uso incorrecto» — el mensaje de stderr sí lo hace.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WINDOW = _ROOT / "operability_runs" / "operability-window.json"
_DEFAULT_JOURNAL = _ROOT / "operability_runs" / "window.jsonl"


def _die(message: str, code: int = 2) -> int:
    print(f"# BLOQUEADO: {message}", file=sys.stderr)
    return code


def _resolve(path_text: str | None, default: Path) -> Path:
    path = Path(path_text) if path_text else default
    return path if path.is_absolute() else _ROOT / path


def _evidence_day(path: Path, evidence: dict[str, Any]) -> str:
    """Día declarado por la evidencia del runner (campo o nombre del fichero); nunca se adivina."""
    for field in ("day", "asOf", "date"):
        value = str(evidence.get(field) or "").strip()
        if value:
            return value[:10]
    digits = "".join(ch if ch.isdigit() else " " for ch in path.stem).split()
    for token in digits:
        if len(token) == 8:  # YYYYMMDD
            return f"{token[:4]}-{token[4:6]}-{token[6:]}"
    return ""


def _load_evidence(patterns: list[str]) -> dict[str, dict[str, Any]]:
    """Evidencia del runner por día (``--forward``, OPCIONAL y read-only). Sin día declarado, se omite."""
    by_day: dict[str, dict[str, Any]] = {}
    for pattern in patterns:
        for match in sorted(glob.glob(str(pattern), recursive=True)):
            path = Path(match)
            if not path.is_file():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                print(f"  !! evidencia ilegible {path}; se omite", file=sys.stderr)
                continue
            if not isinstance(payload, dict):
                continue
            day = _evidence_day(path, payload)
            if day:
                by_day.setdefault(day, payload)
    return by_day


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _load_rows(window_arg: str | None, journal_arg: str | None) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    """Lee las filas del bundle: la ventana JSON si existe (o si se pidió) y, si no, el journal JSONL."""
    window = _resolve(window_arg, _DEFAULT_WINDOW)
    if window.is_file():
        payload = json.loads(window.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            raw_rows = payload.get("rows")
            meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        elif isinstance(payload, list):
            raw_rows, meta = payload, {}
        else:
            raise ValueError(f"{window} no contiene una lista de filas legible")
        rows = [row for row in (raw_rows or []) if isinstance(row, dict)]
        return rows, meta, str(window)
    if window_arg:
        raise ValueError(f"no existe la ventana indicada: {window}")

    journal = _resolve(journal_arg, _DEFAULT_JOURNAL)
    if not journal.is_file():
        raise ValueError(f"no hay material que auditar: ni {window} ni {journal}")
    return _read_jsonl(journal), {}, str(journal)


def _render(rows: list[dict[str, Any]], meta: dict[str, Any], source: str) -> None:
    from bolsa_application.operability_audit import render_window_audit

    print(render_window_audit(rows, meta))
    print("")
    print(f"# fuente: {source}  (read-only: no se escribio nada en el journal durable)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--window",
        default=None,
        metavar="PATH",
        help="JSON de la ventana (por defecto operability_runs/operability-window.json)",
    )
    parser.add_argument(
        "--journal",
        default=None,
        metavar="PATH",
        help="journal JSONL acumulado (por defecto operability_runs/window.jsonl)",
    )
    parser.add_argument(
        "--forward",
        action="append",
        default=None,
        metavar="PATH|GLOB",
        help="JSON de evidencia del runner (repetible; admite glob). OPCIONAL y read-only: rellena "
        "SOLO los huecos declarados (orders/par A/B), nunca sobrescribe lo medido.",
    )
    parser.add_argument("--render", action="store_true", help="publica la auditoría legible")
    parser.add_argument("--json", action="store_true", help="emite la auditoría como JSON por stdout")
    parser.add_argument("--out", default=None, metavar="PATH", help="escribe la auditoría en este JSON")

    args = parser.parse_args(argv)

    try:
        rows, meta, source = _load_rows(args.window, args.journal)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return _die(f"no se pudo leer el material de la ventana ({type(error).__name__}: {error})")

    if not rows:
        return _die(f"no hay ningún día de operabilidad que auditar en {source}")

    from bolsa_application.operability_audit import (
        enrich_rows_with_evidence,
        window_audit,
        window_totals,
    )

    if args.forward:
        evidence_by_day = _load_evidence(list(args.forward))
        rows = enrich_rows_with_evidence(rows, evidence_by_day)

    audit = window_audit(rows)
    payload = {"meta": meta, "rows": rows, "audit": audit}

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=str))
    elif args.render:
        _render(rows, meta, source)

    if args.out:
        out_path = _resolve(args.out, _ROOT / "operability_runs" / "operability-audit.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )
        print(f"# auditoria json: {out_path}", file=sys.stderr)

    totals = window_totals(rows)
    coverage = totals["coverage"]
    partial = sorted(field for field, cover in coverage.items() if bool(cover.get("partial")))
    print(
        f"# auditado: {totals['daysTotal']} dia(s) ({totals['daysMeasured']} medidos)"
        f" · gate {audit['gate']['verdict']}"
        f" · {'campos partial: ' + ', '.join(partial) if partial else 'sin campos partial'}",
        file=sys.stderr,
    )
    for warning in audit["warnings"]:
        if str(warning.get("code")) in {"reason_contract", "pair_not_active"}:
            print(f"# AVISO {warning['code']}: {warning['message']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
