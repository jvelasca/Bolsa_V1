"""Contrato de esquema: qué espera el código y qué divergencias están declaradas.

``alembic check`` comparaba el esquema real con ``Base.metadata`` **sin memoria**: cada
diferencia histórica (la tabla obsoleta ``custody_obligation``, índices que la BD conserva
y los metadatos ya no declaran, ``CHECK`` de ``live_orders``) aparecía como una operación
pendiente. Un ``--autogenerate`` a ciegas habría **borrado** guardrails y índices.

Este módulo introduce dos piezas:

* ``SchemaContractAdapter`` — fotografía de ``Base.metadata`` para el panel de BD.
* ``KNOWN_SCHEMA_DIVERGENCES`` — allowlist **explícita** con motivo y fecha. Se aplica
  igual en ``alembic check``/``--autogenerate`` (vía ``include_object``) y en el gate de
  drift. Una divergencia nueva (no listada) **sigue fallando**: la allowlist no es un
  «ignorar todo», es deuda declarada.

Regla de mantenimiento: para añadir una entrada hay que escribir el motivo y la fecha.
No se aceptan entradas anónimas ni comodines por patrón.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.sql.schema import MetaData, Table

from bolsa_application.database_maintenance import (
    SchemaContractSnapshot,
    SchemaExpectedConstraint,
)
from bolsa_infrastructure.database.models import Base

__all__ = [
    "KNOWN_SCHEMA_DIVERGENCES",
    "KnownSchemaDivergence",
    "SchemaContractAdapter",
    "alembic_include_object",
    "is_known_divergence",
    "known_divergence_names",
]

#: Fecha en la que se congeló esta allowlist. Si una entrada deja de ser cierta hay que
#: retirarla: la lista se revisa al tocar el esquema, no crece sola.
_ALLOWLIST_AS_OF = "2026-10-29"


@dataclass(frozen=True, slots=True)
class KnownSchemaDivergence:
    """Diferencia conocida entre ``Base.metadata`` y la BD real.

    ``object_type`` sigue la nomenclatura de ``include_object`` de Alembic
    (``table``, ``index``, ``check_constraint``, ``unique_constraint``, ``column``).
    ``None`` significa «cualquier tipo con ese nombre» (útil cuando índice y constraint
    comparten nombre).
    """

    name: str
    object_type: str | None
    reason: str
    table: str | None = None

    def describe(self) -> str:
        scope = f"{self.table}." if self.table else ""
        kind = self.object_type or "objeto"
        return f"{kind} {scope}{self.name}: {self.reason}"


KNOWN_SCHEMA_DIVERGENCES: tuple[KnownSchemaDivergence, ...] = (
    KnownSchemaDivergence(
        name="alembic_version",
        object_type="table",
        reason="tabla de control de Alembic, no forma parte de los metadatos de la app",
    ),
    KnownSchemaDivergence(
        name="custody_obligation",
        object_type="table",
        reason=(
            "tabla de 005 sustituida por custody_obligations (006); la migración decidió "
            "NO borrarla en upgrade y los metadatos solo conocen la nueva"
        ),
    ),
    KnownSchemaDivergence(
        name="auto_exit_orders_cycle_id_idx",
        object_type="index",
        table="auto_exit_orders",
        reason="índice creado fuera de la metadata histórica; sigue en uso por consultas de ciclo",
    ),
    KnownSchemaDivergence(
        name="decision_journal_entries_account_created_idx",
        object_type="index",
        table="decision_journal_entries",
        reason="índice histórico de cuenta+fecha; equivalente funcional a la consulta actual",
    ),
    KnownSchemaDivergence(
        name="decision_journal_entries_decision_id_idx",
        object_type="index",
        table="decision_journal_entries",
        reason="índice histórico; los metadatos declaran ix_decision_journal_entries_decision_id",
    ),
    KnownSchemaDivergence(
        name="ix_decision_journal_entries_decision_id",
        object_type="index",
        table="decision_journal_entries",
        reason="nombre declarado en metadata para el índice que la BD tiene con nombre histórico",
    ),
    KnownSchemaDivergence(
        name="decision_journal_entries_session_id_idx",
        object_type="index",
        table="decision_journal_entries",
        reason="índice histórico; los metadatos declaran ix_decision_journal_entries_session_id",
    ),
    KnownSchemaDivergence(
        name="ix_decision_journal_entries_session_id",
        object_type="index",
        table="decision_journal_entries",
        reason="nombre declarado en metadata para el índice que la BD tiene con nombre histórico",
    ),
    KnownSchemaDivergence(
        name="uq_decision_journal_entries_dedupe_key",
        object_type="index",
        table="decision_journal_entries",
        reason="unique index histórico de dedupe; la metadata no lo declara con ese nombre",
    ),
    KnownSchemaDivergence(
        name="ix_execution_events_status_updated_at",
        object_type="index",
        table="execution_events",
        reason="índice histórico de barrido por estado+fecha",
    ),
    KnownSchemaDivergence(
        name="ledger_entries_strategy_idx",
        object_type="index",
        table="ledger_entries",
        reason="índice histórico por estrategia; se conserva para no degradar consultas",
    ),
    KnownSchemaDivergence(
        name="signal_alert_subscriptions_account_id_idx",
        object_type="index",
        table="signal_alert_subscriptions",
        reason="índice histórico de propiedad por cuenta",
    ),
    KnownSchemaDivergence(
        name="sim_auto_positions_engine_updated_idx",
        object_type="index",
        table="sim_auto_positions",
        reason="índice histórico del motor AUTO por fecha de actualización",
    ),
    KnownSchemaDivergence(
        name="sim_auto_positions_strategy_idx",
        object_type="index",
        table="sim_auto_positions",
        reason="índice histórico por estrategia",
    ),
    KnownSchemaDivergence(
        name="instrument_strategy_tops_instrument_timeframe_uq",
        object_type=None,
        table="instrument_strategy_tops",
        reason=(
            "la BD lo materializa como índice único y la metadata como UniqueConstraint; "
            "mismo nombre y misma garantía"
        ),
    ),
    KnownSchemaDivergence(
        name="lifecycle_events_position_seq_uidx",
        object_type=None,
        table="lifecycle_events",
        reason="índice único en BD vs UniqueConstraint en metadata; misma garantía",
    ),
    KnownSchemaDivergence(
        name="lifecycle_outbox_transaction_id_uidx",
        object_type=None,
        table="lifecycle_outbox",
        reason="índice único en BD vs UniqueConstraint en metadata; misma garantía",
    ),
    KnownSchemaDivergence(
        name="live_orders_filled_bounds_check",
        object_type="check_constraint",
        table="live_orders",
        reason="CHECK de la migración 022 no declarado en metadata; la BD lo aplica",
    ),
    KnownSchemaDivergence(
        name="live_orders_filled_remaining_sum_check",
        object_type="check_constraint",
        table="live_orders",
        reason="CHECK de la migración 022 no declarado en metadata; la BD lo aplica",
    ),
    KnownSchemaDivergence(
        name="live_orders_quantity_pos_check",
        object_type="check_constraint",
        table="live_orders",
        reason="CHECK de la migración 022 no declarado en metadata; la BD lo aplica",
    ),
    KnownSchemaDivergence(
        name="live_orders_remaining_nonneg_check",
        object_type="check_constraint",
        table="live_orders",
        reason="CHECK de la migración 022 no declarado en metadata; la BD lo aplica",
    ),
)


def is_known_divergence(
    name: str | None,
    object_type: str | None,
    *,
    table: str | None = None,
) -> bool:
    """¿La diferencia está declarada? Sin nombre no se puede declarar nada."""
    if not name:
        return False
    for item in KNOWN_SCHEMA_DIVERGENCES:
        if item.name != name:
            continue
        if item.object_type is not None and object_type is not None:
            if item.object_type != object_type:
                continue
        if item.table is not None and table is not None and item.table != table:
            continue
        return True
    return False


def known_divergence_names() -> tuple[str, ...]:
    """Nombres declarados, en el formato que lee el panel (``tabla.nombre`` si aplica)."""
    return tuple(
        f"{item.table}.{item.name}" if item.table else item.name
        for item in KNOWN_SCHEMA_DIVERGENCES
    )


def _object_table_name(obj: object) -> str | None:
    table = getattr(obj, "table", None)
    name = getattr(table, "name", None)
    if isinstance(name, str):
        return name
    parent = getattr(obj, "parent", None)
    parent_name = getattr(parent, "name", None)
    return parent_name if isinstance(parent_name, str) else None


def alembic_include_object() -> Callable[[Any, str | None, str, bool, Any], bool]:
    """``include_object`` de Alembic: oculta la deuda declarada, no la desconocida.

    La firma es la que espera Alembic (``object, name, type_, reflected, compare_to``).
    Se aplica en ``alembic check`` y en ``--autogenerate``; una diferencia no listada
    sigue apareciendo y el gate falla.
    """

    def _include(
        obj: object,
        name: str | None,
        type_: str,
        reflected: bool,
        compare_to: object | None,
    ) -> bool:
        del reflected, compare_to
        if type_ == "table":
            return not is_known_divergence(name, type_)
        return not is_known_divergence(name, type_, table=_object_table_name(obj))

    return _include


def _expected_constraints(metadata: MetaData) -> tuple[SchemaExpectedConstraint, ...]:
    """Constraints con nombre que el código declara y deben existir en la BD.

    No incluye claves primarias ni foráneas: su nombre es un detalle del motor y
    compararlas produce ruido sin valor operativo.
    """
    items: list[SchemaExpectedConstraint] = []
    for table in metadata.tables.values():
        for constraint in table.constraints:
            if not isinstance(constraint, (CheckConstraint, UniqueConstraint)):
                continue
            name = getattr(constraint, "name", None)
            if not name:
                continue
            kind = (
                "check_constraint"
                if isinstance(constraint, CheckConstraint)
                else "unique_constraint"
            )
            items.append(
                SchemaExpectedConstraint(name=str(name), table=table.name, kind=kind)
            )
    return tuple(sorted(items, key=lambda item: (item.table, item.name)))


def _expected_columns(tables: Iterable[Table]) -> frozenset[tuple[str, str]]:
    return frozenset(
        (table.name, column.name) for table in tables for column in table.columns
    )


class SchemaContractAdapter:
    """Adaptador de ``SchemaContract`` sobre ``Base.metadata``."""

    def __init__(self, metadata: MetaData | None = None) -> None:
        self._metadata = metadata or Base.metadata

    def snapshot(self) -> SchemaContractSnapshot:
        tables: Sequence[Table] = tuple(self._metadata.tables.values())
        return SchemaContractSnapshot(
            expected_tables=frozenset(self._metadata.tables),
            expected_columns=_expected_columns(tables),
            expected_constraints=_expected_constraints(self._metadata),
            allowlisted=known_divergence_names(),
            source=f"metadatos SQLAlchemy (allowlist congelada {_ALLOWLIST_AS_OF})",
        )
