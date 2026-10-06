"""A8 · M0 — invariant estructural: AUTO nunca construye/referencia el broker LIVE real.

Regla P0 congelada: ``AUTO → SIMULATED ONLY`` · ``AUTO → NEVER REAL LIVE``.

El barricada no depende de recordar "no llamar a XtbBrokerAdapter": se blinda por
estructura. Los únicos productores en el paquete que pueden abrir la vía real
(``resolve_broker_adapter``/``XtbBrokerAdapter.submit`` → POST bridge) son módulos
de CONFIRM humano (``confirm_recommendation``, ``fill_pending_order``) y la propia
definición del puerto (``broker_adapter``). Ninguna ruta AUTO del árbol puede
importar esos símbolos; si algún día alguien cablea un broker en un worker AUTO
AUTO, este test lo impide en CI.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_PKG = Path(__file__).resolve().parents[1] / "src" / "bolsa_application"
_REPO = Path(__file__).resolve().parents[4]
_WORKER = (
    _REPO
    / "apps"
    / "api-python"
    / "src"
    / "bolsa_api"
    / "background"
    / "auto_simulation_worker.py"
)
_BROKER_MODULE = "bolsa_application.broker_adapter"
# Símbolos de la vía real (money). Ningún módulo AUTO puede importarlos/referirlos.
_MONEY_SYMBOLS = {"IBrokerAdapter", "resolve_broker_adapter", "XtbBrokerAdapter"}

# Módulos AUTO/decisión (no deben poder abrir la vía real).
_AUTO_MODULES = [
    "execution_router.py",                # spine AUTO (paper_auto / live_auto dry-run)
    "execute_position_policy_auto.py",    # protect/reduce/exit AUTO
    "paper_desk_cycle.py",                # ciclo PAPER Entry + Position
    "paper_desk_entry.py",                # EntryTick PAPER
    "paper_d_propose.py",                 # Paper-D proposal/execute (mode=paper_auto)
    "position_exit_evaluator.py",         # evaluador de salida full_auto
    "execute_gated_portfolio_trade.py",   # trade HTTP paper-only
    "lifecycle_from_auto.py",             # lifecycle AUTO write
    "paper_daily_report.py",              # reporte diario PAPER (read-only)
    "evaluate_exit_plan.py",              # plan de salida
]

# (ruta, nombre que sale en el fallo). El worker vive fuera de bolsa_application.
_AUTO_PATHS: list[tuple[Path, str]] = [(_PKG / name, name) for name in _AUTO_MODULES]
_AUTO_PATHS.append((_WORKER, "auto_simulation_worker.py"))


def _imported_money_symbols(tree: ast.AST) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith(_BROKER_MODULE):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in _MONEY_SYMBOLS:
                        found.add(name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(_BROKER_MODULE):
                    found.add("(module import of broker_adapter)")
    # Referencias por atributo (p. ej. broker_adapter.resolve_broker_adapter(...)).
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if node.attr in _MONEY_SYMBOLS:
                found.add(f"attribute:{node.attr}")
    return found


@pytest.mark.parametrize(
    ("path", "module_name"),
    _AUTO_PATHS,
    ids=[name for _, name in _AUTO_PATHS],
)
def test_auto_module_never_references_live_broker_money_path(
    path: Path, module_name: str
) -> None:
    if not path.exists():
        pytest.skip(f"módulo {module_name} no presente")
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    found = _imported_money_symbols(tree)
    assert not found, (
        f"{module_name} referencia símbolos de la vía LIVE real: {sorted(found)}. "
        "AUTO es SIMULATED ONLY (regla P0 A8)."
    )


def test_auto_spine_execution_router_has_no_broker_adapter_dependency() -> None:
    """Doble-negación en el corazón AUTO: ExecutionRouter no inyecta ningún adapter."""
    path = _PKG / "execution_router.py"
    source = path.read_text(encoding="utf-8")
    assert "resolve_broker_adapter" not in source
    assert "XtbBrokerAdapter" not in source
    assert "IBrokerAdapter" not in source
