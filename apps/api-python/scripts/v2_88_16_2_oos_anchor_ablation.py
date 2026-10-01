"""V2.88.16.2 · ``W3.2`` — ABLACIÓN del ancla temporal sobre el artefacto OOS del replay.

Por qué existe
--------------
``W3`` (v2.88.16) movió **dos** cosas del tiempo del motor, y el ``replay-repro`` del tag
salió **rojo**: el artefacto OOS congelado (``A4DA036C…``, el sello de ``v2.88.7``) dejó de
reproducirse porque el replay conduce el ``AutoSimulationWorker`` **real** y ese worker es
justo el que ``W3`` cambió. El rediseño del artefacto es **legítimo**, pero el dossier de
``W3`` no lo declaraba, y un cambio que **ensancha** la muestra al **quitar** lookahead es
exactamente lo que no se firma sin explicar: quitar información no debería mejorar nada.

Esta sonda **aísla la causa** sin narración: corre el MISMO replay tres veces, cada una con
un solo movimiento de ``W3`` desactivado, reutilizando los fragmentos **ya auditados** de la
matriz de mutaciones (``v2_44_mutation_audit.py``), que además restaura el árbol byte a byte:

===== ====================================================== ==========================
Variante Desactivación                                          Qué mide
===== ====================================================== ==========================
`w3`  ninguna (árbol tal cual)                                 la referencia
`m280`  ``seed`` vuelve al MINUTO del bucle                     el ancla del fill
`m279`  la frontera devuelve el día de la barra EN CURSO        el no-lookahead (``B-1``)
===== ====================================================== ==========================

Lectura: si con `m280` el artefacto vuelve al sello, la causa era el **seed**; si es con
`m279`, era la **frontera**; si **ninguna** lo devuelve, el ensanche es del **anclaje de
identidad/ejecución** y hay que seguir por ``M281``/``M282``.

Declarado vs medido
-------------------
Las cifras declaradas viven en ``_DECLARED``. La sonda las **compara** y sale con código
``2`` si no cuadran: si el delta no se reproduce, el sello de ``W3.2`` **no se firma**.

Uso::

    uv run --no-sync python apps/api-python/scripts/v2_88_16_2_oos_anchor_ablation.py \\
        --out-dir operability_runs/w32-ablation

Requiere PostgreSQL con la entrada congelada sembrada (``replay_oos_input_fixture.py seed``)
y ``DATABASE_URL`` apuntando a ESA base: el replay es read-only, pero lee barras reales.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_MUTATIONS = _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_44_mutation_audit.py"
_FIXTURE = _REPO_ROOT / "docs" / "engineering" / "evidence" / "v2.88.7" / "replay-input-fixture.ndjson"
_REPLAY = _REPO_ROOT / "apps" / "api-python" / "scripts" / "v2_87_replay_oos_durable_cycle.py"
_WATCH_TOOL = _REPO_ROOT / "apps" / "api-python" / "scripts" / "replay_oos_input_fixture.py"

#: Variante → (mutación de la matriz, o ``None`` para el árbol tal cual) y su control de VIVACIDAD.
#:
#: ``M280`` = seed por MINUTO (el ancla de fill de antes de ``W3``); ``M279`` = frontera con
#: LOOKAHEAD (el día de la barra en curso). ``M279b`` es el **control decisivo**: si la frontera
#: fuera de verdad por el camino del replay, devolver un día de **2099** metería años de barras
#: futuras en la señal, el régimen y el ATR. Un artefacto idéntico bajo ``M279b`` **prueba** que
#: ``last_closed_bar_day`` no se consume en esta configuración (no que «un día dé igual»).
_VARIANTS: tuple[tuple[str, str | None], ...] = (
    ("w3", None),
    ("m280_seed_minuto", "M280"),
    ("m279_frontera_lookahead", "M279"),
    ("m279b_frontera_futuro", "M279b"),
)

#: Mutaciones propias de esta sonda (no están en la matriz porque no inyectan un defecto: son el
#: CONTROL de que ``last_closed_bar_day`` está —o no— en el camino del replay).
_LOCAL_MUTATIONS: dict[str, dict[str, str]] = {
    "M279b": {
        "rel": "packages/py/application/src/bolsa_application/closed_bars.py",
        "old": "    start = parse_bar_timestamp(window[0])\n"
        "    return (start - timedelta(seconds=1)).strftime(\"%Y-%m-%d\")\n",
        "new": "    start = parse_bar_timestamp(window[0])\n    return \"2099-01-01\"\n",
        "label": "M279b (CONTROL de vivacidad): la frontera devuelve un dia de 2099 -> si "
        "last_closed_bar_day alimentara la decision, entrarian anos de barras FUTURAS",
    }
}

#: Sello ``v2.88.7`` (el artefacto que el job ``replay-repro`` congela), tal como quedó
#: **documentado** en ``docs/engineering/evidence/v2.88.7/README.md`` §5. No se re-deriva aquí
#: —haría falta el árbol de ``v2.88.15``— y NO se declara nada que su evidencia no publique
#: (el sello no publicó ``byYear`` ni ``positiveShare``: no se inventan).
_SEAL: dict[str, Any] = {
    "totals": {"decided": 24500, "fills": 752, "orders": 210, "proposals": 238, "vetoes": 24303},
    "daysWithFills": 141,
    "realizedCount": 62,
    "realizedRTotal": -18.365980744109294,
    "sha256_lf": "A4DA036C9AC198EAF88037EBB5D66D0A76CEA95141E03B046CECE1BCBC5B13CB",
}

#: MEDIDO por esta sonda (2026-09-30). Si no coincide, exit ``2``.
_DECLARED: dict[str, dict[str, Any]] = {
    "w3": {
        "totals": {"decided": 24500, "fills": 923, "orders": 247, "proposals": 285, "vetoes": 24264},
        "daysWithFills": 163,
        "realizedCount": 79,
        "realizedRTotal": -15.53352380521819,
        "byYear": {"2022": 53, "2023": 6, "2024": 5, "2025": 8, "2026": 7},
        "sha256_lf": "1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7",
    },
    "m280_seed_minuto": {
        "totals": {"decided": 24500, "fills": 752, "orders": 210, "proposals": 238, "vetoes": 24303},
        "daysWithFills": 141,
        "realizedCount": 62,
        "realizedRTotal": -18.365980744109294,
        "sha256_lf": "A4DA036C9AC198EAF88037EBB5D66D0A76CEA95141E03B046CECE1BCBC5B13CB",
    },
    "m279_frontera_lookahead": {
        # MEDIDO: INERTE en el replay (byte a byte igual al árbol tal cual). No es un fallo: el
        # replay inyecta sus fuentes sobre `cursor.as_of`, que YA es `B-1` por construcción.
        "totals": {"decided": 24500, "fills": 923, "orders": 247, "proposals": 285, "vetoes": 24264},
        "daysWithFills": 163,
        "realizedCount": 79,
        "realizedRTotal": -15.53352380521819,
        "byYear": {"2022": 53, "2023": 6, "2024": 5, "2025": 8, "2026": 7},
        "sha256_lf": "1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7",
    },
    "m279b_frontera_futuro": {
        # CONTROL de vivacidad: una frontera de 2099 metería años de barras FUTURAS si el motor
        # consultara `last_closed_bar_day` en este camino. Idéntico ⇒ NO se consulta.
        "totals": {"decided": 24500, "fills": 923, "orders": 247, "proposals": 285, "vetoes": 24264},
        "daysWithFills": 163,
        "realizedCount": 79,
        "realizedRTotal": -15.53352380521819,
        "byYear": {"2022": 53, "2023": 6, "2024": 5, "2025": 8, "2026": 7},
        "sha256_lf": "1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7",
    },
}


def _load_mutations() -> Any:
    spec = importlib.util.spec_from_file_location("v2_44_mutation_audit", _MUTATIONS)
    if spec is None or spec.loader is None:  # pragma: no cover — el fichero vive al lado.
        raise RuntimeError(f"no se pudo cargar {_MUTATIONS}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _playbook() -> str:
    """Watch congelado del manifiesto (una sola fuente de verdad: no se repite aquí)."""
    out = subprocess.run(
        [sys.executable, str(_WATCH_TOOL), "watch", "--fixture", str(_FIXTURE)],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    return out.stdout.strip()


def _run_replay(watch: str, out_path: pathlib.Path, database_url: str) -> None:
    env = {**os.environ, "DATABASE_URL": database_url, "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run(
        [
            sys.executable,
            str(_REPLAY),
            "--json",
            "--watch",
            watch,
            "--out",
            str(out_path),
        ],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=1800,
        env=env,
    )
    if result.returncode != 0 or not out_path.is_file():
        raise RuntimeError(
            f"el replay no produjo artefacto (exit {result.returncode}):\n"
            f"{(result.stdout or '')[-2000:]}\n{(result.stderr or '')[-2000:]}"
        )


def _measure(path: pathlib.Path) -> dict[str, Any]:
    import hashlib

    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    score = payload["replay"]["score"]
    return {
        "totals": payload["replay"]["totals"],
        "daysWithFills": payload["replay"]["daysWithFills"],
        "realizedCount": score["realizedCount"],
        "realizedRTotal": score["realizedRTotal"],
        "meanR": score["meanR"],
        "positiveShare": score.get("positiveShare"),
        "openPositions": len(score.get("openPositions") or []),
        "byYear": {y: v["count"] for y, v in sorted((score.get("byYear") or {}).items())},
        "sha256_lf": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest().upper(),
    }


def _variant(mutations: Any, label: str, mutation_id: str | None) -> dict[str, Any]:  # noqa: C901
    if mutation_id is None:
        return {}
    local = _LOCAL_MUTATIONS.get(mutation_id)
    if local is not None:
        return dict(local)
    for entry in mutations.MUTATIONS:
        if str(entry[0]).upper().startswith(mutation_id):
            return {
                "rel": entry[1],
                "old": entry[2],
                "new": entry[3],
                "label": entry[0],
            }
    raise RuntimeError(f"la matriz no tiene la mutacion {mutation_id} (¿deriva del codigo?)")


def _pct(share: Any) -> str:
    return "n/d" if share is None else f"{float(share) * 100:.1f}%"


def _print_table(report: dict[str, dict[str, Any]]) -> None:
    print("\n== ablación del ancla temporal sobre el artefacto OOS ==")
    print(f"{'variante':<26} {'ciclos':>7} {'R total':>11} {'signo +':>8} {'fills':>6} "
          f"{'orders':>6} {'días':>5}  LF sha256 (12)  por año")
    print("-" * 128)
    by_year = _SEAL.get("byYear")
    print(f"{'SELLO v2.88.7':<26} {_SEAL['realizedCount']:>7} {_SEAL['realizedRTotal']:>11.4f} "
          f"{'n/d':>8} {_SEAL['totals']['fills']:>6} {_SEAL['totals']['orders']:>6} "
          f"{_SEAL['daysWithFills']:>5}  {_SEAL['sha256_lf'][:12].lower():<15} "
          f"{json.dumps(by_year) if by_year else '(no publicado)'}")
    for label, data in report.items():
        print(f"{label:<26} {data['realizedCount']:>7} {data['realizedRTotal']:>11.4f} "
              f"{_pct(data['positiveShare']):>8} {data['totals']['fills']:>6} "
              f"{data['totals']['orders']:>6} {data['daysWithFills']:>5}  "
              f"{data['sha256_lf'][:12].lower():<15} {json.dumps(data['byYear'])}")


def _check(report: dict[str, dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    for label, declared in _DECLARED.items():
        if not declared:
            problems.append(f"{label}: SIN DECLARAR (medido: {json.dumps(report[label])})")
            continue
        for key, expected in declared.items():
            observed = report[label][key]
            if observed != expected:
                problems.append(f"{label}.{key}: declarado {expected!r} != medido {observed!r}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="operability_runs/w32-ablation")
    parser.add_argument(
        "--database-url",
        default=os.environ.get(
            "DATABASE_URL", "postgresql://bolsa:bolsa_dev@localhost:5432/bolsa_v1_replay_w32"
        ),
    )
    parser.add_argument("--observe", action="store_true", help="mide y publica, sin comparar")
    parser.add_argument(
        "--only", default="", help="rótulos separados por coma (medir solo esos)"
    )
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="reutiliza los artefactos ya presentes en --out-dir (re-valida sin re-correr)",
    )
    args = parser.parse_args(argv)

    out_dir = (_REPO_ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    mutations = _load_mutations()
    only = {token.strip() for token in args.only.split(",") if token.strip()}
    variants = [v for v in _VARIANTS if not only or v[0] in only]
    if only and not variants:
        print("!! ningún rótulo casa con --only:", args.only)
        return 1
    watch = _playbook()
    print(f"watch congelado: {len(watch.split(','))} símbolos · db: {args.database_url}")

    report: dict[str, dict[str, Any]] = {}
    for label, mutation_id in variants:
        variant = _variant(mutations, label, mutation_id)
        rel = variant.get("rel")
        out_path = out_dir / f"{label}.json"
        if args.reuse and out_path.is_file():
            report[label] = _measure(out_path)
            print(f"\n### {label}  (reutilizado de {out_path.name})")
            print(f"    {json.dumps(report[label]['totals'])} · ciclos "
                  f"{report[label]['realizedCount']} · R {report[label]['realizedRTotal']}")
            continue
        original = (_REPO_ROOT / rel).read_text(encoding="utf-8") if rel else ""
        restored = True
        try:
            if rel:
                hits = original.count(variant["old"])
                if hits != 1:
                    print(f"!! {variant['label']}: el fragmento aparece {hits} veces; ABORTO")
                    return 1
                payload = original.replace(variant["old"], variant["new"], 1).encode("utf-8")
                if not mutations._apply(_REPO_ROOT / rel, payload):  # noqa: SLF001 — sonda
                    print(f"!! {variant['label']}: no se pudo escribir la mutación; ABORTO")
                    return 1
                mutations._drop_bytecode((rel,))  # noqa: SLF001
                live = (_REPO_ROOT / rel).read_text(encoding="utf-8")
                if live.count(variant["new"]) != 1:  # control de vivacidad del EDIT
                    print(f"!! {variant['label']}: la mutación no está en el fichero; ABORTO")
                    return 1
                print(f"\n### {variant['label']}  (mutando {rel}, edit vivo)")
            else:
                print(f"\n### {label}  (árbol tal cual)")
            _run_replay(watch, out_path, args.database_url)
            report[label] = _measure(out_path)
            print(f"    {json.dumps(report[label]['totals'])} · ciclos "
                  f"{report[label]['realizedCount']} · R {report[label]['realizedRTotal']} · "
                  f"LF {report[label]['sha256_lf'][:12].lower()}")
        finally:
            if rel:
                restored = mutations._restore(  # noqa: SLF001
                    _REPO_ROOT / rel, rel, original
                )
                mutations._drop_bytecode((rel,))  # noqa: SLF001
        if not restored:
            print(f"!! {rel} NO se restauró byte a byte; ABORTO (árbol en riesgo)")
            return 1

    _print_table(report)
    if args.observe:
        print("\nVEREDICTO  modo --observe: medido y publicado, sin comparar")
        return 0

    problems = _check(report)
    if problems:
        print("\nVEREDICTO  NO REPRODUCIDO")
        for problem in problems:
            print(f"  - {problem}")
        return 2
    print("\nVEREDICTO  DEFINIDO=MEDIDO (la ablación aísla la causa declarada)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
