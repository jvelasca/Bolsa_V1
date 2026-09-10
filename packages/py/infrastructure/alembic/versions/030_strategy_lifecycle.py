"""V2.25 / A10 — Strategy Lifecycle: candidatas, versiones, evaluaciones, promociones y salud.

Crea las tablas del ciclo de vida autónomo de estrategia:

* ``strategy_candidates`` — semilla ESTUDIO→LAB (reproducible por ``data_snapshot_id``).
* ``strategy_versions`` — versión INMUTABLE (finalista/promocionada), única por
  ``(candidate_id, definition_hash)``.
* ``strategy_evaluations`` — evaluación de LABORATORIO (score + gates + evidencia).
* ``strategy_promotions`` — promoción/rechazo con motivos auditables.
* ``strategy_health_snapshots`` — serie temporal de vigilancia de una estrategia activa.

La evidencia pesada (``research_trials``/``research_evidence``/``edge_reports``) NO se
duplica: se referencia por id (``trial_ids``/``edge_report_id``/``optimization_run_id``).
``strategy_definitions`` sigue siendo la definición ejecutable.

Convenciones: ``String`` para ids/estados (sin ENUM DDL), ``JSONB`` para blobs
flexibles, ``Numeric``/``Float`` según el caso, y guards idempotentes
``_table_exists``/``_index_exists`` (offline-safe).

Cadena lineal: ``down_revision = "029_sim_auto_pos_account_scope"``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "030_strategy_lifecycle"
down_revision = "029_sim_auto_pos_account_scope"
branch_labels = None
depends_on = None


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    sql = (
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :t"
    )
    return bind.scalar(sa.text(sql), {"t": table_name}) is not None


def _index_exists(bind: sa.engine.Connection, index_name: str) -> bool:
    sql = "SELECT 1 FROM pg_indexes WHERE schemaname = 'public' AND indexname = :n"
    return bind.scalar(sa.text(sql), {"n": index_name}) is not None


def upgrade() -> None:
    bind = op.get_bind()

    if not _table_exists(bind, "strategy_candidates"):
        op.create_table(
            "strategy_candidates",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("instrument_id", sa.String(), nullable=False),
            sa.Column("strategy_family", sa.String(), nullable=False),
            sa.Column("params", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("origin", sa.String(), nullable=False, server_default="estudio"),
            sa.Column("data_snapshot_id", sa.String(), nullable=True),
            sa.Column("preset_key", sa.String(), nullable=True),
            sa.Column("strategy_definition_id", sa.String(), nullable=True),
            sa.Column("state", sa.String(), nullable=False, server_default="estudio"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "strategy_candidates_instrument_family_idx",
            "strategy_candidates",
            ["instrument_id", "strategy_family"],
        )

    if not _table_exists(bind, "strategy_versions"):
        op.create_table(
            "strategy_versions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("candidate_id", sa.String(), nullable=False),
            sa.Column("instrument_id", sa.String(), nullable=False),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("definition_hash", sa.String(), nullable=False),
            sa.Column("definition", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("is_finalist", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint(
                "candidate_id", "definition_hash", name="strategy_versions_candidate_hash_uq"
            ),
        )

    if not _table_exists(bind, "strategy_evaluations"):
        op.create_table(
            "strategy_evaluations",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("candidate_id", sa.String(), nullable=False),
            sa.Column("instrument_id", sa.String(), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("gates", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("trial_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
            sa.Column("optimization_run_id", sa.String(), nullable=True),
            sa.Column("edge_report_id", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "strategy_evaluations_candidate_idx", "strategy_evaluations", ["candidate_id"]
        )

    if not _table_exists(bind, "strategy_promotions"):
        op.create_table(
            "strategy_promotions",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("finalist_id", sa.String(), nullable=False),
            sa.Column("candidate_id", sa.String(), nullable=False),
            sa.Column("instrument_id", sa.String(), nullable=False),
            sa.Column("promoted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("reasons", postgresql.JSONB(), nullable=False, server_default="[]"),
            sa.Column(
                "shadow_validated", sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
            sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "strategy_promotions_finalist_idx", "strategy_promotions", ["finalist_id"]
        )

    if not _table_exists(bind, "strategy_health_snapshots"):
        op.create_table(
            "strategy_health_snapshots",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("version_id", sa.String(), nullable=False),
            sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
            sa.Column("edge", sa.Float(), nullable=True),
            sa.Column("walk_forward_efficiency", sa.Float(), nullable=True),
            sa.Column("dsr", sa.Float(), nullable=True),
            sa.Column("credibility", sa.Float(), nullable=True),
            sa.Column("thresholds", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("degraded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index(
            "strategy_health_version_asof_idx", "strategy_health_snapshots", ["version_id", "as_of"]
        )


def downgrade() -> None:
    bind = op.get_bind()

    if _table_exists(bind, "strategy_health_snapshots"):
        if _index_exists(bind, "strategy_health_version_asof_idx"):
            op.drop_index(
                "strategy_health_version_asof_idx", table_name="strategy_health_snapshots"
            )
        op.drop_table("strategy_health_snapshots")

    if _table_exists(bind, "strategy_promotions"):
        if _index_exists(bind, "strategy_promotions_finalist_idx"):
            op.drop_index("strategy_promotions_finalist_idx", table_name="strategy_promotions")
        op.drop_table("strategy_promotions")

    if _table_exists(bind, "strategy_evaluations"):
        if _index_exists(bind, "strategy_evaluations_candidate_idx"):
            op.drop_index("strategy_evaluations_candidate_idx", table_name="strategy_evaluations")
        op.drop_table("strategy_evaluations")

    if _table_exists(bind, "strategy_versions"):
        op.drop_table("strategy_versions")

    if _table_exists(bind, "strategy_candidates"):
        if _index_exists(bind, "strategy_candidates_instrument_family_idx"):
            op.drop_index(
                "strategy_candidates_instrument_family_idx", table_name="strategy_candidates"
            )
        op.drop_table("strategy_candidates")
