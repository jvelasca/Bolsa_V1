"""V2.88.16.3 · ``W3.3`` — ROBUSTEZ DEL INSTRUMENTO OOS: la BANDA de ``K`` sorteos del venue.

Por qué existe
--------------
El artefacto OOS del replay es **reproducible byte a byte**, y eso se confundió con
«el resultado es una propiedad del motor». **No lo es.** La ablación de ``W3.2`` lo probó:
cambiar **sólo** el ancla del ``seed`` del fill mueve el artefacto de ``62`` a ``79`` ciclos
y de ``R −18.3660`` a ``R −15.5335``, con restauración byte a byte. Es decir: el replay
**es un sorteo del venue**, y citar un punto sin su banda es citar un dado como si fuera
una constante.

Qué hace esta sonda
-------------------
Expone la **realización del venue** como una **entrada declarada** del instrumento: el
sorteo ``k`` usa ``fill_seed(bar_tick + k, símbolo)`` en vez del ``fill_seed(bar_tick, …)``
de producción (``auto_simulation_worker.py``, **única fuente** de la derivación). Es un
**único** desplazamiento del ancla temporal, inyectado en el árbol y restaurado byte a byte
(``Δ src = 0`` al terminar): **no** se toca la señal, ni el régimen, ni el riesgo, ni la
liquidación, ni el ``base_mid`` de ``W4``.

``k = 0`` **es** la realización de producción ⇒ el sorteo 0 **no se parchea** y tiene que
reproducir el sello del tag **byte a byte**. Es el autochequeo del instrumento: si el sorteo
0 no es el sello, la sonda está midiendo otra cosa.

Qué publica
-----------
* La **BANDA** del instrumento: mínimo / mediana / máximo de ciclos, R y signo positivo, y
  el reparto por año de cada sorteo.
* El **CRITERIO DE VALIDEZ**: cuánta dispersión tiene el instrumento. Si la banda es ancha
  para la magnitud del efecto que ``W4``/``W5`` quieren medir, el instrumento **no sirve
  para citar un punto** y hay que citar la banda (o reducir el ruido del venue). El criterio
  se declara aquí y la sonda lo **evalúa**, no lo narra.

Declarado vs medido
-------------------
Las cifras declaradas viven en ``_DECLARED`` y la banda en ``_BAND``. La sonda las
**compara** y sale con código ``2`` si no cuadran: si la banda no se reproduce, el sello de
``W3.3`` **no se firma**.

Uso::

    uv run --no-sync python apps/api-python/scripts/v2_88_16_3_oos_seed_robustness.py \\
        --out-dir operability_runs/w33-band

Requiere PostgreSQL con la entrada congelada sembrada (``replay_oos_input_fixture.py seed``)
y ``DATABASE_URL`` apuntando a ESA base: el replay es read-only, pero lee barras reales.
"""

from __future__ import annotations

import argparse
import hashlib
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

#: El sorteo del venue, en su ÚNICA fuente (``auto_simulation_worker.py``): el ancla temporal
#: del ``seed`` del book SIM. La sonda la desplaza por sorteo y la restaura byte a byte.
_WORKER_REL = "apps/api-python/src/bolsa_api/background/auto_simulation_worker.py"
_SEED_LINE = "                seed=fill_seed(bar_tick_now, symbol),\n"

#: Sorteos declarados: ``k = 0`` es la realización de PRODUCCIÓN (sin parchear) y ``k >= 1``
#: son re-sorteos del mismo dato y la misma estrategia. ``K`` = ``--draws``.
_DEFAULT_DRAWS = 12

#: Sello del tag vigente (``v2.88.16.2``): el sorteo 0 tiene que salir EXACTAMENTE así.
_SEAL: dict[str, Any] = {
    "realizedCount": 79,
    "realizedRTotal": -15.53352380521819,
    "totals": {"decided": 24500, "fills": 923, "orders": 247, "proposals": 285, "vetoes": 24264},
    "daysWithFills": 163,
    "sha256_lf": "1E3ADAC26543FC7BFC7DA4CAA8733D3B24937A0E3E0E78650DC059FA929A37E7",
}

