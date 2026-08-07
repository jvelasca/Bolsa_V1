"""Campaign manifest v0 + Repro+ (hashes / feature flags).

Se embebe en ``manifest_ref`` / se escribe a ``research/campaigns/*.json``.
No reescribe K histórico; solo formaliza metadatos en cierres nuevos.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
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
    """Use-case / tipo: Campaign Manifest 0 (+ Repro+ fields)."""
    campaign_id: str
    universe: str
    timeframe: str = "1d"
    engine: str = "h0"
    indicators_version: str | None = None
    git_commit: str | None = None
    git_dirty: bool | None = None
    python_version: str | None = None
    dataset_start: str | None = None
    dataset_end: str | None = None
    bar_count: int | None = None
    dataset_fingerprint: str | None = None
    feature_flags: dict[str, Any] = field(default_factory=dict)
    payload_hash: str | None = None
    costs: CampaignCosts = field(default_factory=CampaignCosts)
    presets: list[str] = field(default_factory=list)
    notes: str | None = None
    schema_version: str = CAMPAIGN_MANIFEST_SCHEMA
    created_at: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())
    # Q1.5 — CPU cost separado del ledger K (no altera k_contribution).
    cpu_cost_units: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_manifest_ref(self) -> dict[str, Any]:
        """Compacto para research_trials.manifest_ref."""
        ref = {
            "schemaVersion": self.schema_version,
            "campaign": self.campaign_id,
            "gitCommit": self.git_commit,
            "gitDirty": self.git_dirty,
            "pythonVersion": self.python_version,
            "engine": self.engine,
            "indicatorsVersion": self.indicators_version,
            "universe": self.universe,
            "timeframe": self.timeframe,
            "datasetStart": self.dataset_start,
            "datasetEnd": self.dataset_end,
            "barCount": self.bar_count,
            "datasetFingerprint": self.dataset_fingerprint,
            "featureFlags": dict(self.feature_flags or {}),
            "payloadHash": self.payload_hash,
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
        return ref


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


def resolve_git_dirty(repo_root: Path | None = None) -> bool | None:
    root = repo_root or Path(__file__).resolve().parents[5]
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
        return bool(out.strip())
    except (OSError, subprocess.SubprocessError):
        return None


def compute_dataset_fingerprint(
    *,
    universe: str,
    timeframe: str,
    dataset_start: str | None,
    dataset_end: str | None,
    bar_count: int | None,
    instrument_ids: list[str] | None = None,
) -> str:
    """SHA256 estable del universo/ventana (no del blob OHLCV completo)."""
    payload = {
        "universe": universe,
        "timeframe": timeframe,
        "datasetStart": dataset_start,
        "datasetEnd": dataset_end,
        "barCount": bar_count,
        "instrumentIds": sorted(instrument_ids or []),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_payload_hash(manifest_ref_without_hash: dict[str, Any]) -> str:
    """Hash del manifest_ref excluyendo payloadHash (anti-circular)."""
    cleaned = {k: v for k, v in manifest_ref_without_hash.items() if k != "payloadHash"}
    raw = json.dumps(cleaned, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def default_feature_flags_snapshot() -> dict[str, Any]:
    """Flags relevantes al experimento (Repro+). Best-effort desde Settings."""
    try:
        from bolsa_infrastructure.config import get_settings

        s = get_settings()
        return {
            "COST_MODEL_V2_ENABLED": bool(s.cost_model_v2_enabled),
            "CORE_R_CRON_ENABLED": bool(s.core_r_cron_enabled),
            "ESTUDIO_EOD_OPINION_ENABLED": bool(s.estudio_eod_opinion_enabled),
            "RISK_KILL_SWITCH": bool(s.risk_kill_switch),
            "PAPER_D_EXECUTE": False,  # env-only; default documentado off
        }
    except Exception:
        return {}


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
    instrument_ids: list[str] | None = None,
    feature_flags: dict[str, Any] | None = None,
    dataset_fingerprint: str | None = None,
) -> CampaignManifestV0:
    fp = dataset_fingerprint or compute_dataset_fingerprint(
        universe=universe,
        timeframe=timeframe,
        dataset_start=dataset_start,
        dataset_end=dataset_end,
        bar_count=bar_count,
        instrument_ids=instrument_ids,
    )
    m = CampaignManifestV0(
        campaign_id=campaign_id,
        universe=universe,
        timeframe=timeframe,
        engine=engine,
        indicators_version=indicators_version,
        git_commit=git_commit if git_commit is not None else resolve_git_commit(repo_root),
        git_dirty=resolve_git_dirty(repo_root),
        python_version=sys.version.split()[0],
        dataset_start=dataset_start,
        dataset_end=dataset_end,
        bar_count=bar_count,
        dataset_fingerprint=fp,
        feature_flags=dict(feature_flags if feature_flags is not None else default_feature_flags_snapshot()),
        costs=CampaignCosts(
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            spread_bps=spread_bps,
        ),
        presets=list(presets or []),
        notes=notes,
        cpu_cost_units=cpu_cost_units,
    )
    # payload_hash sobre el ref sin circularidad
    provisional = m.to_manifest_ref()
    m.payload_hash = compute_payload_hash(provisional)
    return m


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
