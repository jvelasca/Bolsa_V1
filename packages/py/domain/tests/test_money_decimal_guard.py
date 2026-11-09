"""Guard ejecutable de la política monetaria del dominio (Fase 2.3, auditoría externa).

La política vive en :mod:`bolsa_domain.money`: **campo monetario ⇒ ``Decimal``**,
**ratio ⇒ ``float``**. Este test la convierte en un ratchet: recorre todas las
dataclasses de ``bolsa_domain`` y falla si un campo con nombre monetario
(``amount``, ``price``, ``cost``, ``fee``, ``commission``, ``balance``, ``equity``,
``cash``, ``pnl``, ``value``, ...) sigue anotado como ``float`` sin una excepción
declarada y justificada.

Las excepciones son deliberadas y están acotadas por clase: módulos cuyos números son
entradas/salidas de calculadoras vectorizadas o de proveedores de mercado (``float`` de
extremo a extremo), no libros de caja. Cuando una excepción deja de serlo (todos sus
campos monetarios ya son ``Decimal``), el test obliga a borrarla para que la lista no
envejezca.
"""

from __future__ import annotations

import dataclasses
import importlib
import pkgutil
from decimal import Decimal
from typing import Any

import pytest

import bolsa_domain
from bolsa_domain.entities.account import (
    AccountSummary,
    CustodyObligation,
    InvestmentAccount,
    LedgerEntry,
)
from bolsa_domain.entities.portfolio import (
    Portfolio,
    Position,
    Transaction,
)
from bolsa_domain.money import (
    MONEY_QUANT,
    PRICE_QUANT,
    quantize_money,
    quantize_price,
    to_decimal,
)

#: Campos cuyo nombre contiene dinero. ``total`` se incluye como nombre exacto porque
#: ``total_market_value`` ya entra por ``value``.
MONEY_TOKENS: tuple[str, ...] = (
    "amount",
    "price",
    "cost",
    "fee",
    "commission",
    "balance",
    "equity",
    "cash",
    "pnl",
    "value",
    "deposit",
    "outstanding",
    "margin_used",
    "free_margin",
)

#: Campos que son ratios por contrato, aunque su nombre contenga un token monetario
#: (``unrealized_pnl_pct``). ``leverage`` es un multiplicador, no dinero.
RATIO_SUFFIXES: tuple[str, ...] = ("_pct", "_ratio")
RATIO_NAMES: frozenset[str] = frozenset({"leverage"})

#: Excepciones declaradas: ``(módulo, clase) -> motivo``. Cada una es un borde que
#: trabaja en ``float`` y convierte a ``Decimal`` antes de tocar una entidad de libro.
EXEMPT_CLASSES: dict[tuple[str, str], str] = {
    (
        "bolsa_domain.account_settings",
        "CommissionProfile",
    ): "tasas y topes min/max de comisión consumidos por calculadoras de fees en float; "
    "el importe resultante entra en LedgerEntry como Decimal.",
    (
        "bolsa_domain.account_settings",
        "TradeFeeBreakdown",
    ): "desglose producido por la calculadora de comisiones en float; no se suma en un "
    "libro de caja y se cuantiza al persistir el asiento.",
    (
        "bolsa_domain.entities.backtest",
        "BacktestRun",
    ): "resultado de simulación vectorizada (numpy float); no es un libro contable.",
    (
        "bolsa_domain.entities.backtest",
        "BacktestRunDetail",
    ): "detalle de simulación vectorizada (numpy float); no es un libro contable.",
    (
        "bolsa_domain.entities.backtest",
        "BacktestTrade",
    ): "operación simulada por el motor vectorizado en float; no se persiste como libro.",
    (
        "bolsa_domain.entities.cognitive_artifacts",
        "PredictionRecord",
    ): "``value`` es una métrica genérica de predicción (probabilidad/score), no dinero.",
    (
        "bolsa_domain.value_objects.market",
        "LiveQuoteReference",
    ): "precio de cotización entrante del proveedor; se convierte a Decimal al cruzar al "
    "dominio contable.",
    (
        "bolsa_domain.tax_report",
        "_ResidualPosition",
    ): "estado interno de la calculadora FIFO, que opera en float por contrato.",
    (
        "bolsa_domain.tax_report",
        "TaxReportTransaction",
    ): "entrada de la calculadora fiscal; el mapeador convierte Decimal->float en el borde.",
    (
        "bolsa_domain.tax_report",
        "RealizedGainLine",
    ): "línea de reporte fiscal calculada en float y publicada como número.",
    (
        "bolsa_domain.tax_report",
        "UnrealizedGainLine",
    ): "línea de reporte fiscal calculada en float y publicada como número.",
    (
        "bolsa_domain.tax_report",
        "TaxReportSummary",
    ): "agregados del reporte fiscal calculados en float por la calculadora.",
}


