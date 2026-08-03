"""RD-3 — selección de motor de optimización."""

from __future__ import annotations

OptimizeEngineName = str


def vectorbt_available() -> bool:
    """True si VectorBT + llvmlite cargan.

    En Windows, WDAC puede bloquear ``llvmlite.dll`` (WinError 4551) aunque el
    paquete esté instalado — tratamos eso como no disponible.
    """
    try:
        import vectorbt  # noqa: F401

        return True
    except (ImportError, OSError):
        return False


def optuna_available() -> bool:
    """Helper: ``optuna_available``."""
    try:
        import optuna  # noqa: F401

        return True
    except (ImportError, OSError):
        return False


def resolve_optimize_engine(requested: str | None) -> OptimizeEngineName:
    """Resuelve ``optimize_engine``."""
    normalized = (requested or "auto").strip().lower()
    if normalized == "auto":
        if vectorbt_available():
            return "vectorbt"
        return "h0"
    if normalized in {"h0", "sma_grid_h0"}:
        return "h0"
    if normalized == "vectorbt":
        if not vectorbt_available():
            raise ValueError("VectorBT no instalado — usa engine=h0 o instala vectorbt")
        return "vectorbt"
    if normalized == "optuna":
        if not vectorbt_available():
            raise ValueError("VectorBT requerido para engine=optuna")
        if not optuna_available():
            raise ValueError("Optuna no instalado — pip install optuna")
        return "optuna"
    raise ValueError("engine inválido — usa auto, h0, vectorbt u optuna")


def engine_result_label(engine: OptimizeEngineName) -> str:
    """Función pública ``engine_result_label``."""
    return {
        "h0": "sma_grid_h0",
        "vectorbt": "vectorbt_sma_grid",
        "optuna": "optuna_sma",
    }[engine]