#: MEDIDO por esta sonda (2026-10-01) — sorteo a sorteo. Si no coincide, exit ``2``.
#:
#: Se declara el ``sha256_lf`` de cada sorteo (fija el artefacto **byte a byte**, y con él el
#: reparto por año) MÁS las métricas que se citan. ``k00`` **es** el sello del tag: la sonda
#: no lo «comprueba por parecido», lo compara contra el mismo valor.
_DECLARED: dict[str, dict[str, Any]] = {
    "k00": {
        "sha256_lf": _SEAL["sha256_lf"],
        "realizedCount": 79,
        "realizedRTotal": -15.53352380521819,
        "daysWithFills": 163,
        "positiveShare": 0.43037974683544306,
        "totals": {"decided": 24500, "fills": 923, "orders": 247, "proposals": 285, "vetoes": 24264},
    },
    "k01": {
        "sha256_lf": "CD59FEB83D64BDDF499CBF69DF58A9C44383CB3ED6CACEFA38E2789F41537D6A",
        "realizedCount": 84,
        "realizedRTotal": -8.705202464081399,
        "daysWithFills": 179,
        "positiveShare": 0.4642857142857143,
        "totals": {"decided": 24500, "fills": 992, "orders": 267, "proposals": 306, "vetoes": 24242},
    },
    "k02": {
        "sha256_lf": "7891A0327F9DD93C205172C44854BEF7C456FAF39A72279C2879ECD3E1D595AF",
        "realizedCount": 66,
        "realizedRTotal": -4.4819805078043045,
        "daysWithFills": 148,
        "positiveShare": 0.48484848484848486,
        "totals": {"decided": 24500, "fills": 817, "orders": 220, "proposals": 253, "vetoes": 24290},
    },
    "k03": {
        "sha256_lf": "1001E0D1D0DA84A4AF03F974964CAEFD5A7AE7A898EF2D889E346B7231715751",
        "realizedCount": 70,
        "realizedRTotal": -9.939179921103952,
        "daysWithFills": 156,
        "positiveShare": 0.44285714285714284,
        "totals": {"decided": 24500, "fills": 855, "orders": 233, "proposals": 262, "vetoes": 24280},
    },
    "k04": {
        "sha256_lf": "F6F65AFC8A43C7D88C32F8317A339DBBEF57B4262D2E5E5EBDDCBE5BEC1EC2D8",
        "realizedCount": 59,
        "realizedRTotal": -15.11831345883083,
        "daysWithFills": 130,
        "positiveShare": 0.423728813559322,
        "totals": {"decided": 24500, "fills": 720, "orders": 197, "proposals": 220, "vetoes": 24315},
    },
    "k05": {
        "sha256_lf": "C034436454884824238E9A2C41C9E07466DABC67E047D0D37F874752FE3B460D",
        "realizedCount": 107,
        "realizedRTotal": -17.265511636390233,
        "daysWithFills": 208,
        "positiveShare": 0.4205607476635514,
        "totals": {"decided": 24500, "fills": 1252, "orders": 336, "proposals": 373, "vetoes": 24187},
    },
    "k06": {
        "sha256_lf": "5B4C7A29FE9CF5409F5E1AAC6F1A9F4EBDC08E39849A252727E43842F22942D8",
        "realizedCount": 47,
        "realizedRTotal": -10.214173277433972,
        "daysWithFills": 100,
        "positiveShare": 0.40425531914893614,
        "totals": {"decided": 24500, "fills": 601, "orders": 164, "proposals": 181, "vetoes": 24344},
    },
    "k07": {
        "sha256_lf": "E44D86B63B1A4C845F08D0EA12FD57462E8F5344E56004FBA967316FE1D2DF59",
        "realizedCount": 53,
        "realizedRTotal": -1.3902363202833927,
        "daysWithFills": 121,
        "positiveShare": 0.4339622641509434,
        "totals": {"decided": 24500, "fills": 680, "orders": 189, "proposals": 211, "vetoes": 24323},
    },
    "k08": {
        "sha256_lf": "314980A17C936E4A11D9F71363D423DD4D1237D2D369C9FD8DF2EFF560D7C5B9",
        "realizedCount": 73,
        "realizedRTotal": -37.72438124763515,
        "daysWithFills": 143,
        "positiveShare": 0.2876712328767123,
        "totals": {"decided": 24500, "fills": 806, "orders": 218, "proposals": 244, "vetoes": 24294},
    },
    "k09": {
        "sha256_lf": "DC7B128CF264CFD8573A8D34B5F865BACC7D4AC0CC57D02135E22F80207A5529",
        "realizedCount": 82,
        "realizedRTotal": 0.8182464577270899,
        "daysWithFills": 190,
        "positiveShare": 0.47560975609756095,
        "totals": {"decided": 24500, "fills": 1034, "orders": 283, "proposals": 319, "vetoes": 24242},
    },
    "k10": {
        "sha256_lf": "522EE3DDF7686D70EEC3A56E6FEB411FEA68E5C5D331658DB27E06E4A41F7CA6",
        "realizedCount": 43,
        "realizedRTotal": -25.37500469509636,
        "daysWithFills": 76,
        "positiveShare": 0.27906976744186046,
        "totals": {"decided": 24500, "fills": 516, "orders": 141, "proposals": 153, "vetoes": 24364},
    },
    "k11": {
        "sha256_lf": "D9C97343717BF0467B38C1B22791A1BA369FDDB209B765B50966235173E49C9A",
        "realizedCount": 88,
        "realizedRTotal": -15.799936975779922,
        "daysWithFills": 169,
        "positiveShare": 0.45454545454545453,
        "totals": {"decided": 24500, "fills": 980, "orders": 270, "proposals": 302, "vetoes": 24246},
    },
}