def _annotation_text(cls: type, field: dataclasses.Field[Any]) -> str:
    raw: Any = getattr(cls, "__annotations__", {}).get(field.name, field.type)
    if isinstance(raw, str):
        return raw
    return getattr(raw, "__name__", str(raw))


def _is_money_like(field: dataclasses.Field[Any]) -> bool:
    name = field.name
    if name in RATIO_NAMES or name.endswith(RATIO_SUFFIXES):
        return False
    return name == "total" or any(token in name for token in MONEY_TOKENS)


def _is_numeric(annotation: str) -> bool:
    return "float" in annotation or "int" in annotation


def _violations(cls: type) -> list[str]:
    """Campos monetarios numéricos que NO son ``Decimal``."""
    return [
        f"{cls.__qualname__}.{field.name}: {_annotation_text(cls, field)}"
        for field in dataclasses.fields(cls)
        if _is_money_like(field)
        and _is_numeric(_annotation_text(cls, field))
        and "Decimal" not in _annotation_text(cls, field)
    ]


def _iter_domain_dataclasses() -> list[type]:
    classes: list[type] = []
    for module_info in pkgutil.walk_packages(bolsa_domain.__path__, "bolsa_domain."):
        if ".tests" in module_info.name or ".__main__" in module_info.name:
            continue
        module = importlib.import_module(module_info.name)
        for obj in vars(module).values():
            if (
                isinstance(obj, type)
                and dataclasses.is_dataclass(obj)
                and obj.__module__ == module_info.name
            ):
                classes.append(obj)
    return sorted(classes, key=lambda cls: (cls.__module__, cls.__qualname__))


def test_money_like_domain_fields_are_decimal() -> None:
    offenders: list[str] = []
    for cls in _iter_domain_dataclasses():
        if (cls.__module__, cls.__qualname__) in EXEMPT_CLASSES:
            continue
        offenders.extend(_violations(cls))
    assert offenders == [], (
        "campos monetarios del dominio que siguen en float:\n  "
        + "\n  ".join(offenders)
        + "\nMigra el campo a Decimal (bolsa_domain.money.coerce_money_fields) o, si es "
        "un borde deliberado, declara la clase en EXEMPT_CLASSES con su motivo."
    )


def test_accounting_entities_are_guarded() -> None:
    """Las entidades del libro de caja deben estar vigiladas, no exentas."""
    guarded_modules = {
        "bolsa_domain.entities.account",
        "bolsa_domain.entities.portfolio",
        "bolsa_domain.lifecycle",
    }
    guarded = {
        (cls.__module__, cls.__qualname__)
        for cls in _iter_domain_dataclasses()
        if cls.__module__ in guarded_modules and _violations(cls) == []
    }
    expected = {
        ("bolsa_domain.entities.account", "InvestmentAccount"),
        ("bolsa_domain.entities.account", "AccountSummary"),
        ("bolsa_domain.entities.account", "LedgerEntry"),
        ("bolsa_domain.entities.account", "CashMovementResult"),
        ("bolsa_domain.entities.account", "CustodyObligation"),
        ("bolsa_domain.entities.portfolio", "Portfolio"),
        ("bolsa_domain.entities.portfolio", "Position"),
        ("bolsa_domain.entities.portfolio", "PortfolioSummary"),
        ("bolsa_domain.entities.portfolio", "Transaction"),
    }
    assert expected <= guarded, f"entidades del libro sin guardar: {expected - guarded}"


def test_ratio_fields_stay_float() -> None:
    ratios = [("InvestmentAccount", InvestmentAccount, "leverage")]
    ratios += [
        ("AccountSummary", AccountSummary, "margin_level_pct"),
        ("Position", Position, "unrealized_pnl_pct"),
    ]
    for label, cls, field_name in ratios:
        annotation = _annotation_text(cls, dataclasses.fields(cls)[
            [f.name for f in dataclasses.fields(cls)].index(field_name)
        ])
        assert "Decimal" not in annotation, f"{label}.{field_name} no debe ser Decimal"
        assert "float" in annotation, f"{label}.{field_name} debe ser float"


def test_exemptions_are_documented_and_not_stale() -> None:
    by_key = {
        (cls.__module__, cls.__qualname__): cls for cls in _iter_domain_dataclasses()
    }
    for (module, name), reason in EXEMPT_CLASSES.items():
        assert reason.strip(), f"excepción sin motivo: {module}.{name}"
        cls = by_key.get((module, name))
        assert cls is not None, f"excepción apunta a una clase inexistente: {module}.{name}"
        assert _violations(cls), (
            f"excepción obsoleta: {module}.{name} ya no tiene campos monetarios en float; "
            "bórrala de EXEMPT_CLASSES."
        )


