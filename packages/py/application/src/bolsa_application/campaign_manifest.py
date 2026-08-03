"""Campaign manifest v0 (Q0.2) — trazabilidad reproducible por campaña.

Se embebe en ``manifest_ref`` / se escribe a ``research/campaigns/*.json``.
No reescribe K histórico; solo formaliza metadatos en cierres nuevos.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CAMPAIGN_MANIFEST_SCHEMA = "campaign_manifest_v0"


@dataclass
class CampaignCosts:
    """Use-case / tipo: Campaign Costs."""
    commission_bps: int = 10
    slippage_bps: int = 5
    spread_bps: int = 2


@dataclass
class CampaignManifestV0:
    """Use-case / tipo: Campaign Manifest 0."""
    campaign_id: str
    universe: str
    timeframe: str = "1d"
    engine: str = "h0"
    indicators_version: str | None = None
    git_commit: str | None = None
    dataset_start: str | None = None
    dataset_end: str | None = None
    bar_count: int | None = None
    costs: CampaignCosts = field(default_factory=CampaignCosts)
    presets: list[str] = field(default_factory=list)
    notes: str | None = None
    schema_version: str = CAMPAIGN_MANIFEST_SCHEMA
    created_at: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())
    # Q1.5 — CPU cost separado del ledger K (no altera k_contribution).
    cpu_cost_units: float | None = None

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        return raw

    def to_manifest_ref(self) -> dict[str, Any]:
        """Compacto para research_trials.manifest_ref."""
        return {
            "schemaVersion": self.schema_version,
            "campaign": self.campaign_id,
            "gitCommit": self.git_commit,
            "engine": self.engine,
            "indicatorsVersion": self.indicators_version,
            "universe": self.universe,
            "timeframe": self.timeframe,
            "datasetStart": self.dataset_start,
            "datasetEnd": self.dataset_end,
            "barCount": self.bar_count,
            "costs": {
                "commissionBps": self.costs.commission_bps,
                "slippageBps": self.costs.slippage_bps,
                "spreadBps": self.costs.spread_bps,
            },
            "cpuCostUnits": self.cpu_cost_units,
            "createdAt": self.created_at,
            **({"notes": self.notes} if self.notes else {}),
            **({"presets": self.presets} if self.presets else {}),
        }


def resolve_git_commit(repo_root: Path | None = None) -> str | None:
    # .../packages/py/application/src/bolsa_application/campaign_manifest.py → repo root
    root = repo_root or Path(__file__).resolve().parents[5]
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        return out.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def build_campaign_manifest(
    *,
    campaign_id: str,
    universe: str,
    timeframe: str = "1d",
    engine: str = "h0",
    indicators_version: str | None = None,
    dataset_start: str | None = None,
    dataset_end: str | None = None,
    bar_count: int | None = None,
    commission_bps: int = 10,
    slippage_bps: int = 5,
    spread_bps: int = 2,
    presets: list[str] | None = None,
    notes: str | None = None,
    cpu_cost_units: float | None = None,
    git_commit: str | None = None,
    repo_root: Path | None = None,
) -> CampaignManifestV0:
    return CampaignManifestV0(
        campaign_id=campaign_id,
        universe=universe,
        timeframe=timeframe,
        engine=engine,
        indicators_version=indicators_version,
        git_commit=git_commit if git_commit is not None else resolve_git_commit(repo_root),
        dataset_start=dataset_start,
        dataset_end=dataset_end,
        bar_count=bar_count,
        costs=CampaignCosts(
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            spread_bps=spread_bps,
        ),
        presets=list(presets or []),
        notes=notes,
        cpu_cost_units=cpu_cost_units,
    )


def write_campaign_manifest(manifest: CampaignManifestV0, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def validate_campaign_manifest(data: dict[str, Any]) -> list[str]:
    """Checklist Q1.6 (parcial): campos mínimos del manifest v0."""
    errors: list[str] = []
    if data.get("schema_version") != CAMPAIGN_MANIFEST_SCHEMA and data.get("schemaVersion") != CAMPAIGN_MANIFEST_SCHEMA:
        # accept either snake (file) or already-normalized
        if data.get("schema_version") is None and data.get("schemaVersion") is None:
            errors.append("schema_version missing")
    campaign = data.get("campaign_id") or data.get("campaign")
    if not campaign:
        errors.append("campaign_id missing")
    if not data.get("universe"):
        errors.append("universe missing")
    if not data.get("engine"):
        errors.append("engine missing")
    if data.get("bar_count") is None and data.get("barCount") is None:
        errors.append("bar_count missing")
    costs = data.get("costs") or {}
    for key in ("commission_bps", "commissionBps"):
        if key in costs:
            break
    else:
        if not isinstance(costs, dict) or not costs:
            errors.append("costs missing")
    return errors