#: BANDA declarada del instrumento (K = 12 sorteos), con su potencia y su criterio de validez.
#:
#: **La banda se cita ENTERA o no se cita.** Lo que enseña no es que el R sea negativo: es que
#: el **sorteo del venue mueve el resultado más que el efecto que el instrumento quería medir**
#: (``σ(R) = 10.14``, IC95 de la media ``±5.74``, y la banda **cruza el cero**). Por eso
#: ``point_citable = False``: con K = 1 el OOS **no tiene potencia** para distinguir la
#: estrategia del ruido del simulador.
_BAND: dict[str, Any] = {
    "draws": 12,
    "realizedCount": {
        "min": 43.0,
        "median": 71.5,
        "max": 107.0,
        "mean": 70.91666666666667,
        "stdev": 17.787909439341718,
    },
    "realizedRTotal": {
        "min": -37.72438124763515,
        "median": -12.6662433681324,
        "max": 0.8182464577270899,
        "mean": -13.394099820994219,
        "stdev": 10.138105364243431,
    },
    "fills": {
        "min": 516.0,
        "median": 836.0,
        "max": 1252.0,
        "mean": 848.0,
        "stdev": 195.83411347362338,
    },
    "positiveShare": {
        "min": 0.27906976744186046,
        "median": 0.4321710054931932,
        "max": 0.48484848484848486,
        "mean": 0.41681453702592713,
        "stdev": 0.06376395092622043,
    },
    "spread": {"realizedCount": 64.0, "realizedRTotal": 38.54262770536224},
    "power": {
        "se_mean_realizedRTotal": 2.9266189305593673,
        "ci95_half_width_realizedRTotal": 5.73617310389636,
        "se_mean_realizedCount": 5.134927151562313,
    },
    "validity": {"crosses_zero_r": True, "point_citable": False},
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
        [sys.executable, str(_REPLAY), "--json", "--watch", watch, "--out", str(out_path)],
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
        "byYear": {y: v["count"] for y, v in sorted((score.get("byYear") or {}).items())},
        "sha256_lf": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest().upper(),
    }


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _stats(values: list[float]) -> dict[str, float]:
    """Resumen declarado de una métrica sobre los K sorteos.

    Se publican **orden estadísticos** (``min``/``median``/``max``) y **momentos**
    (``mean``/``stdev``): los primeros no suponen forma; los segundos son los que permiten
    comparar la dispersión con la magnitud del efecto que se quiera medir (criterio de
    validez del instrumento). ``stdev`` es poblacional (los K sorteos SON la muestra).
    """
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    return {
        "min": min(values),
        "median": _median(values),
        "max": max(values),
        "mean": mean,
        "stdev": var**0.5,
    }


