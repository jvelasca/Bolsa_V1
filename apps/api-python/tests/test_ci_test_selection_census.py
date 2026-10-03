"""Guarda de CENSO de la selección de tests del CI (peaje ``OBS-19``).

Certifica la propiedad que `OBS-19` dejaba abierta: **ningún fichero de test puede existir
sin ejecutarse en algún job, ni sin estar declarado con motivo.** El agujero puede
ENCOGERSE; no puede crecer, ni en silencio.

Por qué es una guarda y no un `rg` sobre los workflows
-----------------------------------------------------
Un grep miente aquí: los jobs recogen por *directorios* y los `--ignore` recortan, así que
"el nombre aparece en el YAML" no equivale a "el fichero corre". Y al revés: un fichero
puede estar en el `--ignore` de un job dando por hecho que otro job lo lista, y que ese
otro job nunca lo liste —que es exactamente cómo `test_auth.py` llegó a no correr en
NINGÚN sitio, y cómo el certificador de AUTO-23 estuvo rojo sin que nadie lo ejecutara.

El censo se deriva con `scripts/ci/test_selection.py`, que expande los objetivos de cada
invocación y resta los `--ignore` del propio job. Su fidelidad está verificada contra el
oráculo real (`pytest --collect-only` con los mismos argumentos): mismo universo, mismo
conjunto ejecutado.

Qué falla (y por qué cada comprobación es falsable)
--------------------------------------------------
1. **Fichero nuevo invisible**: aparece un `test_*.py` que ningún job recoge y que no está
   en la línea base declarada ⇒ hay que cablearlo o declararlo con motivo.
2. **Declaración mentirosa**: una entrada de la línea base cuyo fichero YA corre ⇒ se
   regenera la línea base (la declaración no puede quedarse inflada).
3. **Motivo vacío**: ninguna entrada puede declarar sin motivo ni sin tanda.
4. **Censo ciego**: si el parser de invocaciones dejara de ver los workflows, el
   "ejecutado" se desplomaría y la comprobación 1 pasaría a ser vacua; por eso se anclan
   ficheros que se sabe que corren, incluido el certificador de AUTO-23 dado de alta en
   este mismo sello (regresión directa de este peaje).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
_SELECTION = _ROOT / "scripts" / "ci" / "test_selection.py"

#: Anclas del censo: ficheros que DEBEN aparecer como ejecutados. Sin ellas, un parser roto
#: haría que "ejecutado" fuese un conjunto pequeño y la comprobación de invisibles pasara
#: en falso (todos parecerían declarados).
_ANCHORS = (
    "packages/py/domain/tests/test_operative_granularity.py",
    "packages/py/application/tests/test_replay_oos.py",
    "apps/api-python/tests/test_auto_simulation_worker.py",
    "apps/api-python/tests/test_auto_v70_auto23_evidence_validation.py",
)


def _load_selection() -> Any:
    """Carga el módulo del censo. Se registra en ``sys.modules``: es lo correcto para
    ``spec_from_file_location`` y evita que las anotaciones del módulo se resuelvan a ciegas.
    """
    name = "ci_test_selection_under_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _SELECTION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _census() -> tuple[Any, dict[str, Any]]:
    module = _load_selection()
    return module, module.report()


def test_the_census_actually_sees_the_workflows() -> None:
    """Ancla: si el parser dejara de ver los workflows, el censo sería vacuo."""
    module, data = _census()
    invocations = module.invocations()
    assert len(invocations) >= 10, (
        f"sólo se han hallado {len(invocations)} invocaciones de pytest en los workflows: "
        "el censo no está leyendo el CI y sus comprobaciones no valdrían nada"
    )
    executed = set(data["executed"])
    for anchor in _ANCHORS:
        assert anchor in executed, (
            f"{anchor} debería ejecutarse en algún job y el censo no lo ve: "
            "o se ha caído del CI, o el parser de invocaciones está roto"
        )


def test_no_test_file_is_invisible_without_being_declared() -> None:
    """(1) La propiedad central: ningún test existe sin correr y sin declararse."""
    _module, data = _census()
    undeclared = data["undeclared"]
    assert undeclared == [], (
        f"hay {len(undeclared)} fichero(s) de test que NINGÚN job ejecuta y que tampoco "
        "están declarados en la línea base:\n  "
        + "\n  ".join(undeclared)
        + "\nCablea el fichero en un job (o en el pase de directorio que le toque) o "
        "decláralo con motivo y tanda en scripts/ci/ci-test-selection-baseline.json."
    )


def test_the_declared_baseline_does_not_lie() -> None:
    """(2) El agujero puede encogerse; la declaración no puede quedarse inflada."""
    _module, data = _census()
    stale = data["stale_baseline_entries"]
    assert stale == [], (
        f"hay {len(stale)} entrada(s) en la línea base cuyo fichero YA se ejecuta:\n  "
        + "\n  ".join(stale)
        + "\nRegenera la línea base: uv run --no-sync python "
        "scripts/ci/test_selection.py --write-baseline"
    )


def test_every_declared_entry_carries_a_reason_and_a_wave() -> None:
    """(3) Declarar no es esconder: cada entrada dice por qué y cuándo se cablea.

    Un baseline **vacío** es el estado META (``G2`` cerrado: ningún fichero de test existe
    sin ejecutarse), y no hay entradas que validar; la comprobación es vacuamente cierta.
    Mientras haya entradas, cada una debe llevar motivo y tanda.
    """
    module, _data = _census()
    entries = module.declared_baseline().get("entries", {})
    if not entries:
        return  # agujero cerrado: no queda ninguna declaración que auditar
    without_reason = [
        path
        for path, meta in entries.items()
        if not str(meta.get("reason", "")).strip() or not str(meta.get("wave", "")).strip()
    ]
    assert without_reason == [], (
        "entradas sin motivo o sin tanda (declarar sin motivo es esconder):\n  "
        + "\n  ".join(sorted(without_reason))
    )


def test_the_policy_is_zero_undeclared() -> None:
    """(4) La política declarada de la línea base es explícita, no implícita."""
    module, _data = _census()
    baseline = module.declared_baseline()
    assert int(baseline.get("maxUndeclared", -1)) == 0, (
        "la línea base debe declarar maxUndeclared=0: la política es que no haya ni un "
        "fichero de test invisible sin declarar"
    )
