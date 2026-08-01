"""Platform Kernel — constantes y validación (ADR-010, paridad @bolsa/shared)."""

from __future__ import annotations

KERNEL_TIMEFRAMES: frozenset[str] = frozenset({"1d", "1wk"})

KERNEL_EVALUATION_MODES: frozenset[str] = frozenset({"bar_close", "realtime"})
KERNEL_EVALUATION_MODES_ACTIVE: frozenset[str] = frozenset({"bar_close"})

MIN_SCAN_BARS = 50
MAX_SCAN_BAR_LIMIT = 5000
MAX_SCAN_RESULTS = 500

# Sync HTTP — límite operativo hasta P2 chunking.
MAX_SCAN_INSTRUMENTS_SYNC = 500

# Jobs async — techo duro; P2 particionará en chunks de MAX_SCAN_INSTRUMENTS_CHUNK.
MAX_SCAN_INSTRUMENTS_ASYNC = 5000
MAX_SCAN_INSTRUMENTS_CHUNK = 250

EXECUTION_MODES: frozenset[str] = frozenset({"inform_only", "alert", "paper_auto", "live_auto"})
POSITION_EXECUTION_MODES: frozenset[str] = frozenset({"manual", "exit_strategy", "full_auto"})
PAPER_ACCOUNT_TYPES: frozenset[str] = frozenset({"paper", "simulated"})
# Premisa 2026-07-31: hoy solo DEMO (simulated). Tipo paper = broker real futuro.
# paper_auto mode ejecuta sobre ledger de cuenta activa (típicamente simulated).
# @see docs/engineering/account-premises-demo-vs-paper-2026-07-31.md
DEFAULT_SIGNAL_KINDS: tuple[str, ...] = ("entry_long", "exit")


def validate_kernel_timeframe(timeframe: str) -> str:
    normalized = timeframe.strip()
    if normalized not in KERNEL_TIMEFRAMES:
        allowed = ", ".join(sorted(KERNEL_TIMEFRAMES))
        raise ValueError(
            f"timeframe debe ser uno de: {allowed} (kernel ADR-010). Recibido: {timeframe!r}",
        )
    return normalized


def validate_scan_bar_limit(bar_limit: int) -> int:
    if bar_limit < MIN_SCAN_BARS or bar_limit > MAX_SCAN_BAR_LIMIT:
        raise ValueError(f"barLimit debe estar entre {MIN_SCAN_BARS} y {MAX_SCAN_BAR_LIMIT}")
    return bar_limit


def validate_scan_max_results(max_results: int) -> int:
    if max_results < 1 or max_results > MAX_SCAN_RESULTS:
        raise ValueError(f"maxResults debe estar entre 1 y {MAX_SCAN_RESULTS}")
    return max_results


def max_scan_instruments(*, async_job: bool) -> int:
    return MAX_SCAN_INSTRUMENTS_ASYNC if async_job else MAX_SCAN_INSTRUMENTS_SYNC


def validate_scan_universe_size(count: int, *, async_job: bool = False) -> None:
    limit = max_scan_instruments(async_job=async_job)
    if count > limit:
        mode = "async" if async_job else "sync"
        hint = (
            " Usa POST /api/scans/jobs para universos grandes."
            if not async_job and count <= MAX_SCAN_INSTRUMENTS_ASYNC
            else ""
        )
        raise ValueError(
            f"El universo tiene {count} instrumentos; límite {mode}: {limit}.{hint}",
        )


def validate_execution_mode(mode: str) -> str:
    normalized = mode.strip()
    if normalized not in EXECUTION_MODES:
        allowed = ", ".join(sorted(EXECUTION_MODES))
        raise ValueError(f"mode debe ser uno de: {allowed}. Recibido: {mode!r}")
    return normalized


def validate_position_execution_mode(mode: str) -> str:
    normalized = mode.strip()
    if normalized not in POSITION_EXECUTION_MODES:
        allowed = ", ".join(sorted(POSITION_EXECUTION_MODES))
        raise ValueError(f"mode debe ser uno de: {allowed}. Recibido: {mode!r}")
    return normalized