def _band(report: dict[str, dict[str, Any]]) -> dict[str, Any]:
    counts = [float(d["realizedCount"]) for d in report.values()]
    rs = [float(d["realizedRTotal"]) for d in report.values()]
    fills = [float(d["totals"]["fills"]) for d in report.values()]
    shares = [float(d["positiveShare"]) for d in report.values() if d["positiveShare"] is not None]
    band: dict[str, Any] = {
        "draws": len(report),
        "realizedCount": _stats(counts),
        "realizedRTotal": _stats(rs),
        "fills": _stats(fills),
    }
    if shares:
        band["positiveShare"] = _stats(shares)
    band["spread"] = {
        "realizedCount": max(counts) - min(counts),
        "realizedRTotal": max(rs) - min(rs),
    }
    # POTENCIA del instrumento: con K sorteos, la media de R solo se conoce con un error
    # estándar ``sigma/sqrt(K)``. Es la cifra que decide si el OOS puede **citar un punto**
    # o solo una **banda**: si el efecto que se quiere medir es del orden de ese error (o
    # menor), el instrumento NO tiene potencia para distinguirlo del sorteo.
    n = float(len(rs))
    se_r = band["realizedRTotal"]["stdev"] / n**0.5
    se_c = band["realizedCount"]["stdev"] / n**0.5
    band["power"] = {
        "se_mean_realizedRTotal": se_r,
        "ci95_half_width_realizedRTotal": 1.96 * se_r,
        "se_mean_realizedCount": se_c,
    }
    # CRITERIO DE VALIDEZ (evaluado, no narrado): un punto solo es citable si la banda de R
    # NO cruza el cero y la media no se come su propio error.
    mean_r = band["realizedRTotal"]["mean"]
    band["validity"] = {
        "crosses_zero_r": band["realizedRTotal"]["min"] < 0.0 < band["realizedRTotal"]["max"],
        "point_citable": (
            not (band["realizedRTotal"]["min"] < 0.0 < band["realizedRTotal"]["max"])
            and abs(mean_r) > 1.96 * se_r
        ),
    }
    return band


def _report_path(out_dir: pathlib.Path) -> pathlib.Path:
    return out_dir / "band.json"


def _draws(watch: str, out_dir: pathlib.Path, database_url: str, draws: int,
           reuse: bool, mutations: Any) -> dict[str, dict[str, Any]]:
    report: dict[str, dict[str, Any]] = {}
    worker = _REPO_ROOT / _WORKER_REL
    for k in range(draws):
        label = f"k{k:02d}"
        out_path = out_dir / f"{label}.json"
        if reuse and out_path.is_file():
            report[label] = _measure(out_path)
            print(f"\n### {label}  (reutilizado) · ciclos {report[label]['realizedCount']} · "
                  f"R {report[label]['realizedRTotal']}")
            continue
        original = ""
        restored = True
        try:
            if k > 0:
                original = worker.read_text(encoding="utf-8")
                hits = original.count(_SEED_LINE)
                if hits != 1:
                    print(f"!! el ancla del seed aparece {hits} veces en {_WORKER_REL}; ABORTO")
                    return report
                patched = original.replace(
                    _SEED_LINE,
                    f"                seed=fill_seed(bar_tick_now + {k}, symbol),\n",
                    1,
                ).encode("utf-8")
                if not mutations._apply(worker, patched):  # noqa: SLF001 — sonda
                    print(f"!! {label}: no se pudo escribir el sorteo; ABORTO")
                    return report
                mutations._drop_bytecode((_WORKER_REL,))  # noqa: SLF001
                live = worker.read_text(encoding="utf-8")
                if f"fill_seed(bar_tick_now + {k}, symbol)" not in live:  # vivacidad del EDIT
                    print(f"!! {label}: el desplazamiento no está en el fichero; ABORTO")
                    return report
                print(f"\n### {label}  (re-sorteo: seed=fill_seed(bar_tick_now + {k}, …))")
            else:
                print("\n### k00  (realización de PRODUCCIÓN, sin tocar el árbol)")
            _run_replay(watch, out_path, database_url)
            report[label] = _measure(out_path)
            print(f"    {json.dumps(report[label]['totals'])} · ciclos "
                  f"{report[label]['realizedCount']} · R {report[label]['realizedRTotal']} · "
                  f"LF {report[label]['sha256_lf'][:12].lower()}")
        finally:
            if k > 0:
                restored = mutations._restore(worker, _WORKER_REL, original)  # noqa: SLF001
                mutations._drop_bytecode((_WORKER_REL,))  # noqa: SLF001
        if not restored:
            print(f"!! {_WORKER_REL} NO se restauró byte a byte; ABORTO (árbol en riesgo)")
            return report
    return report


