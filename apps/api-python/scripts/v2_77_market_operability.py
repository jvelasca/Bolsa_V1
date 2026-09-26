#!/usr/bin/env python3
"""V2.77 · AUTO-MATERIAL-5 — AUTO MARKET OPERABILITY (journal diario del forward PAPER).

Qué resuelve: ``v2.76`` dejó el forward PAPER operando con **precio y régimen de MERCADO** y el
bloqueo localizado, pero el veredicto diario (¿por qué no hubo material?) vivía **disperso** en el
JSON de cada corrida. Esta herramienta lo convierte en una **serie diaria** y reparte cada veto en
su familia declarada, para responder sin sesgo a la pregunta que decide el siguiente paso:

    ¿la falta de material es ESTADÍSTICA o la causa ESTRUCTURALMENTE el gobernador / TOP_N?

No decide nada: lee el JSON que el runner ya produce (o el journal acumulado), CLASIFICA lo que el
motor ya declaró y publica la tabla. NO abre PostgreSQL, NO toca el material durable, NO recalcula
el gate y NO cambia un umbral. Escribe SOLO el journal de operabilidad (JSONL, directorio no
versionado): nunca ``evidence_runs/`` ni ``evidence_validations/``.

Uso (desde la raíz del repo)::

    # Tras una sesión de forward (el runner de v2.76 con --out):
    uv run --no-sync python apps/api-python/scripts/v2_77_market_operability.py \\
        --forward evidencia-forward-2026-09-28.json --render

    # Varios días de golpe (glob) + journal acumulado:
    uv run --no-sync python apps/api-python/scripts/v2_77_market_operability.py \\
        --forward 'operability_runs/forward-*.json' --render

    # Solo leer el journal ya acumulado (sin nuevos forward):
    uv run --no-sync python apps/api-python/scripts/v2_77_market_operability.py --render

Códigos de salida: ``0`` si se leyó al menos un registro; ``2`` si no hay ninguno que leer (se
declara por stderr); ``1`` uso incorrecto.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_JOURNAL = _REPO_ROOT / "operability_runs" / "journal.jsonl"

#: Nombre del fichero del journal (una fila JSON por forward/día).
_IDENTITY_FIELDS = ("day", "account", "versionA", "watchSize")


def _die(message: str, code: int = 2) -> int:
    print(f"# BLOQUEADO: {message}", file=sys.stderr)
    return code


def _expand(patterns: list[str]) -> list[Path]:
    """Expande cada patrón (glob) a ficheros existentes, sin duplicados y ordenado."""
    found: dict[str, Path] = {}
    for pattern in patterns:
        for match in sorted(glob.glob(str(pattern), recursive=True)):
            path = Path(match)
            if path.is_file():
                found[str(path.resolve())] = path
    return [found[key] for key in sorted(found)]


def _load_forward(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} no contiene un objeto JSON de evidencia")
    return payload


def _derive_day(path: Path, evidence: dict[str, Any], override: str | None) -> tuple[str, str]:
    """Día de la fila y su PROCEDENCIA declarada (nunca se inventa una fecha)."""
    if override:
        return str(override), "cli"
    for field in ("day", "asOf", "date"):
        value = str(evidence.get(field) or "").strip()
        if value:
            return value[:10], f"evidence.{field}"
    digits = "".join(ch if ch.isdigit() else " " for ch in path.stem).split()
    for token in digits:
        if len(token) == 8:  # YYYYMMDD
            return f"{token[:4]}-{token[4:6]}-{token[6:]}", "filename"
        if len(token) == 6:  # YYMMDD — ambiguo: se declara, no se adivina el siglo.
            return token, "filename(ambiguous)"
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    return mtime.date().isoformat(), "mtime"


def _identity(record: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(record.get(field) or "") for field in _IDENTITY_FIELDS)


def _read_journal(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                records.append(payload)
    return records


def _append_journal(path: Path, records: list[dict[str, Any]]) -> tuple[int, int]:
    """Añade las filas nuevas (por identidad) al journal. Devuelve ``(añadidas, ya presentes)``."""
    existing = {_identity(record) for record in _read_journal(path)}
    fresh = [record for record in records if _identity(record) not in existing]
    if not fresh:
        return 0, len(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        for record in fresh:
            handle.write(json.dumps(record, sort_keys=True, ensure_ascii=False, default=str) + "\n")
    return len(fresh), len(records) - len(fresh)


def _records_from_forwards(paths: list[Path], day_override: str | None) -> list[dict[str, Any]]:
    from bolsa_application.market_operability import build_operability_record

    records: list[dict[str, Any]] = []
    for path in paths:
        try:
            evidence = _load_forward(path)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            print(f"  !! {path} ilegible ({type(error).__name__}: {error}); se omite", file=sys.stderr)
            continue
        day, day_source = _derive_day(path, evidence, day_override)
        record = build_operability_record(evidence, day=day)
        record["daySource"] = day_source
        record["source"] = str(path)
        records.append(record)
    return records


def _render(records: list[dict[str, Any]]) -> None:
    from bolsa_application.market_operability import render_operability_table

    print("AUTO MARKET OPERABILITY (V2.77 · AUTO-MATERIAL-5) — read-only, sin PostgreSQL")
    print("=" * 92)
    print(render_operability_table(records))
    print("")
    print("Nota: un dia con vetos NO se lee como 'sin senal'; el PORQUE vive en las familias.")
    print("      pairCapable = arquitectura lista; pairActive = dos versiones operando.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--forward",
        action="append",
        default=None,
        metavar="PATH|GLOB",
        help="JSON de evidencia del runner forward (repetible; admite glob). Sin él solo se lee el journal.",
    )
    parser.add_argument(
        "--journal",
        default=str(_DEFAULT_JOURNAL),
        help="journal JSONL acumulado (por defecto operability_runs/journal.jsonl, no versionado)",
    )
    parser.add_argument("--day", default=None, help="fuerza el día de las filas nuevas (override)")
    parser.add_argument("--render", action="store_true", help="publica la tabla diaria y el desglose")
    parser.add_argument("--json", action="store_true", help="emite los registros como JSON")
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="no escribe el journal (dry-run: solo lee y renderiza)",
    )
    args = parser.parse_args(argv)

    journal_path = Path(args.journal)
    if not journal_path.is_absolute():
        journal_path = _REPO_ROOT / journal_path

    new_records: list[dict[str, Any]] = []
    if args.forward:
        paths = _expand(list(args.forward))
        if not paths:
            return _die(f"ningún fichero --forward casa con los patrones {args.forward!r}")
        new_records = _records_from_forwards(paths, args.day)

    added = skipped = 0
    if new_records and not args.no_write:
        added, skipped = _append_journal(journal_path, new_records)

    records = _read_journal(journal_path)
    if not records:
        return _die("no hay registros de operabilidad que leer (ni --forward ni journal acumulado)")
    records.sort(key=lambda record: (str(record.get("day") or ""), str(record.get("account") or "")))

    if args.json:
        print(json.dumps(records, indent=2, sort_keys=True, ensure_ascii=False, default=str))
    elif args.render:
        _render(records)

    if new_records:
        print(
            f"# journal: {added} fila(s) nueva(s), {skipped} ya presente(s) — {journal_path}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
