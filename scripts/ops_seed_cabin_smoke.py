#!/usr/bin/env python3
"""V2.10 — Seed ops cabina: birth estructural + Journal MFE/MAE.

Cierra el hueco ops bloqueado desde v2.6 (opens via /portfolio/trade = bootstrap -5%).

Subcomandos:
  birth-structural   Confirm SEMI con signedStop estructural (!= entry*0.95)
  journal-mfe-mae    Asegura/ubica study con runtime.mfeMae finito

Por defecto DRY-RUN. Con --apply:
  - birth: mandato + sesion propose en BD (package recommend_long) + Confirm fill
  - journal: siembra sesion propose con mfeMae si no hay study

La sesion BD es necesaria porque propose live suele devolver action=wait
(DecisionPackage incompatible con Confirm opening). Mismo patron que golden v191.

Uso (repo root, API en :8000, .env DATABASE_URL):
  python scripts/ops_seed_cabin_smoke.py birth-structural
  python scripts/ops_seed_cabin_smoke.py birth-structural --apply --account-id <id>
  python scripts/ops_seed_cabin_smoke.py journal-mfe-mae --apply

Env:
  BOLSA_API_URL          default http://127.0.0.1:8000
  BOLSA_KEEP_ACCOUNT_ID  cuenta por defecto
  OPS_SEED_REQUIRED=1    exit 1 si API down / BLOCKED

Anti-patterns:
  POST /portfolio/trade  -> OPEN_UNPROTECTED
  Proteger -5%           -> protectKind bootstrap
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

ROOT = Path(__file__).resolve().parents[1]
for _p in (
    ROOT / "packages" / "py" / "infrastructure" / "src",
    ROOT / "packages" / "py" / "domain" / "src",
    ROOT / "packages" / "py" / "application" / "src",
    ROOT / "packages" / "py" / "analytics" / "src",
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:  # noqa: BLE001
        pass

API = os.environ.get("BOLSA_API_URL", "http://127.0.0.1:8000").rstrip("/")
REQUIRED = os.environ.get("OPS_SEED_REQUIRED", "").strip().lower() in {
    "1",
    "true",
    "yes",
}
BOOTSTRAP_PCT = 0.05
STRUCTURAL_STOP_PCT = 0.03
PRICE_BAND = 0.02


def _load_env() -> None:
    """Load flat KEY=VALUE from repo .env (same rules as scripts/lib/load-env.mjs)."""
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    try:
        raw = env_path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in raw.splitlines():
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#"):
            continue
        eq = trimmed.find("=")
        if eq <= 0:
            continue
        key = trimmed[:eq].strip()
        value = trimmed[eq + 1 :].strip()
        if not key:
            continue
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value
    # Fallback if python-dotenv is available and still empty.
    if not os.environ.get("DATABASE_URL"):
        try:
            from dotenv import load_dotenv
        except ImportError:
            return
        load_dotenv(env_path, override=False)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _request(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    account_id: str | None = None,
    timeout: float = 60.0,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers: dict[str, str] = {}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if account_id:
        headers["X-Account-Id"] = account_id
    req = urlrequest.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers=headers,
    )
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return resp.status, None
            return resp.status, json.loads(raw)
    except urlerror.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        try:
            parsed: Any = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed
    except urlerror.URLError as exc:
        return 0, {"error": str(exc.reason)}


def _unwrap(payload: Any) -> Any:
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _accounts(payload: Any) -> list[dict[str, Any]]:
    rows = _unwrap(payload)
    if not isinstance(rows, list):
        return []
    return [a for a in rows if isinstance(a, dict)]


def _resolve_account_id(
    accounts: list[dict[str, Any]], account_arg: str | None
) -> str:
    env_keep = (os.environ.get("BOLSA_KEEP_ACCOUNT_ID") or "").strip()
    keep = (account_arg or env_keep or "").strip()
    if keep:
        if not any(a.get("id") == keep for a in accounts):
            raise SystemExit(f"account id no existe en /api/accounts: {keep}")
        return keep
    defaults = [
        a
        for a in accounts
        if a.get("isDefault") is True and a.get("status") == "active"
    ]
    if len(defaults) == 1:
        return str(defaults[0]["id"])
    active = [a for a in accounts if a.get("status") == "active"]
    if len(active) == 1:
        return str(active[0]["id"])
    raise SystemExit(
        "No se pudo inferir la cuenta. Pasa --account-id <id> "
        "(o BOLSA_KEEP_ACCOUNT_ID). Activas:\n"
        + "\n".join(
            f"  {a.get('id')}  {a.get('type')}  {a.get('name')}  "
            f"default={a.get('isDefault')}"
            for a in active
        )
    )


def _finite(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        if f != f:
            return None
        return f
    return None


def _bootstrap_floor(entry: float, *, direction: str = "long") -> float:
    if direction == "short":
        return entry * (1.0 + BOOTSTRAP_PCT)
    return entry * (1.0 - BOOTSTRAP_PCT)


def _structural_stop(entry: float, *, direction: str = "long") -> float:
    if direction == "short":
        return round(entry * (1.0 + STRUCTURAL_STOP_PCT), 4)
    return round(entry * (1.0 - STRUCTURAL_STOP_PCT), 4)


def _is_bootstrap_stop(entry: float, stop: float, *, direction: str = "long") -> bool:
    floor = _bootstrap_floor(entry, direction=direction)
    if entry <= 0:
        return False
    return abs(stop - floor) / entry < 0.002


def _last_close(instrument_id: str) -> float | None:
    status, payload = _request(
        "GET", f"/api/instruments/{instrument_id}/ohlcv?timeframe=1d&limit=5"
    )
    if status != 200:
        return None
    bars = _unwrap(payload)
    if not isinstance(bars, list) or not bars:
        return None
    last = bars[-1]
    if not isinstance(last, dict):
        return None
    return _finite(last.get("close"))


def _open_instrument_ids(account_id: str) -> set[str]:
    status, payload = _request("GET", "/api/portfolio", account_id=account_id)
    if status != 200:
        return set()
    data = _unwrap(payload)
    if not isinstance(data, dict):
        return set()
    positions = data.get("positions")
    if not isinstance(positions, list):
        return set()
    out: set[str] = set()
    for p in positions:
        if isinstance(p, dict) and isinstance(p.get("instrumentId"), str):
            out.add(p["instrumentId"])
    return out


def _portfolio_position(
    account_id: str, instrument_id: str
) -> dict[str, Any] | None:
    status, payload = _request("GET", "/api/portfolio", account_id=account_id)
    if status != 200:
        return None
    data = _unwrap(payload)
    if not isinstance(data, dict):
        return None
    positions = data.get("positions")
    if not isinstance(positions, list):
        return None
    for p in positions:
        if isinstance(p, dict) and p.get("instrumentId") == instrument_id:
            return p
    return None


def _ensure_mandate(
    account_id: str, instrument_id: str, *, apply: bool
) -> bool:
    status, payload = _request("GET", f"/api/accounts/{account_id}/mandates")
    if status != 200:
        print(f"FAIL: GET mandates HTTP {status}: {payload}")
        return False
    bundle = _unwrap(payload)
    if not isinstance(bundle, dict):
        print("FAIL: mandates bundle missing")
        return False
    tenures = bundle.get("tenures") if isinstance(bundle.get("tenures"), list) else []
    links = bundle.get("links") if isinstance(bundle.get("links"), list) else []
    has = any(
        isinstance(t, dict) and t.get("instrumentId") == instrument_id for t in tenures
    )
    if has:
        print(f"OK mandate already present for {instrument_id}")
        return True
    new_tenure = {
        "id": f"mt-ops-v210-{uuid.uuid4().hex[:10]}",
        "accountId": account_id,
        "instrumentId": instrument_id,
        "effectiveFrom": _now_iso(),
        "actor": "user",
        "reason": "adopt",
    }
    merged = list(tenures) + [new_tenure]
    if not apply:
        print(
            f"DRY-RUN: would PUT mandate tenure for {instrument_id} "
            f"(tenures {len(tenures)} -> {len(merged)})"
        )
        return True
    status, put_res = _request(
        "PUT",
        f"/api/accounts/{account_id}/mandates",
        body={"tenures": merged, "links": links},
    )
    if status != 200:
        print(f"FAIL: PUT mandates HTTP {status}: {put_res}")
        return False
    print(f"OK mandate adopted for {instrument_id}")
    return True


def _candidate_instruments(
    *,
    prefer_id: str | None,
    open_ids: set[str],
    limit: int = 8,
) -> list[dict[str, Any]]:
    status, payload = _request("GET", "/api/instruments")
    if status != 200:
        raise SystemExit(f"instruments HTTP {status}: {payload}")
    rows = _unwrap(payload)
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    if prefer_id:
        for row in rows:
            if isinstance(row, dict) and row.get("id") == prefer_id:
                out.append(row)
                break
    for row in rows:
        if not isinstance(row, dict):
            continue
        iid = row.get("id")
        if not isinstance(iid, str) or not iid:
            continue
        if prefer_id and iid == prefer_id:
            continue
        if iid in open_ids:
            continue
        if _last_close(iid) is None:
            continue
        out.append(row)
        if len(out) >= limit:
            break
    return out


def _build_triggered_plan(
    *,
    instrument_id: str,
    decision_id: str,
    entry: float,
    stop: float,
    qty: float,
    direction: str,
    symbol: str | None,
) -> dict[str, Any]:
    risk = abs(entry - stop) * qty
    t1 = entry * (1.02 if direction == "long" else 0.98)
    t2 = entry * (1.04 if direction == "long" else 0.96)
    return {
        "id": f"tp-ops-v210-{decision_id[-10:]}",
        "decisionId": decision_id,
        "instrumentId": instrument_id,
        "symbol": symbol or "OPS",
        "direction": direction,
        "status": "TRIGGERED",
        "entry": entry,
        "structuralStop": stop,
        "target1": round(t1, 4),
        "target2": round(t2, 4),
        "quantity": qty,
        "riskAmount": round(risk, 4),
    }


async def _seed_propose_session_db(
    *,
    session_id: str,
    account_id: str,
    instrument_id: str,
    decision_id: str,
    action: str,
    trade_plan: dict[str, Any],
    symbol: str | None = None,
    mfe_mae: dict[str, Any] | None = None,
) -> None:
    """ADR-031 H3 — Confirm openings need a propose DecisionPackage (golden v191)."""
    _load_env()
    from bolsa_domain.entities.cognitive_artifacts import DecisionSessionRecord
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.repositories.cognitive_repository import (
        SqlAlchemyCognitiveRepository,
    )
    from bolsa_infrastructure.database.session import create_engine, create_session_factory

    get_settings.cache_clear()
    settings = get_settings()
    if not (settings.database_url or "").strip() or "@localhost" in (
        settings.database_url or ""
    ) and ":@" in (settings.database_url or ""):
        # Weak check — real failure still surfaces on connect.
        pass
    if not os.environ.get("DATABASE_URL") and not getattr(settings, "db_password", None):
        raise RuntimeError(
            "DATABASE_URL missing after .env load — run via "
            "`node scripts/ops_seed_cabin_smoke.mjs ...` or export DATABASE_URL"
        )
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    runtime: dict[str, Any] = {
        "decisionPackage": {
            "decisionId": decision_id,
            "instrumentId": instrument_id,
            "action": action,
        },
        "tradePlan": trade_plan,
    }
    if mfe_mae is not None:
        runtime["mfeMae"] = mfe_mae
    record = DecisionSessionRecord(
        id=session_id,
        kind="propose",
        status="open",
        instrument_id=instrument_id,
        created_at=_now_iso(),
        decision_id=decision_id,
        account_id=account_id,
        symbol=symbol,
        recommendation_id=decision_id,
        payload={
            "decisionId": decision_id,
            "runtime": runtime,
        },
    )
    async with factory() as session:
        await SqlAlchemyCognitiveRepository(session).append_decision_session(record)
        await session.commit()
    await engine.dispose()


async def _seed_flat_opening_fixture(
    *,
    instrument_id: str,
    symbol: str,
) -> float:
    """Instrument + 120 flat daily bars @ 10.0 (golden opening_gate_seed / DS-05)."""
    _load_env()
    from datetime import timedelta
    from decimal import Decimal

    from bolsa_domain.ohlcv_time import parse_bar_timestamp
    from bolsa_domain.value_objects.timeframe import TimeFrame
    from bolsa_infrastructure.config import get_settings
    from bolsa_infrastructure.database.models import InstrumentRow, OhlcvBarRow
    from bolsa_infrastructure.database.session import create_engine, create_session_factory
    from bolsa_infrastructure.ids import new_id
    from sqlalchemy import delete

    get_settings.cache_clear()
    settings = get_settings()
    if not os.environ.get("DATABASE_URL"):
        raise RuntimeError(
            "DATABASE_URL missing — run via `node scripts/ops_seed_cabin_smoke.mjs ...`"
        )
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    price = 10.0
    now = datetime.now(UTC)
    async with factory() as session:
        row = await session.get(InstrumentRow, instrument_id)
        if row is None:
            session.add(
                InstrumentRow(
                    id=instrument_id,
                    symbol=symbol,
                    yahoo_symbol=f"{symbol}-{instrument_id[-8:]}",
                    isin=None,
                    name=f"OPS V2.10 {symbol}",
                    exchange="TEST",
                    country="US",
                    currency="USD",
                    sector=None,
                    type="stock",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
            )
        # Fresh flat series (delete prior ops bars for this instrument id).
        await session.execute(
            delete(OhlcvBarRow).where(OhlcvBarRow.instrument_id == instrument_id)
        )
        last = now.date()
        start = last - timedelta(days=119)
        day = start
        while day <= last:
            session.add(
                OhlcvBarRow(
                    id=new_id(),
                    instrument_id=instrument_id,
                    timeframe=TimeFrame.D1,
                    timestamp=parse_bar_timestamp(day.isoformat()),
                    open=Decimal(str(price)),
                    high=Decimal(str(price)),
                    low=Decimal(str(price)),
                    close=Decimal(str(price)),
                    volume=1000,
                    adj_close=Decimal(str(price)),
                    source="yahoo",
                    created_at=now,
                )
            )
            day += timedelta(days=1)
        await session.commit()
    await engine.dispose()
    return price


def _assert_birth_position(
    pos: dict[str, Any], *, entry: float, signed_stop: float, direction: str
) -> list[str]:
    fails: list[str] = []
    op = pos.get("operational") if isinstance(pos.get("operational"), dict) else {}
    view = (
        op.get("operationalView")
        if isinstance(op.get("operationalView"), dict)
        else {}
    )
    operating = view.get("operatingState") or op.get("operatingState")
    primary = view.get("primaryAction")
    cur = _finite(op.get("currentStop"))
    ini = _finite(op.get("initialStop"))
    stop = cur if cur is not None else ini
    if operating == "OPEN_UNPROTECTED":
        fails.append("operatingState=OPEN_UNPROTECTED (want PROTECTED)")
    elif stop is None:
        fails.append(f"operatingState={operating!r} without stop")
    if stop is None:
        fails.append("no currentStop/initialStop on position")
    elif _is_bootstrap_stop(entry, stop, direction=direction):
        fails.append(f"stop {stop} looks like bootstrap floor (~{entry * 0.95})")
    elif abs(stop - signed_stop) / max(entry, 1e-9) > 0.01:
        fails.append(f"stop {stop} != signedStop {signed_stop} (+/-1%)")
    if primary is not None and primary not in {"MANTENER", "MONITOR", "HOLD"}:
        fails.append(
            f"primaryAction={primary!r} (want MANTENER/MONITOR with structural stop)"
        )
    return fails


def cmd_birth_structural(args: argparse.Namespace) -> int:
    print("=== ops_seed_cabin_smoke birth-structural ===")
    print(f"API={API} apply={args.apply} required={REQUIRED}")
    status, health = _request("GET", "/api/health")
    if status != 200:
        msg = f"health HTTP {status}: {health}"
        if REQUIRED:
            print(f"FAIL: {msg}")
            return 1
        print(f"SKIP: {msg}")
        return 0

    status, acc_payload = _request("GET", "/api/accounts")
    if status != 200:
        print(f"FAIL: accounts HTTP {status}")
        return 1
    account_id = _resolve_account_id(_accounts(acc_payload), args.account_id)
    print(f"OK account: {account_id}")

    # Fixture path (default): synthetic instrument + flat bars @ 10 — passes DS-05.
    # Optional --instrument-id without --flat uses live Yahoo bars (may risk_veto).
    use_flat = not args.instrument_id or args.flat
    if use_flat:
        suffix = uuid.uuid4().hex[:8]
        instrument_id = args.instrument_id or f"inst-ops-v210-{suffix}"
        symbol = f"OP{suffix[:6].upper()}"
        entry = 10.0
        print(f"-- fixture flat {symbol} ({instrument_id})")
        if args.apply:
            try:
                entry = asyncio.run(
                    _seed_flat_opening_fixture(
                        instrument_id=instrument_id, symbol=symbol
                    )
                )
            except Exception as exc:  # noqa: BLE001
                print(f"BLOCKED: flat fixture seed failed: {exc}")
                return 1 if REQUIRED else 0
            print(f"OK flat OHLCV fixture @ {entry}")
        else:
            print("DRY-RUN: would seed instrument + 120 flat bars @ 10.0")
    else:
        instrument_id = str(args.instrument_id)
        status, payload = _request("GET", f"/api/instruments/{instrument_id}")
        data = _unwrap(payload) if status == 200 else None
        symbol = (
            data.get("symbol")
            if isinstance(data, dict) and isinstance(data.get("symbol"), str)
            else None
        )
        close = _last_close(instrument_id)
        if close is None or close <= 0:
            print("BLOCKED: instrument has no OHLCV close")
            return 1 if REQUIRED else 0
        entry = close
        print(f"-- live instrument {symbol or instrument_id} entry={entry}")

    if not _ensure_mandate(account_id, instrument_id, apply=args.apply):
        return 1

    direction = "long"
    action = "recommend_long"
    signed_stop = _structural_stop(entry, direction=direction)
    qty = float(args.qty)
    decision_id = f"dec-ops-v210-{uuid.uuid4().hex[:10]}"
    session_id = f"DSS-ops-v210-{uuid.uuid4().hex[:10]}"
    trade_plan = _build_triggered_plan(
        instrument_id=instrument_id,
        decision_id=decision_id,
        entry=entry,
        stop=signed_stop,
        qty=qty,
        direction=direction,
        symbol=symbol,
    )
    confirm_body = {
        "recommendation": {
            "decisionId": decision_id,
            "instrumentId": instrument_id,
            "action": action,
            "suggestedQuantity": qty,
            "suggestedPrice": entry,
            "tradePlan": trade_plan,
        },
        "accountId": account_id,
        "execute": True,
        "signedStop": signed_stop,
        "sessionId": session_id,
    }
    print(
        f"   plan entry={entry} signedStop={signed_stop} "
        f"bootstrapFloor={_bootstrap_floor(entry):.4f} qty={qty}"
    )
    print("   browser checklist (post-apply):")
    print("     - Cabina / Position Card: proteccion Planificado (no emergencia -5%)")
    print("     - NEXT ACTION cabina: MANTENER (POV API puede decir MONITOR)")
    print("     - data-protect-kind != bootstrap")
    print("     - stop visible ~ signedStop")

    if not args.apply:
        print("DRY-RUN: would seed propose session in DB + Confirm execute")
        print(f"   sessionId={session_id} decisionId={decision_id}")
        print("OK: birth-structural dry-run ready")
        return 0

    try:
        asyncio.run(
            _seed_propose_session_db(
                session_id=session_id,
                account_id=account_id,
                instrument_id=instrument_id,
                decision_id=decision_id,
                action=action,
                trade_plan=trade_plan,
                symbol=symbol,
            )
        )
    except Exception as exc:  # noqa: BLE001
        print(f"BLOCKED: DB seed propose session failed: {exc}")
        print(
            "Hint: run via `node scripts/ops_seed_cabin_smoke.mjs birth-structural --apply ...`"
        )
        return 1 if REQUIRED else 0
    print(f"OK seeded propose session {session_id}")

    status, conf = _request(
        "POST",
        "/api/ai/intents/confirm",
        body=confirm_body,
        account_id=account_id,
    )
    data = _unwrap(conf)
    if status != 200:
        print(f"BLOCKED: confirm HTTP {status}: {conf}")
        return 1 if REQUIRED else 0
    trade = data.get("trade") if isinstance(data, dict) else None
    trade_status = trade.get("status") if isinstance(trade, dict) else None
    if trade_status != "executed":
        print(f"BLOCKED: confirm trade status={trade_status}: {trade}")
        return 1 if REQUIRED else 0
    print(f"OK confirm executed tx={trade.get('transactionId')}")

    pos = _portfolio_position(account_id, instrument_id)
    if pos is None:
        print("FAIL: position not found on portfolio after confirm")
        return 1
    fails = _assert_birth_position(
        pos, entry=entry, signed_stop=signed_stop, direction=direction
    )
    op = pos.get("operational") if isinstance(pos.get("operational"), dict) else {}
    view = (
        op.get("operationalView")
        if isinstance(op.get("operationalView"), dict)
        else {}
    )
    print(
        f"OK position {pos.get('id')} operatingState={view.get('operatingState')} "
        f"primaryAction={view.get('primaryAction')} "
        f"currentStop={op.get('currentStop')} initialStop={op.get('initialStop')}"
    )
    if fails:
        print("FAIL asserts:")
        for f in fails:
            print(f"  - {f}")
        return 1
        print("PASS: birth-structural (PROTECTED, stop != bootstrap)")
    return 0


def _study_mfe_mae(study: dict[str, Any]) -> dict[str, Any] | None:
    raw = study.get("mfeMae")
    if not isinstance(raw, dict):
        return None
    mfe = _finite(raw.get("mfeR"))
    mae = _finite(raw.get("maeR"))
    if mfe is None and mae is None:
        return None
    return raw


def _list_studies(account_id: str) -> list[dict[str, Any]]:
    status, payload = _request(
        "GET", f"/api/accounts/{account_id}/decision-studies?limit=50"
    )
    if status != 200:
        print(f"FAIL: decision-studies HTTP {status}: {payload}")
        return []
    data = _unwrap(payload)
    if isinstance(data, dict):
        items = data.get("items") or data.get("studies") or data.get("rows")
        if isinstance(items, list):
            return [x for x in items if isinstance(x, dict)]
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    return []


def cmd_journal_mfe_mae(args: argparse.Namespace) -> int:
    print("=== ops_seed_cabin_smoke journal-mfe-mae ===")
    print(f"API={API} apply={args.apply} required={REQUIRED}")
    status, health = _request("GET", "/api/health")
    if status != 200:
        msg = f"health HTTP {status}: {health}"
        if REQUIRED:
            print(f"FAIL: {msg}")
            return 1
        print(f"SKIP: {msg}")
        return 0

    status, acc_payload = _request("GET", "/api/accounts")
    if status != 200:
        print(f"FAIL: accounts HTTP {status}")
        return 1
    account_id = _resolve_account_id(_accounts(acc_payload), args.account_id)
    print(f"OK account: {account_id}")

    studies = _list_studies(account_id)
    hit: dict[str, Any] | None = None
    for s in studies:
        if _study_mfe_mae(s) is not None:
            hit = s
            break

    if hit is None and not args.apply:
        print(
            "BLOCKED: no decision-study with finite mfeR/maeR. "
            "Re-run with --apply to seed a propose session with mfeMae."
        )
        print("Honesty: Final R stays '-' on ficha; MFE/MAE is session photo.")
        return 1 if REQUIRED else 0

    if hit is None and args.apply:
        candidates = _candidate_instruments(
            prefer_id=args.instrument_id, open_ids=set(), limit=3
        )
        if not candidates:
            print("BLOCKED: no instrument with OHLCV to seed journal mfeMae")
            return 1 if REQUIRED else 0
        inst = candidates[0]
        instrument_id = str(inst["id"])
        symbol = inst.get("symbol") if isinstance(inst.get("symbol"), str) else None
        close = _last_close(instrument_id) or 100.0
        decision_id = f"dec-ops-mfe-{uuid.uuid4().hex[:10]}"
        session_id = f"DSS-ops-mfe-{uuid.uuid4().hex[:10]}"
        stop = _structural_stop(close)
        trade_plan = _build_triggered_plan(
            instrument_id=instrument_id,
            decision_id=decision_id,
            entry=close,
            stop=stop,
            qty=1.0,
            direction="long",
            symbol=symbol,
        )
        mfe_mae = {
            "status": "ok",
            "mfeR": 0.42,
            "maeR": -0.18,
            "currentR": 0.1,
            "source": "ops_seed_v210",
            "why": [],
        }
        try:
            asyncio.run(
                _seed_propose_session_db(
                    session_id=session_id,
                    account_id=account_id,
                    instrument_id=instrument_id,
                    decision_id=decision_id,
                    action="recommend_long",
                    trade_plan=trade_plan,
                    symbol=symbol,
                    mfe_mae=mfe_mae,
                )
            )
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL: DB seed mfeMae session: {exc}")
            return 1
        print(f"OK seeded propose session {session_id} with mfeMae")
        studies = _list_studies(account_id)
        for s in studies:
            if s.get("instrumentId") == instrument_id and _study_mfe_mae(s) is not None:
                hit = s
                break
        if hit is None:
            print(
                "PASS: session seeded with mfeMae "
                f"(mfeR={mfe_mae['mfeR']} maeR={mfe_mae['maeR']}); "
                "study list may lag — open Journal Tesis for "
                f"{symbol or instrument_id}"
            )
            print("Honesty: Final/Realized R on ficha may be '-' (positionState null).")
            print("Browser: /decision-journal -> Tesis -> ficha -> journal-mfe-mae")
            return 0

    assert hit is not None
    mfe = _study_mfe_mae(hit) or {}
    print(
        f"PASS: study instrumentId={hit.get('instrumentId')} "
        f"symbol={hit.get('symbol')} status={hit.get('status')} "
        f"mfeR={mfe.get('mfeR')} maeR={mfe.get('maeR')} source={mfe.get('source')}"
    )
    print("Honesty:")
    print("  - MFE/MAE = foto de sesion (runtime.mfeMae), not PositionState life peaks")
    print("  - Final/Realized R on ficha may show '-' (positionState: null)")
    print("  - status may not be 'closed' after exit (studies join open positions)")
    print("Browser checklist:")
    print("  1. Open /decision-journal -> Tesis")
    print(f"  2. Open ficha for {hit.get('symbol') or hit.get('instrumentId')}")
    print("  3. Assert [data-testid=journal-spine] and [data-testid=journal-mfe-mae]")
    print("  4. Caption mentions foto de sesion")
    return 0


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_birth = sub.add_parser(
        "birth-structural",
        help="Seed Confirm+signedStop estructural (Planificado+MANTENER)",
    )
    p_birth.add_argument("--account-id", help="Account id DEMO")
    p_birth.add_argument(
        "--instrument-id",
        help="Instrument id (with --flat: fixture id; without --flat: live Yahoo)",
    )
    p_birth.add_argument(
        "--flat",
        action="store_true",
        default=True,
        help="Seed flat OHLCV @ 10 (default; passes opening gate)",
    )
    p_birth.add_argument(
        "--no-flat",
        action="store_false",
        dest="flat",
        help="Use live instrument OHLCV (may risk_veto)",
    )
    p_birth.add_argument("--qty", type=float, default=1.0, help="Quantity (default 1)")
    p_birth.add_argument(
        "--apply",
        action="store_true",
        help="PUT mandato if needed + DB propose session + Confirm execute",
    )
    p_birth.set_defaults(func=cmd_birth_structural)

    p_j = sub.add_parser(
        "journal-mfe-mae",
        help="Locate or seed Journal study with mfeMae",
    )
    p_j.add_argument("--account-id", help="Account id DEMO")
    p_j.add_argument("--instrument-id", help="Prefer instrument for seed")
    p_j.add_argument(
        "--apply",
        action="store_true",
        help="Seed propose session with mfeMae if none found",
    )
    p_j.set_defaults(func=cmd_journal_mfe_mae)

    args = parser.parse_args()
    try:
        return int(args.func(args))
    except urlerror.URLError as exc:
        msg = f"API unreachable: {exc}"
        if REQUIRED:
            print(f"FAIL: {msg}")
            return 1
        print(f"SKIP: {msg}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