def _print(report: dict[str, dict[str, Any]], band: dict[str, Any]) -> None:
    print("\n== robustez del instrumento OOS: la banda de K sorteos del venue ==")
    print(f"{'sorteo':<8} {'ciclos':>7} {'R total':>11} {'signo +':>8} {'fills':>6} "
          f"{'orders':>6} {'días':>5}  LF sha256 (12)  por año")
    print("-" * 134)
    print(f"{'SELLO':<8} {_SEAL['realizedCount']:>7} {_SEAL['realizedRTotal']:>11.4f} "
          f"{'n/d':>8} {_SEAL['totals']['fills']:>6} {_SEAL['totals']['orders']:>6} "
          f"{_SEAL['daysWithFills']:>5}  {_SEAL['sha256_lf'][:12].lower():<15} (no publicado)")
    for label, data in report.items():
        share = data["positiveShare"]
        print(f"{label:<8} {data['realizedCount']:>7} {data['realizedRTotal']:>11.4f} "
              f"{(f'{float(share) * 100:.1f}%' if share is not None else 'n/d'):>8} "
              f"{data['totals']['fills']:>6} {data['totals']['orders']:>6} "
              f"{data['daysWithFills']:>5}  {data['sha256_lf'][:12].lower():<15} "
              f"{json.dumps(data['byYear'])}")
    if not band:
        return
    count, r = band["realizedCount"], band["realizedRTotal"]
    print(f"\nBANDA del instrumento (K = {band['draws']} sorteos):")
    print(f"  ciclos     media {count['mean']:.1f} ± {count['stdev']:.1f} · "
          f"min {count['min']:.0f} · mediana {count['median']:.0f} · max {count['max']:.0f} · "
          f"dispersión {band['spread']['realizedCount']:.0f}")
    print(f"  R total    media {r['mean']:.4f} ± {r['stdev']:.4f} · "
          f"min {r['min']:.4f} · mediana {r['median']:.4f} · max {r['max']:.4f} · "
          f"dispersión {band['spread']['realizedRTotal']:.4f}")
    print(f"  fills      media {band['fills']['mean']:.1f} ± {band['fills']['stdev']:.1f} · "
          f"min {band['fills']['min']:.0f} · max {band['fills']['max']:.0f}")
    if "positiveShare" in band:
        s = band["positiveShare"]
        print(f"  signo +    media {s['mean'] * 100:.1f}% ± {s['stdev'] * 100:.1f}% · "
              f"min {s['min'] * 100:.1f}% · max {s['max'] * 100:.1f}%")
    power = band.get("power") or {}
    if power:
        print(f"\nPOTENCIA: la media de R solo se conoce con SE = "
              f"{power['se_mean_realizedRTotal']:.4f} "
              f"(IC95 ±{power['ci95_half_width_realizedRTotal']:.4f}); "
              f"ciclos SE = {power['se_mean_realizedCount']:.2f}")
    validity = band.get("validity") or {}
    if validity:
        print(f"VALIDEZ: banda de R cruza el cero = {validity['crosses_zero_r']} ⇒ "
              f"punto citable = {validity['point_citable']}")


def _check(report: dict[str, dict[str, Any]], band: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for label, declared in _DECLARED.items():
        if label not in report:
            problems.append(f"{label}: declarado pero NO medido")
            continue
        for key, expected in declared.items():
            observed = report[label].get(key)
            if observed != expected:
                problems.append(f"{label}.{key}: declarado {expected!r} != medido {observed!r}")
    for key, expected in _BAND.items():
        observed = band.get(key)
        if observed != expected:
            problems.append(f"BANDA.{key}: declarado {expected!r} != medido {observed!r}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="operability_runs/w33-band")
    parser.add_argument("--draws", type=int, default=_DEFAULT_DRAWS)
    parser.add_argument(
        "--database-url",
        default=os.environ.get(
            "DATABASE_URL", "postgresql://bolsa:bolsa_dev@localhost:5432/bolsa_v1_replay_w32"
        ),
    )
    parser.add_argument("--observe", action="store_true", help="mide y publica, sin comparar")
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="reutiliza los artefactos ya presentes en --out-dir (re-valida sin re-correr)",
    )
    args = parser.parse_args(argv)

    out_dir = (_REPO_ROOT / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    mutations = _load_mutations()
    watch = _playbook()
    print(f"watch congelado: {len(watch.split(','))} símbolos · db: {args.database_url} · "
          f"K = {args.draws} sorteos")

    report = _draws(watch, out_dir, args.database_url, args.draws, args.reuse, mutations)
    if len(report) != args.draws:
        print("\nVEREDICTO  INCOMPLETO (la sonda no terminó los sorteos declarados)")
        return 1
    band = _band(report)
    report_path = _report_path(out_dir)
    payload = {"band": band, "draws": report, "seal": _SEAL}
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _print(report, band)

    if args.observe:
        print(f"\nVEREDICTO  modo --observe: band publicado en {report_path} (sin comparar)")
        return 0

    problems = _check(report, band)
    if problems:
        print("\nVEREDICTO  NO REPRODUCIDO")
        for problem in problems:
            print(f"  - {problem}")
        return 2
    print("\nVEREDICTO  BANDA DEFINIDA=MEDIDA (el instrumento declara su sorteo, no lo esconde)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
