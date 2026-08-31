"""V1.46 — GP-DESK-03 PaperDailyReport / autoDesk shape."""

from __future__ import annotations

from datetime import date

from bolsa_application.daily_ops_report import DailyOpsReportBundle
from bolsa_application.paper_daily_report import (
    PAPER_DAILY_REPORT_SCHEMA,
    build_paper_daily_report,
)
from bolsa_application.paper_desk_cycle import (
    PaperDeskCycleResult,
    PaperDeskEntryTickResult,
    PaperDeskPositionTickRow,
)


def _cycle(**kwargs: object) -> PaperDeskCycleResult:
    defaults: dict[str, object] = {
        "account_id": "acc-1",
        "as_of": "2026-08-31",
        "dry_run": True,
        "paper_d_execute": False,
        "entry": PaperDeskEntryTickResult(
            status="dry_run",
            proposed_count=1,
            executed_count=0,
            notes=("entry note",),
        ),
        "positions": (
            PaperDeskPositionTickRow(
                instrument_id="MSFT",
                status="held",
                decision_verdict="HOLD",
            ),
            PaperDeskPositionTickRow(
                instrument_id="AAPL",
                status="denied",
                reason="data_stale",
                decision_verdict="EXIT",
                permission_reasons=("data_stale",),
            ),
            PaperDeskPositionTickRow(
                instrument_id="IBM",
                status="protected",
                decision_verdict="PROTECT",
            ),
        ),
        "notes": ("dryRun=true — no ledger mutate.",),
    }
    defaults.update(kwargs)
    return PaperDeskCycleResult(**defaults)  # type: ignore[arg-type]


def test_gp_desk_03_report_shape() -> None:
    report = build_paper_daily_report(_cycle())
    d = report.to_dict()
    assert d["schemaVersion"] == PAPER_DAILY_REPORT_SCHEMA
    assert d["entry"]["proposed"] == 1
    assert d["entry"]["executed"] == 0
    assert d["positions"]["held"] == 1
    assert d["positions"]["denied"] == 1
    assert d["positions"]["protected"] == 1
    assert d["jitDenies"]["data_stale"] == 1
    assert "dryRun" in d["notes"] or any("dryRun" in n for n in d["notes"])


def test_gp_desk_03_env_blocked_notes() -> None:
    report = build_paper_daily_report(
        _cycle(
            dry_run=False,
            blocked=True,
            block_reason="paper_auto_env_blocked",
            positions=(),
            entry=PaperDeskEntryTickResult(
                status="blocked",
                reason="paper_auto_env_blocked",
            ),
            notes=("PAPER_D_EXECUTE off.", "paper_auto_env_blocked"),
        )
    )
    assert report.jit_denies.get("paper_auto_env_blocked", 0) >= 1
    assert "paper_auto_env_blocked" in report.notes


def test_gp_desk_03_daily_ops_valid_without_autodesk() -> None:
    """DailyOpsReportBundle sigue válido sin auto_desk."""
    from unittest.mock import MagicMock

    bundle = DailyOpsReportBundle(
        as_of=date(2026, 8, 31),
        generated_at="2026-08-31T12:00:00Z",
        account_id="acc-1",
        summary=MagicMock(),
        ledger_today=[],
        trades_today=[],
        week=[],
        f3_pending_count=0,
        channels={"alarma": 0, "aviso": 0, "none": 0},
        opinions=[],
        notes=["ok"],
        estudio_status="ok",
        estudio_count=0,
        auto_desk=None,
    )
    assert bundle.auto_desk is None
    assert bundle.estudio_status == "ok"


def test_gp_desk_03_daily_ops_with_autodesk() -> None:
    from unittest.mock import MagicMock

    auto = build_paper_daily_report(_cycle()).to_dict()
    bundle = DailyOpsReportBundle(
        as_of=date(2026, 8, 31),
        generated_at="2026-08-31T12:00:00Z",
        account_id="acc-1",
        summary=MagicMock(),
        ledger_today=[],
        trades_today=[],
        week=[],
        f3_pending_count=0,
        channels={"alarma": 0, "aviso": 0, "none": 0},
        opinions=[],
        notes=["ok"],
        auto_desk=auto,
    )
    assert bundle.auto_desk is not None
    assert bundle.auto_desk["schemaVersion"] == PAPER_DAILY_REPORT_SCHEMA
