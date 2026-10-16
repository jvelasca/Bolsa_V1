"""Tripwire: la purga de residuos NO debe borrar la cuenta de la ventana PAPER (ADR-046).

Causa raíz medida (2026-10-16, con testigo controlado): el fixture autouse de sesión
``_cleanup_residuals_around_session`` borraba TODA cuenta con ``id <> 'default-account-seed'``,
incluida la de la ventana. Como ADR-046 exige que esa cuenta sobreviva ≥4 días de CALENDARIO,
cualquier ``pytest`` local sobre la BD compartida devolvía la ventana a ``0/4`` y ``v2_98`` a
``INCONCLUSIVE``: el bloqueador no era deriva, era determinista.

Este test fija las dos invariantes que impiden la recaída:

1. La identidad protegida sale de la FUENTE ÚNICA (``scripts/lib/window-forward.mjs``), no de un
   literal duplicado en Python: si alguien re-ancla la ventana a otra cuenta, este test lo exige
   de nuevo.
2. La regla de purga (``residual_targets``) respeta ese conjunto.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WINDOW_FORWARD_MJS = _REPO_ROOT / "scripts" / "lib" / "window-forward.mjs"
_CONFTEST_PY = Path(__file__).with_name("conftest.py")


def _load_conftest() -> ModuleType:
    """Carga ``conftest.py`` por ruta (los tests no viven en un paquete importable)."""
    spec = importlib.util.spec_from_file_location("_bolsa_tests_conftest", _CONFTEST_PY)
    assert spec is not None and spec.loader is not None, "no se pudo especificar conftest.py"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _window_account_from_js() -> str:
    """Id de la cuenta de la ventana tal como lo declara el runner JS (fuente única)."""
    source = _WINDOW_FORWARD_MJS.read_text(encoding="utf-8")
    start = source.find("export const WINDOW_CONFIG")
    assert start >= 0, "window-forward.mjs no declara `WINDOW_CONFIG`"
    match = re.search(r"\baccount:\s*'([^']+)'", source[start:])
    assert match is not None, "`WINDOW_CONFIG` no declara `account`"
    return match.group(1).strip()


def test_conftest_protects_the_window_account_from_the_single_source() -> None:
    """La purga protege la demo Y la cuenta de la ventana, con el id del JS (no duplicado)."""
    conftest = _load_conftest()
    window_account = _window_account_from_js()
    assert window_account, "el runner JS no aporta el id de la cuenta de la ventana"
    assert conftest.DEMO_ACCOUNT_ID in conftest.PROTECTED_ACCOUNT_IDS
    assert window_account in conftest.PROTECTED_ACCOUNT_IDS, (
        "conftest.PROTECTED_ACCOUNT_IDS no incluye la cuenta de la ventana: la purga la borraría"
    )


def test_residual_targets_never_returns_a_protected_id() -> None:
    """La regla de purga excluye lo protegido, deduplica y descarta ids vacíos."""
    conftest = _load_conftest()
    window_account = _window_account_from_js()
    all_ids = [
        "acc-test-a",
        conftest.DEMO_ACCOUNT_ID,
        window_account,
        str(conftest.DEMO_ACCOUNT_ID),
        "acc-test-a",
        "",
    ]
    targets = conftest.residual_targets(all_ids)  # type: ignore[arg-type]
    assert targets == ["acc-test-a"]
    assert not set(targets) & set(conftest.PROTECTED_ACCOUNT_IDS)
