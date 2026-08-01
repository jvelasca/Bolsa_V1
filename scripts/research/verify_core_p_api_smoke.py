#!/usr/bin/env python3
"""Optional live API smoke — CORE-P multi-perfil (cuenta ↔ declared ↔ política Coach/Lab).

Crea dos perfiles (low / high), los asigna a una cuenta, lee active-profile y
verifica que el contrato declared alimenta las invariantes CORE-P del front
(techo DD, Lab si débil, soft-bias espacio, familia Lab preferida).

SKIP if API down unless CORE_P_API_REQUIRED=1 or OPERATIVA_API_REQUIRED=1.

Usage (repo root, API en :8000):
  python scripts/research/verify_core_p_api_smoke.py
  CORE_P_API_REQUIRED=1 python scripts/research/verify_core_p_api_smoke.py

Mirror TS: apps/web/src/features/backtests/coach-profile-policy.ts
Doc: docs/engineering/profile-coach-lab-binding.md
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

# Windows consoles often use cp1252 — keep smoke prints ASCII-safe.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

API = os.environ.get("BOLSA_API_URL", "http://127.0.0.1:8000").rstrip("/")
REQUIRED = any(
    os.environ.get(k, "").strip().lower() in {"1", "true", "yes"}
    for k in ("CORE_P_API_REQUIRED", "OPERATIVA_API_REQUIRED")
)

# Invariantes espejo de resolveCoachProfilePolicy / preferredLabFamiliesForHorizon
POLICY_BY_RISK: dict[str, dict[str, Any]] = {
    "low": {
        "allowLabIfWeak": False,
        "maxDrawdownSoftPct": 18,
        "spaceWidthFactor": 0.75,
    },
    "moderate": {
        "allowLabIfWeak": False,
        "maxDrawdownSoftPct": 28,
        "spaceWidthFactor": 1.0,
    },
    "high": {
        "allowLabIfWeak": True,
        "maxDrawdownSoftPct": 40,
        "spaceWidthFactor": 1.35,
    },
}

# Horizonte → primera familia Lab (mismo mapa CATEGORY_TO_LAB del front)
FIRST_LAB_FAMILY_BY_HORIZON: dict[str, str] = {
    "intraday": "rsi_mean_reversion",
    "swing": "sma_crossover",
    "position": "sma_crossover",
    "long_term": "sma_crossover",
}


def _request(
    method: str, path: str, body: dict[str, Any] | None = None
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = None
        return exc.code, parsed
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"API unreachable: {exc}") from exc


def _unwrap(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _first_account_id(payload: Any) -> str | None:
    rows = _unwrap(payload)
    if not isinstance(rows, list) or not rows:
        return None
    row = rows[0]
    if not isinstance(row, dict):
        return None
    return row.get("id") or row.get("accountId")


def _policy_from_declared(declared: dict[str, Any]) -> dict[str, Any]:
    risk = declared.get("riskTolerance") or declared.get("risk_tolerance")
    horizon = declared.get("horizon")
    if risk not in POLICY_BY_RISK:
        raise RuntimeError(f"riskTolerance inesperado: {risk!r}")
    pol = dict(POLICY_BY_RISK[risk])
    pol["riskTolerance"] = risk
    pol["horizon"] = horizon
    pol["firstLabFamily"] = FIRST_LAB_FAMILY_BY_HORIZON.get(str(horizon), "sma_crossover")
    return pol


def _create_profile(name: str, horizon: str, risk: str) -> str:
    status, body = _request(
        "POST",
        "/api/investor-profiles",
        {
            "name": name,
            "horizon": horizon,
            "objectives": ["preservation"] if risk == "low" else ["growth"],
            "riskTolerance": risk,
            "experience": "intermediate",
            "notes": "CORE-P API smoke · auto-delete",
        },
    )
    if status not in (200, 201):
        raise RuntimeError(f"create profile HTTP {status}: {body}")
    data = _unwrap(body)
    pid = data.get("profileId") if isinstance(data, dict) else None
    if not pid:
        raise RuntimeError(f"create profile sin profileId: {body}")
    return str(pid)


def _delete_profile(profile_id: str) -> None:
    status, _ = _request("DELETE", f"/api/investor-profiles/{profile_id}")
    if status not in (200, 204, 404):
        print(f"WARN: delete profile {profile_id} HTTP {status}")


def _assign(account_id: str, profile_id: str | None) -> None:
    status, body = _request(
        "PUT",
        f"/api/accounts/{account_id}/active-profile",
        {"profileId": profile_id},
    )
    if status != 200:
        raise RuntimeError(f"assign active-profile HTTP {status}: {body}")


def _get_active(account_id: str) -> dict[str, Any]:
    status, body = _request("GET", f"/api/accounts/{account_id}/active-profile")
    if status != 200:
        raise RuntimeError(f"get active-profile HTTP {status}: {body}")
    data = _unwrap(body)
    if not isinstance(data, dict):
        raise RuntimeError("active-profile payload missing")
    return data


def _assert_profile_roundtrip(label: str, data: dict[str, Any], expect_risk: str, expect_horizon: str) -> None:
    declared = data.get("declared")
    if not isinstance(declared, dict):
        raise RuntimeError(f"{label}: declared missing")
    risk = declared.get("riskTolerance")
    horizon = declared.get("horizon")
    if risk != expect_risk:
        raise RuntimeError(f"{label}: riskTolerance={risk!r} esperado {expect_risk!r}")
    if horizon != expect_horizon:
        raise RuntimeError(f"{label}: horizon={horizon!r} esperado {expect_horizon!r}")
    pol = _policy_from_declared(declared)
    print(
        f"OK {label}: profileId={data.get('profileId')} risk={risk} "
        f"horizon={horizon} ddSoft={pol['maxDrawdownSoftPct']} "
        f"labIfWeak={pol['allowLabIfWeak']} spacex{pol['spaceWidthFactor']} "
        f"labFamily={pol['firstLabFamily']}"
    )
    if expect_risk == "low":
        assert pol["allowLabIfWeak"] is False
        assert pol["maxDrawdownSoftPct"] == 18
        assert pol["spaceWidthFactor"] == 0.75
        assert pol["firstLabFamily"] == "sma_crossover"
    if expect_risk == "high":
        assert pol["allowLabIfWeak"] is True
        assert pol["maxDrawdownSoftPct"] == 40
        assert pol["spaceWidthFactor"] == 1.35
        assert pol["firstLabFamily"] == "rsi_mean_reversion"


def main() -> int:
    print("=== verify_core_p_api_smoke ===")
    print(f"API={API} required={REQUIRED}")
    created: list[str] = []
    account_id: str | None = None
    previous_profile_id: str | None = None

    try:
        try:
            status, health = _request("GET", "/api/health")
        except RuntimeError as exc:
            msg = f"SKIP: {exc}"
            print(msg)
            return 1 if REQUIRED else 0
        if status != 200:
            raise RuntimeError(f"health HTTP {status}")
        print(f"OK health: {health if isinstance(health, dict) else status}")

        status, accounts = _request("GET", "/api/accounts")
        if status != 200:
            raise RuntimeError(f"accounts HTTP {status}")
        account_id = _first_account_id(accounts)
        if not account_id:
            print("SKIP: no accounts")
            return 0 if not REQUIRED else 1
        print(f"OK account: {account_id}")

        # Ensure defaults so DB has catalog; ignore result shape.
        status_ed, _ = _request("POST", "/api/investor-profiles/ensure-defaults")
        print(f"OK ensure-defaults HTTP {status_ed}")

        # Remember previous active profile for restore.
        status_prev, prev_body = _request(
            "GET", f"/api/accounts/{account_id}/active-profile"
        )
        if status_prev == 200:
            prev = _unwrap(prev_body)
            if isinstance(prev, dict):
                previous_profile_id = prev.get("profileId")
                print(f"OK previous activeProfileId={previous_profile_id}")
        else:
            print(f"OK previous active-profile HTTP {status_prev} (none)")

        stamp = int(time.time())
        low_id = _create_profile(
            f"CORE-P smoke low {stamp}", horizon="long_term", risk="low"
        )
        created.append(low_id)
        high_id = _create_profile(
            f"CORE-P smoke high {stamp}", horizon="intraday", risk="high"
        )
        created.append(high_id)
        print(f"OK created profiles low={low_id} high={high_id}")

        _assign(account_id, low_id)
        active_low = _get_active(account_id)
        if active_low.get("profileId") != low_id:
            raise RuntimeError("active profile no cambió a low")
        _assert_profile_roundtrip("low->active", active_low, "low", "long_term")

        _assign(account_id, high_id)
        active_high = _get_active(account_id)
        if active_high.get("profileId") != high_id:
            raise RuntimeError("active profile no cambió a high")
        _assert_profile_roundtrip("high->active", active_high, "high", "intraday")

        # Mismatch stamp (simula Finalistas de low con cuenta en high).
        if low_id == high_id:
            raise RuntimeError("profile ids no deben coincidir")
        print(
            f"OK mismatch simulable: stamped={low_id} active={high_id} "
            "(Front: activeTopProfileMismatch)"
        )

        print("PASS CORE-P multi-perfil live")
        return 0
    except Exception as exc:  # noqa: BLE001 — smoke script
        print(f"FAIL: {exc}")
        return 1
    finally:
        if account_id is not None:
            try:
                if previous_profile_id:
                    _assign(account_id, previous_profile_id)
                    print(f"OK restored activeProfileId={previous_profile_id}")
                elif created:
                    # Dejar un perfil no-smoke si no había previo: unassign not
                    # always supported; assign first remaining catalog profile.
                    status, listed = _request("GET", "/api/investor-profiles")
                    rows = _unwrap(listed) if status == 200 else []
                    fallback = None
                    if isinstance(rows, list):
                        for row in rows:
                            if (
                                isinstance(row, dict)
                                and row.get("profileId") not in created
                            ):
                                fallback = row.get("profileId")
                                break
                    if fallback:
                        _assign(account_id, str(fallback))
                        print(f"OK fallback activeProfileId={fallback}")
            except Exception as restore_exc:  # noqa: BLE001
                print(f"WARN restore active-profile: {restore_exc}")
        for pid in created:
            _delete_profile(pid)
        if created:
            print(f"OK cleaned {len(created)} smoke profiles")


if __name__ == "__main__":
    sys.exit(main())
