"""A8 · M0 — invariant estructural: AUTO nunca construye/referencia el broker LIVE real.

Regla P0 congelada: ``AUTO → SIMULATED ONLY`` · ``AUTO → NEVER REAL LIVE``.

El barricada no depende de recordar "no llamar a XtbBrokerAdapter": se blinda por
estructura. Los únicos módulos del paquete que pueden abrir la vía real
(``resolve_broker_adapter``/``XtbBrokerAdapter`` → POST bridge) son los de CONFIRM
humano y la propia definición del puerto (``broker_adapter``).

§7 (endurecimiento) — dos cambios sobre el invariante original:

1. **Lista derivada, no fija.** Ya no se mantiene a mano un censo de módulos AUTO.
   Se DERIVA del árbol real:
   * por convención de nombre (``*auto*``, ``paper_d*``) → conjunto AUTOMÁTICO, y
   * por ROL (spine AUTO sin marca en el nombre) → declarado y verificado presente.
   Además se aplica una **allowlist invertida**: barrido de TODO el paquete y de todo
   ``apps/*/src``; la vía real solo puede aparecer en los módulos permitidos. Un módulo
   nuevo (AUTO o no) que cablee el broker rompe en CI sin que nadie recuerde añadirlo.
2. **Doble-negación + ausencia de vía real en apps.** El spine ``execution_router`` no
   inyecta adapter, y NINGÚN módulo bajo ``apps/`` referencia la vía real.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_PKG = Path(__file__).resolve().parents[1] / "src" / "bolsa_application"
_REPO = Path(__file__).resolve().parents[4]
_APPS_SRC = _REPO / "apps"
_WORKER = (
    _REPO / "apps" / "api-python" / "src" / "bolsa_api" / "background" / "auto_simulation_worker.py"
)
_BROKER_MODULE = "bolsa_application.broker_adapter"
# Símbolos de la vía real (money).
_MONEY_SYMBOLS = {"IBrokerAdapter", "resolve_broker_adapter", "XtbBrokerAdapter"}

# ── Allowlist INVERTIDA (única enumeración manual) ────────────────────────────────
# Los ÚNICOS módulos que legítimamente pueden tocar la vía real. Todo lo demás —
# incluido cualquier módulo AUTO nuevo — la tiene prohibida. Añadir aquí algo exige
# una revisión humana explícita: es el punto de auditoría del invariante.
_ALLOWED_MONEY_MODULES: frozenset[str] = frozenset(
    {
        "broker_adapter.py",  # definición del puerto + XtbBrokerAdapter (POST)
        "fill_pending_order.py",  # CONFIRM humano (reconcile/recuperación)
        "confirm_recommendation.py",  # CONFIRM humano (aceptación explícita)
        "confirm/execution.py",  # CONFIRM humano (ejecución)
    }
)
# CONFIRM vive en el paquete: ningún módulo de aplicación puede alcanzar la vía real.
_ALLOWED_MONEY_APP_MODULES: frozenset[str] = frozenset()

# Convención (sub) de nombre que marca un módulo como AUTO/decisión.
_AUTO_NAME_TOKENS = ("auto", "paper_d")
# AUTO por ROL sin marca en el nombre. Se declaran y se exige que sigan presentes: si
# se renombran, el test rota y obliga a revisar el invariante (no se pierde en silencio).
_AUTO_BY_ROLE = (
    "execution_router.py",  # spine AUTO (paper_auto / live_auto dry-run)
    "position_exit_evaluator.py",  # evaluador de salida full_auto
    "execute_gated_portfolio_trade.py",  # trade HTTP paper-only
    "evaluate_exit_plan.py",  # plan de salida
)


def _imported_money_symbols(tree: ast.AST) -> set[str]:
    """Símbolos de la vía real importados/referenciados en un AST (imports + attrs)."""
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
        if isinstance(node, ast.Attribute) and node.attr in _MONEY_SYMBOLS:
            found.add(f"attribute:{node.attr}")
    # El verbo que MUEVE dinero en la vía real: cualquier ``X.submit(...)`` (así se
    # detecta también lo que llega por DI — un adapter inyectado como callable, p. ej.
    # ``confirm/execution.py``— sin nombrar el símbolo del puerto).
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "submit"
        ):
            found.add("call:.submit")
    return found


def _defined_money_symbols(tree: ast.AST) -> set[str]:
    """Símbolos de la vía real DEFINIDOS en el módulo (top-level class/def)."""
    out: set[str] = set()
    for node in getattr(tree, "body", []):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in _MONEY_SYMBOLS:
                out.add(node.name)
    return out


def _collect_modules(root: Path) -> dict[str, Path]:
    """Módulos ``.py`` bajo ``root`` → {ruta relativa posix: path} (derivado del árbol)."""
    return {path.relative_to(root).as_posix(): path for path in sorted(root.glob("**/*.py"))}


def _app_source_roots() -> dict[str, Path]:
    """Raíces ``src`` de cada app (evita escanear ``node_modules`` y demás)."""
    roots: dict[str, Path] = {}
    if not _APPS_SRC.is_dir():
        return roots
    for app in sorted(p for p in _APPS_SRC.iterdir() if p.is_dir()):
        src = app / "src"
        if src.is_dir():
            roots[app.name] = src
    return roots


def _reference_money(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return _imported_money_symbols(tree)


def _derive_auto_modules() -> dict[str, Path]:
    """AUTO por convención de nombre (derivado, sin censo manual)."""
    return {
        rel: path
        for rel, path in _collect_modules(_PKG).items()
        if any(tok in Path(rel).name.lower() for tok in _AUTO_NAME_TOKENS)
    }


def _auto_module_paths() -> list[tuple[Path, str]]:
    """Set efectivo AUTO = derivado por nombre ∪ por ROL (filtrado a lo existente)."""
    derived = _derive_auto_modules()
    out: list[tuple[Path, str]] = [(path, rel) for rel, path in sorted(derived.items())]
    for rel in _AUTO_BY_ROLE:
        if rel not in derived and (_PKG / rel).exists():
            out.append((_PKG / rel, rel))
    return out


# ── 1. Censo derivado + allowlist (auditoría) sobre TODO el paquete ───────────────
def test_reference_set_equals_allowlist() -> None:
    """El censo real de quien toca la vía real COINCIDE con la allowlist (derivado).

    No hay lista fija de módulos AUTO que mantener: se barre el árbol, se detecta todo
    módulo que importe/referencie el puerto **o llame a ``.submit``**, y se exige que
    coincida EXACTAMENTE con los módulos autorizados. Cualquier módulo nuevo —AUTO o
    no— que cablee el broker rompe aquí sin que nadie recuerde añadirlo.
    """
    referenced = {rel for rel, path in _collect_modules(_PKG).items() if _reference_money(path)}
    allowed = set(_ALLOWED_MONEY_MODULES)
    extra = sorted(referenced - allowed)
    assert not extra, (
        "Módulos NO autorizados tocan la vía LIVE real (AUTO es SIMULATED ONLY, regla "
        f"P0 A8): {extra}. Si de verdad es un CONFIRM humano, añádelo a "
        "_ALLOWED_MONEY_MODULES tras revisión humana (punto de auditoría)."
    )
    missing = sorted(allowed - referenced)
    assert not missing, (
        f"Allowlist obsoleta: {missing} ya no toca la vía real. Retíralos para que el "
        "invariante no dé permiso a lo que no lo necesita."
    )


def test_allowlist_modules_exist_and_port_is_still_defined() -> None:
    """La allowlist no apunta a humo y el puerto sigue definido con sus símbolos."""
    discovered = _collect_modules(_PKG)
    absent = sorted(rel for rel in _ALLOWED_MONEY_MODULES if rel not in discovered)
    assert not absent, f"Allowlist apunta a módulos inexistentes: {absent}"
    defined = _defined_money_symbols(
        ast.parse((_PKG / "broker_adapter.py").read_text(encoding="utf-8"))
    )
    assert defined == _MONEY_SYMBOLS, (
        "El puerto LIVE cambió de nombre/estructura: actualiza _MONEY_SYMBOLS y la "
        f"allowlist. Definidos={sorted(defined)}"
    )


# ── 2. Barrido de apps: nadie bajo apps/ abre la vía real ─────────────────────────
def test_no_app_module_references_live_money_path() -> None:
    roots = _app_source_roots()
    assert roots, "No se descubrió ninguna raíz apps/*/src — revisa el barrido."
    offenders: dict[str, list[str]] = {}
    for app_name, src in roots.items():
        for rel, path in _collect_modules(src).items():
            key = f"{app_name}/{rel}"
            hit = _reference_money(path)
            if hit and rel not in _ALLOWED_MONEY_APP_MODULES:
                offenders[key] = sorted(hit)
    assert not offenders, (
        "Módulos de app referencian la vía LIVE real (prohibido: CONFIRM vive en el "
        f"paquete): {offenders}"
    )


def test_auto_worker_is_discovered_by_app_scan() -> None:
    """El barrido de apps CUBRE al worker AUTO (no es un escaneo vacío)."""
    assert _WORKER.exists(), "worker AUTO no presente"
    api_src = _app_source_roots().get("api-python")
    assert api_src is not None
    discovered = _collect_modules(api_src)
    rel = _WORKER.relative_to(api_src).as_posix()
    assert rel in discovered
    assert not _reference_money(_WORKER), "el worker AUTO referencia la vía real"


# ── 3. AUTO (derivado + rol): cero símbolos de dinero, fallo por módulo ───────────
@pytest.mark.parametrize(
    ("path", "module_name"),
    _auto_module_paths(),
    ids=[name for _, name in _auto_module_paths()],
)
def test_auto_module_never_references_live_broker_money_path(path: Path, module_name: str) -> None:
    if not path.exists():
        pytest.skip(f"módulo {module_name} no presente")
    found = _reference_money(path)
    assert not found, (
        f"{module_name} referencia símbolos de la vía LIVE real: {sorted(found)}. "
        "AUTO es SIMULATED ONLY (regla P0 A8)."
    )


def test_auto_set_is_derived_from_tree_and_covers_role_spine() -> None:
    """La derivación es real (no vacía) y cubre el spine AUTO por rol."""
    assert _derive_auto_modules(), "la convención de nombre no derivó ningún módulo AUTO"
    names = {rel for _, rel in _auto_module_paths()}
    missing = sorted(rel for rel in _AUTO_BY_ROLE if rel not in names)
    assert not missing, (
        f"El spine AUTO por rol desapareció del árbol/censo: {missing}. Si se renombró, "
        "actualiza _AUTO_BY_ROLE para no perder cobertura del invariante."
    )


# ── 4. Doble-negación en el corazón AUTO ─────────────────────────────────────────
def test_auto_spine_execution_router_has_no_broker_adapter_dependency() -> None:
    """ExecutionRouter no inyecta ningún adapter ni menciona la vía real."""
    source = (_PKG / "execution_router.py").read_text(encoding="utf-8")
    assert "resolve_broker_adapter" not in source
    assert "XtbBrokerAdapter" not in source
    assert "IBrokerAdapter" not in source