def test_float_payload_is_coerced_without_binary_tail() -> None:
    position = Position(
        id="p1",
        instrument_id="i1",
        symbol="SAN",
        name="Santander",
        quantity=10.0,
        avg_cost=0.1,
        last_price=4.5,
        market_value=45.0,
        unrealized_pnl=1.25,
        unrealized_pnl_pct=2.86,
    )
    assert isinstance(position.avg_cost, Decimal)
    assert str(position.avg_cost) == "0.1"  # Decimal(str(0.1)), no la expansión binaria
    assert isinstance(position.unrealized_pnl_pct, float)

    summary = AccountSummary(
        account=_account(),
        default_portfolio=Portfolio(id="pf1", name="Cartera", currency="EUR", cash=0.1),
        cash=0.1,
        total_market_value=45.0,
        total_cost=30.0,
        total_unrealized_pnl=1.25,
        total_equity=1234.56,
        margin_used=0.0,
        free_margin=1234.56,
        margin_level_pct=None,
        positions_count=1,
    )
    assert isinstance(summary.cash, Decimal)
    assert str(summary.cash) == "0.1"
    assert isinstance(summary.total_equity, Decimal)

    transaction = Transaction(
        id="t1",
        type="buy",
        instrument_id="i1",
        symbol="SAN",
        quantity=10.0,
        price=12.71,
        total=127.1,
        executed_at="2026-01-02T09:00:00Z",
    )
    assert transaction.price == Decimal("12.71")
    assert transaction.total == Decimal("127.1")

    entry = LedgerEntry(
        id="l1",
        account_id="a1",
        portfolio_id="pf1",
        type="deposit",
        amount=50000.0,
        currency="EUR",
        balance_after=50000.0,
        instrument_id=None,
        symbol=None,
        quantity=None,
        price=None,
        reference_type=None,
        reference_id=None,
        description=None,
        executed_at="2026-01-02T09:00:00Z",
    )
    assert entry.amount == Decimal("50000.0")
    assert entry.price is None


def test_none_stays_none_for_unmeasured_money() -> None:
    obligation = CustodyObligation(
        account_id="a1",
        period="2026",
        status="PENDING",
        outstanding=Decimal("1.23"),
        total_fee=Decimal("1.23"),
    )
    assert obligation.outstanding == Decimal("1.23")
    assert to_decimal("0.1") == Decimal("0.1")


def test_float_artifact_is_preserved_not_invented() -> None:
    """``to_decimal`` no adivina: convierte la repr decimal del float, no la corrige.

    ``0.1 + 0.2`` ya es otro número en binario; el dominio lo conserva tal cual y el
    redondeo explícito (``quantize_money``) es el único que lo cierra a céntimos.
    """
    assert to_decimal(0.1) == Decimal("0.1")
    assert to_decimal(0.1 + 0.2) == Decimal("0.30000000000000004")
    assert quantize_money(0.1 + 0.2) == Decimal("0.30")


def test_quantize_policy_is_half_even() -> None:
    assert MONEY_QUANT == Decimal("0.01")
    assert PRICE_QUANT == Decimal("0.0001")
    assert quantize_money("10.005") == Decimal("10.00")
    assert quantize_money("10.015") == Decimal("10.02")
    assert quantize_price("1.00005") == Decimal("1.0000")
    assert quantize_price("1.00015") == Decimal("1.0002")


def test_guard_detects_a_violation() -> None:
    """El guard debe fallar de verdad: si no, es decorativo."""

    @dataclasses.dataclass
    class Rogue:
        amount: float
        unrealized_pnl_pct: float

    assert _violations(Rogue) == ["test_guard_detects_a_violation.<locals>.Rogue.amount: float"]


def _account() -> InvestmentAccount:
    return InvestmentAccount(
        id="a1",
        user_id=None,
        name="Cuenta",
        description=None,
        type="standard",
        status="active",
        currency="EUR",
        base_currency="EUR",
        initial_deposit=Decimal("50000"),
        leverage=1.0,
        margin_call_level_pct=None,
        is_default=True,
        settings=None,
        strategy_definition_id=None,
        source_backtest_run_id=None,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        last_activity_at=None,
    )


@pytest.mark.parametrize(
    "field_name",
    ["initial_deposit", "cash", "avg_cost", "price", "amount", "total_fee"],
)
def test_representative_money_fields_are_decimal(field_name: str) -> None:
    owners = [
        cls
        for cls in (
            InvestmentAccount,
            Portfolio,
            Position,
            Transaction,
            LedgerEntry,
            CustodyObligation,
        )
        if field_name in {f.name for f in dataclasses.fields(cls)}
    ]
    assert owners, f"ninguna entidad declara {field_name}"
    for cls in owners:
        field = next(f for f in dataclasses.fields(cls) if f.name == field_name)
        assert "Decimal" in _annotation_text(cls, field), f"{cls.__qualname__}.{field_name}"
