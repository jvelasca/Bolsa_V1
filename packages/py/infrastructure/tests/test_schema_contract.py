"""Contrato de esquema: metadatos declarados y allowlist de drift histórico."""

from __future__ import annotations

from sqlalchemy import CheckConstraint

from bolsa_infrastructure.database.models import Base, SyncSettingsRow
from bolsa_infrastructure.database.schema_contract import (
    KNOWN_SCHEMA_DIVERGENCES,
    SchemaContractAdapter,
    alembic_include_object,
    is_known_divergence,
)


def test_sync_settings_declares_the_060_check() -> None:
    """La migración 060 creó el CHECK; el modelo debe declararlo igual.

    Sin esta declaración ``alembic check`` veía el constraint como diferencia y un
    ``--autogenerate`` habría emitido el DROP: el intervalo se quedaba sin guardrail.
    """
    checks = {
        constraint.name: constraint
        for constraint in SyncSettingsRow.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    constraint = checks["sync_settings_provider_check_interval_check"]
    expression = str(constraint.sqltext)
    assert "provider_check_interval_seconds >= 15" in expression
    assert "provider_check_interval_seconds <= 3600" in expression


def test_contract_snapshot_covers_metadata() -> None:
    snapshot = SchemaContractAdapter().snapshot()
    assert "sync_settings" in snapshot.expected_tables
    assert ("sync_settings", "provider_check_interval_seconds") in snapshot.expected_columns
    assert any(
        item.name == "sync_settings_provider_check_interval_check"
        for item in snapshot.expected_constraints
    )
    # La tabla de control de Alembic no está en los metadatos, pero está declarada.
    assert "alembic_version" in snapshot.allowlisted


def test_allowlist_matches_by_name_and_type() -> None:
    assert is_known_divergence("custody_obligation", "table")
    assert not is_known_divergence("tabla_inventada", "table")
    assert is_known_divergence("live_orders_quantity_pos_check", "check_constraint")
    # Un nombre declarado como índice no autoriza un constraint homónimo.
    assert not is_known_divergence("ledger_entries_strategy_idx", "check_constraint")


def test_include_object_hides_only_declared_objects() -> None:
    include = alembic_include_object()
    assert callable(include)
    assert include(object(), "custody_obligation", "table", True, None) is False
    assert include(object(), "tabla_inventada", "table", True, None) is True
    assert include(object(), "sync_settings", "table", False, None) is True
    assert len(KNOWN_SCHEMA_DIVERGENCES) > 0
    assert Base.metadata.tables, "Los metadatos deben cargarse"


def test_active_profile_fk_is_restrict_not_set_null() -> None:
    """AUD-03: el borrado de un perfil asignado no puede desasignar cuentas por FK.

    ``SET NULL`` era una segunda vía de desasignación silenciosa (incluso por SQL
    directo). La migración 061 convierte la FK a ``RESTRICT``; los metadatos deben
    declarar lo mismo o un ``--autogenerate`` reintroduciría la semántica vieja.
    """
    from bolsa_infrastructure.database.models import InvestmentAccountRow

    foreign_keys = [
        fk
        for fk in InvestmentAccountRow.__table__.foreign_keys
        if fk.parent.name == "active_profile_id"
    ]
    assert len(foreign_keys) == 1, foreign_keys
    assert foreign_keys[0].target_fullname == "investor_profiles.id"
    assert foreign_keys[0].ondelete == "RESTRICT"
    # La BD crea la FK con ON UPDATE CASCADE (catálogo ART-PROFILE y la 061 lo conserva).
    # Sin declararlo aquí, ``alembic check`` no lo ve (Alembic no compara acciones de FK)
    # y el drift solo lo detecta el gate PG de acciones: la metadata debe decir la verdad.
    assert foreign_keys[0].onupdate == "CASCADE"
