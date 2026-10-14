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

§8 (cierre de huecos de auditoría `G2`/`G3`, 2026-10-14) — el invariante amplía
su superficie y su poder de detección:

* **`G2` — alcance completo del monorepo.** El barrido ya NO se acota a
  ``bolsa_application`` + ``apps/*/src``: también censa ``packages/py/{analytics,
  infrastructure, market, domain, ai}/src``. La allowlist invertida sigue vigente:
  la vía real solo puede vivir en ``bolsa_application.broker_adapter`` y en los
  módulos CONFIRM autorizados; en el resto de paquetes la allowlist es **vacía**.
  Un módulo nuevo de cualquier paquete que cablee el broker rompe en CI sin que
  nadie recuerde añadirlo.
* **`G3` — dispatch dinámico.** El detector deja de ser puramente nominal y marca
  también referencias construidas por nombre/string: ``getattr(obj, "<símbolo de
  dinero>")``, ``importlib.import_module(...)``, ``__import__(...)``, ``eval(...)``
  / ``exec(...)``, y **literales string IGUALES** a un nombre prohibido
  (``resolve_broker_adapter``, ``XtbBrokerAdapter``, ``IBrokerAdapter``,
  ``broker_adapter``, ``bolsa_application.broker_adapter``). Alcanzar la vía real
  por ``getattr``/``import`` dinámico ya no es un punto ciego.

§8b (endurecimiento del residual `G3`, 2026-10-14) — se cubren formas **NO
literales** sin introducir falsos positivos sobre el árbol actual:

* ``getattr(<receptor>, <nombre NO literal>)`` cuando el receptor es un **módulo
  importado** (nombre ligado a ``import``/``from … import``) o su identificador es
  un nombre prohibido ⇒ ``getattr:dynamic@L<n>``.
* ``importlib.import_module(...)`` / ``__import__(...)`` / ``eval(...)`` / ``exec(...)``
  ya se marcan incondicionalmente (cubren el argumento literal y el no literal).
* **Composición estática**: ``ast.BinOp`` (``+``) y ``ast.JoinedStr`` (f-strings)
  cuyo texto reconstruible es IGUAL a un nombre prohibido ⇒
  ``composed-name:<valor>@L<n>`` (p. ej. ``"resolve_broker" + "_adapter"``), aunque
  ningún fragmento suelto coincida.

**Residual declarado:** ``getattr(<objeto-local>, <variable>)`` sobre un objeto de
datos (``getattr(self, field_name)``, ``getattr(row, name)``…) NO se marca: es
indistinguible del acceso dinámico benigno sin análisis de flujo de datos y
marcarlo rompería los barridos con ~46 falsos positivos. El invariante lo declara
como límite (ver auditoría §7/§9), no como ausencia de barrera.
"""

from __future__ import annotations

import ast
import textwrap
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
# G3 — nombres prohibidos que, apareciendo como string literal o como nombre de
# ``getattr``, delatan una referencia DINÁMICA (construida por nombre) a la vía real.
_FORBIDDEN_DYNAMIC_NAMES: frozenset[str] = frozenset(
    _MONEY_SYMBOLS | {"broker_adapter", _BROKER_MODULE}
)
# G2 — paquetes del monorepo cuyo ``src`` también se barre. Para ellos la allowlist
# invertida es VACÍA: la vía real solo puede vivir en bolsa_application.
_OTHER_PACKAGE_ROOTS: dict[str, Path] = {
    "analytics": _REPO / "packages" / "py" / "analytics" / "src",
    "infrastructure": _REPO / "packages" / "py" / "infrastructure" / "src",
    "market": _REPO / "packages" / "py" / "market" / "src",
    "domain": _REPO / "packages" / "py" / "domain" / "src",
    "ai": _REPO / "packages" / "py" / "ai" / "src",
}

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
    """Símbolos de la vía real importados/referenciados en un AST (imports + attrs).

    Cada hallazgo se anota con su línea (``símbolo@L<n>``) para que el fallo sea
    trazable a ``file:line``.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith(_BROKER_MODULE):
                for alias in node.names:
                    name = alias.name.split(".")[0]
                    if name in _MONEY_SYMBOLS:
                        found.add(f"{name}@L{node.lineno}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(_BROKER_MODULE):
                    found.add(f"(module import of broker_adapter)@L{node.lineno}")
    # Referencias por atributo (p. ej. broker_adapter.resolve_broker_adapter(...)).
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in _MONEY_SYMBOLS:
            found.add(f"attribute:{node.attr}@L{node.lineno}")
    # El verbo que MUEVE dinero en la vía real: cualquier ``X.submit(...)`` (así se
    # detecta también lo que llega por DI — un adapter inyectado como callable, p. ej.
    # ``confirm/execution.py``— sin nombrar el símbolo del puerto).
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "submit"
        ):
            found.add(f"call:.submit@L{node.lineno}")
    return found


def _string_literal(node: ast.AST) -> str | None:
    """Valor de un literal string, o ``None`` si el nodo no es un literal str."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _composed_static_string(node: ast.AST) -> str | None:
    """Texto estático de una composición de strings, o ``None`` si no es resoluble.

    Cubre ``ast.BinOp`` con ``+`` (concatenación) y ``ast.JoinedStr`` (f-strings)
    **solo** cuando TODAS sus partes son literales resolubles. Si alguna parte es
    dinámica (variable, llamada…) devuelve ``None``: el invariante prefiere el falso
    negativo (declarado en la auditoría) al falso positivo sobre el árbol actual.
    """
    literal = _string_literal(node)
    if literal is not None:
        return literal
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _composed_static_string(node.left)
        right = _composed_static_string(node.right)
        if left is None or right is None:
            return None
        return left + right
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.FormattedValue):
                part = _composed_static_string(value.value)
            else:
                part = _composed_static_string(value)
            if part is None:
                return None
            parts.append(part)
        return "".join(parts)
    return None


def _module_bound_names(tree: ast.AST) -> set[str]:
    """Nombres locales ligados a un ``import`` (módulo o alias) en el propio fichero.

    Un ``getattr`` con 2º argumento NO literal solo es señal de dispatch dinámico
    cuando el receptor puede ser un **módulo** (p. ej. ``import a.b as ba; getattr(ba, n)``
    o ``from x import broker_adapter; getattr(broker_adapter, n)``). Sobre un objeto de
    datos (``getattr(self, field_name)``, ``getattr(row, name)``…) es acceso de atributo
    ordinario: marcarlo sería un falso positivo masivo sobre el repositorio actual y
    obligaría a silenciar media base de código. Ese caso queda **declarado** como
    residual del invariante.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.add(alias.asname or alias.name)
    return names


def _receiver_identifiers(node: ast.AST) -> set[str]:
    """Identificadores que aparecen en la expresión receptora de un ``getattr``."""
    identifiers: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name):
            identifiers.add(sub.id)
        elif isinstance(sub, ast.Attribute):
            identifiers.add(sub.attr)
    return identifiers


def _dynamic_dispatch_symbols(tree: ast.AST) -> set[str]:
    """G3 — referencias a la vía real construidas por NOMBRE/string en runtime.

    Marca los puntos ciegos del detector nominal:

    * ``getattr(obj, "<símbolo de dinero>")`` (el 2º argumento es un literal igual a
      un nombre prohibido);
    * ``getattr(<receptor>, <nombre NO literal>)`` cuando el receptor es un **módulo
      importado** (o su identificador es un nombre prohibido) — dispatch construido
      en runtime, p. ej. ``getattr(broker_adapter, name)``;
    * ``importlib.import_module(...)`` (import dinámico);
    * el builtin ``__import__(...)``;
    * los builtins ``eval(...)`` / ``exec(...)`` (código generado);
    * **literales string IGUALES** a un nombre prohibido (p. ej. la cadena
      ``"resolve_broker_adapter"`` usada para construir la referencia);
    * **concatenaciones/f-strings** (``ast.BinOp`` / ``ast.JoinedStr``) cuyo texto
      estático reconstruible es IGUAL a un nombre prohibido (p. ej.
      ``"resolve_broker" + "_adapter"`` o ``f"{'resolve_broker'}_adapter"``), aunque
      ninguno de sus fragmentos sueltos coincida por separado.
    """
    found: set[str] = set()
    module_bound = _module_bound_names(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name):
                if func.id == "getattr":
                    if len(node.args) >= 2:
                        literal = _string_literal(node.args[1])
                        if literal is not None:
                            if literal in _FORBIDDEN_DYNAMIC_NAMES:
                                found.add(f"getattr:{literal}@L{node.lineno}")
                        elif _receiver_identifiers(node.args[0]) & (
                            module_bound | _FORBIDDEN_DYNAMIC_NAMES
                        ):
                            found.add(f"getattr:dynamic@L{node.lineno}")
                elif func.id == "__import__":
                    found.add(f"__import__@L{node.lineno}")
                elif func.id in {"eval", "exec"}:
                    found.add(f"builtin:{func.id}@L{node.lineno}")
            elif (
                isinstance(func, ast.Attribute)
                and func.attr == "import_module"
                and isinstance(func.value, ast.Name)
                and func.value.id == "importlib"
            ):
                found.add(f"importlib.import_module@L{node.lineno}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in _FORBIDDEN_DYNAMIC_NAMES:
                found.add(f"string-literal:{node.value}@L{node.lineno}")
        elif isinstance(node, (ast.BinOp, ast.JoinedStr)):
            composed = _composed_static_string(node)
            if composed is not None and composed in _FORBIDDEN_DYNAMIC_NAMES:
                found.add(f"composed-name:{composed}@L{node.lineno}")
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
    """Toda señal (estática + dinámica) de que un módulo toca la vía real.

    Une el censo nominal (``_imported_money_symbols``: imports/attrs/``.submit``) con
    el detector de dispatch dinámico (``_dynamic_dispatch_symbols``: G3).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return _imported_money_symbols(tree) | _dynamic_dispatch_symbols(tree)


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


# ── 2b. Barrido ampliado (G2): NINGÚN otro paquete del monorepo toca la vía real ──
def test_no_other_package_references_live_money_path() -> None:
    """G2 — el censo cubre TODOS los paquetes, no solo ``bolsa_application``.

    La vía real solo puede vivir en la allowlist de ``bolsa_application``. Para el
    resto de paquetes (``analytics``, ``infrastructure``, ``market``, ``domain``,
    ``ai``) la allowlist invertida es VACÍA: cualquier módulo que importe/referencie
    el puerto, llame a ``.submit`` o lo alcance por dispatch dinámico (G3) rompe aquí.
    El mensaje lista cada hallazgo como ``paquete/fichero.py:símbolo@L<línea>``.
    """
    discovered = 0
    offenders: list[str] = []
    for pkg, root in _OTHER_PACKAGE_ROOTS.items():
        assert root.is_dir(), (
            f"paquete esperado ausente del barrido G2: {root}. Si de verdad ya no "
            "existe, retíralo de _OTHER_PACKAGE_ROOTS (punto de auditoría)."
        )
        for rel, path in _collect_modules(root).items():
            discovered += 1
            for finding in sorted(_reference_money(path)):
                offenders.append(f"{pkg}/{rel}:{finding}")
    assert discovered, "el barrido ampliado G2 no descubrió ningún módulo — revisa las raíces"
    assert not offenders, (
        "Paquetes fuera de bolsa_application referencian la vía LIVE real (la vía real "
        f"solo puede vivir en bolsa_application): {offenders}"
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


# ── 5. G3 residual: dispatch dinámico NO literal (tests puros, AST) ───────────────
def _dynamic_hits(source: str) -> set[str]:
    """Hallazgos del detector G3 para un fragmento de código (sin tocar el disco)."""
    return _dynamic_dispatch_symbols(ast.parse(textwrap.dedent(source)))


class TestDynamicDispatchSymbols:
    """Fija por unidad el contrato del detector de dispatch dinámico (G3).

    Positivos = formas construidas por nombre/string que SÍ deben marcar.
    Negativos = formas benignas dominantes del repo que NO deben marcar (si marcan,
    los barridos del monorepo dejan de estar en 0 hallazgos).
    """

    def test_literal_forbidden_getattr_marks(self) -> None:
        # El literal del 2º arg también dispara la guarda de string-literal (esperado).
        hits = _dynamic_hits('getattr(obj, "resolve_broker_adapter")')
        assert "getattr:resolve_broker_adapter@L1" in hits, hits
        assert "string-literal:resolve_broker_adapter@L1" in hits, hits

    def test_literal_forbidden_module_getattr_marks(self) -> None:
        hits = _dynamic_hits('getattr(obj, "broker_adapter")')
        assert "getattr:broker_adapter@L1" in hits, hits
        assert "string-literal:broker_adapter@L1" in hits, hits

    def test_nonliteral_getattr_on_imported_module_marks(self) -> None:
        hits = _dynamic_hits(
            """
            from bolsa_application import broker_adapter

            name = "resolve"
            fn = getattr(broker_adapter, name)
            """
        )
        assert any(h.startswith("getattr:dynamic@L") for h in hits), hits

    def test_nonliteral_getattr_on_import_alias_marks(self) -> None:
        hits = _dynamic_hits(
            """
            import bolsa_application.broker_adapter as ba

            fn = getattr(ba, attr_name)
            """
        )
        assert any(h.startswith("getattr:dynamic@L") for h in hits), hits

    def test_nonliteral_getattr_on_forbidden_ident_marks(self) -> None:
        # DI: el receptor NO es un import, pero su identificador es un símbolo prohibido.
        hits = _dynamic_hits("fn = getattr(self.broker_adapter, method_name)")
        assert any(h.startswith("getattr:dynamic@L") for h in hits), hits

    def test_nonliteral_getattr_on_instance_does_not_mark(self) -> None:
        # Negativo = forma benigna dominante del repo (self/row/...): NO marca.
        hits = _dynamic_hits(
            """
            def f(self, row):
                a = getattr(self, field_name)
                b = getattr(row, name, None)
                return a, b
            """
        )
        assert hits == set(), hits

    def test_literal_benign_getattr_does_not_mark(self) -> None:
        hits = _dynamic_hits('getattr(obj, "instrument_id")')
        assert hits == set(), hits

    def test_importlib_import_module_marks(self) -> None:
        hits = _dynamic_hits(
            """
            import importlib

            mod = importlib.import_module(build_name())
            """
        )
        assert any(h.startswith("importlib.import_module@L") for h in hits), hits

    def test_dunder_import_marks(self) -> None:
        hits = _dynamic_hits("__import__(name)")
        assert any(h.startswith("__import__@L") for h in hits), hits

    def test_eval_marks(self) -> None:
        hits = _dynamic_hits("eval(payload)")
        assert any(h.startswith("builtin:eval@L") for h in hits), hits

    def test_exec_marks(self) -> None:
        hits = _dynamic_hits("exec(payload)")
        assert any(h.startswith("builtin:exec@L") for h in hits), hits

    def test_binop_composed_forbidden_name_marks(self) -> None:
        # Ningún fragmento suelto es prohibido: solo la composición lo es.
        hits = _dynamic_hits('name = "resolve_broker" + "_adapter"')
        assert hits == {"composed-name:resolve_broker_adapter@L1"}, hits

    def test_fstring_composed_forbidden_name_marks(self) -> None:
        hits = _dynamic_hits("name = f\"{'resolve_broker'}{'_adapter'}\"")
        assert hits == {"composed-name:resolve_broker_adapter@L1"}, hits

    def test_binop_with_dynamic_part_does_not_mark(self) -> None:
        hits = _dynamic_hits('name = "resolve_broker" + suffix')
        assert not any(h.startswith("composed-name:") for h in hits), hits

    def test_fstring_with_dynamic_part_does_not_mark(self) -> None:
        hits = _dynamic_hits('name = f"resolve_{suffix}"')
        assert not any(h.startswith("composed-name:") for h in hits), hits

    def test_benign_similar_literal_does_not_mark(self) -> None:
        # "broker_venue" NO es un nombre prohibido (guarda anti-sobreajuste).
        hits = _dynamic_hits('label = "broker_venue"')
        assert hits == set(), hits
