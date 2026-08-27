#!/usr/bin/env python3
"""Cierra y purga cuentas dejando solo la operativa (keep).

Por defecto es DRY-RUN. Con ``--apply``:
  1. Cierra (soft) todas las activas excepto ``--keep``.
  2. Purga en bucle demos simulated ya cerradas (API batch ≤50).
  3. Papers: solo soft-close (DELETE solo admite simulated).

Resolución de keep (en orden):
  --keep ID | BOLSA_KEEP_ACCOUNT_ID | cuenta isDefault=true | fallo si >1 activa.

Notas:
  - Si purgas ``default-account-seed`` y no es keep, el próximo arranque del API
    puede recrearla vacía. Por defecto el script **no** purga el seed si keep ≠ seed
    (lo deja closed). Usa ``--purge-seed`` para borrarlo también.
  - Requiere API en ``BOLSA_API_URL`` (default http://127.0.0.1:8000).

Uso (repo root):
  python scripts/ops_keep_one_account.py
  python scripts/ops_keep_one_account.py --keep <accountId>
  python scripts/ops_keep_one_account.py --keep <accountId> --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

API = os.environ.get("BOLSA_API_URL", "http://127.0.0.1:8000").rstrip("/")
SEED_ID = "default-account-seed"


def _request(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    account_id: str | None = None,
) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers: dict[str, str] = {}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if account_id:
        headers["X-Account-Id"] = account_id
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            if not raw:
                return resp.status, None
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed: Any = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw
        return exc.code, parsed
    except urllib.error.URLError as exc:
        return 0, {"error": str(exc.reason)}


def _accounts(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return [a for a in payload["data"] if isinstance(a, dict)]
    return []


def _resolve_keep(
    accounts: list[dict[str, Any]],
    keep_arg: str | None,
) -> str:
    env_keep = (os.environ.get("BOLSA_KEEP_ACCOUNT_ID") or "").strip()
    keep = (keep_arg or env_keep or "").strip()
    if keep:
        if not any(a.get("id") == keep for a in accounts):
            raise SystemExit(f"KEEP id no existe en /api/accounts: {keep}")
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
        "No se pudo inferir la cuenta operativa. Pasa --keep <accountId> "
        "(o BOLSA_KEEP_ACCOUNT_ID). Cuentas activas:\n"
        + "\n".join(
            f"  {a.get('id')}  {a.get('type')}  {a.get('name')}  "
            f"default={a.get('isDefault')}"
            for a in active
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", help="Account id a conservar (operativa)")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Ejecutar cambios (sin esto: dry-run)",
    )
    parser.add_argument(
        "--purge-seed",
        action="store_true",
        help="Permitir purgar default-account-seed si está closed y no es keep "
        "(puede recrearse al reiniciar API)",
    )
    parser.add_argument(
        "--skip-purge",
        action="store_true",
        help="Solo cerrar; no purgar demos cerradas",
    )
    args = parser.parse_args()

    status, health = _request("GET", "/api/health")
    if status != 200:
        print(f"API no disponible en {API} (health={status} {health})", file=sys.stderr)
        return 2

    status, body = _request("GET", "/api/accounts")
    if status != 200:
        print(f"GET /api/accounts falló: {status} {body}", file=sys.stderr)
        return 2
    accounts = _accounts(body)
    keep = _resolve_keep(accounts, args.keep)
    keep_row = next(a for a in accounts if a.get("id") == keep)

    active = [a for a in accounts if a.get("status") == "active"]
    to_close = [a for a in active if a.get("id") != keep]
    closed_already = [a for a in accounts if a.get("status") == "closed"]

    print(f"API: {API}")
    print(f"Modo: {'APPLY' if args.apply else 'DRY-RUN'}")
    print(
        f"KEEP: {keep} · {keep_row.get('type')} · {keep_row.get('name')!r}"
    )
    print(f"Activas totales: {len(active)} · a cerrar: {len(to_close)}")
    print(f"Ya cerradas: {len(closed_already)}")
    for a in to_close[:20]:
        print(f"  CLOSE  {a.get('id')}  {a.get('type')}  {a.get('name')}")
    if len(to_close) > 20:
        print(f"  … +{len(to_close) - 20} más")

    if not args.apply:
        print("\nSin --apply no se modifica nada. Revisa KEEP y vuelve a lanzar.")
        return 0

    closed_ok = 0
    closed_err = 0
    for a in to_close:
        aid = str(a.get("id"))
        st, resp = _request("POST", f"/api/accounts/{aid}/close", account_id=aid)
        if st in {200, 201}:
            closed_ok += 1
            print(f"  closed {aid}")
        else:
            closed_err += 1
            print(f"  FAIL close {aid}: {st} {resp}", file=sys.stderr)
        time.sleep(0.02)

    print(f"Cierre: ok={closed_ok} err={closed_err}")

    if args.skip_purge:
        print("Purge omitido (--skip-purge).")
        return 0 if closed_err == 0 else 1

    # DELETE individual (simulated cerradas). Evita el purge batch ciego
    # que podría borrar el seed sin control.
    st, body_all = _request("GET", "/api/accounts")
    all_now = _accounts(body_all) if st == 200 else []
    delete_candidates = [
        a
        for a in all_now
        if a.get("status") == "closed"
        and a.get("type") == "simulated"
        and a.get("id") != keep
        and (args.purge_seed or a.get("id") != SEED_ID)
    ]
    deleted_ok = 0
    deleted_err = 0
    for a in delete_candidates:
        aid = str(a.get("id"))
        st, resp = _request("DELETE", f"/api/accounts/{aid}", account_id=aid)
        if st in {200, 204}:
            deleted_ok += 1
            print(f"  deleted {aid}")
        else:
            deleted_err += 1
            print(f"  FAIL delete {aid}: {st} {resp}", file=sys.stderr)
        time.sleep(0.02)

    print(f"Delete simulated: ok={deleted_ok} err={deleted_err}")

    # Recontar
    st, body2 = _request("GET", "/api/accounts")
    after = _accounts(body2) if st == 200 else []
    active_after = [a for a in after if a.get("status") == "active"]
    closed_after = [a for a in after if a.get("status") == "closed"]
    paper_closed = [a for a in closed_after if a.get("type") == "paper"]
    seed_left_closed = any(
        a.get("id") == SEED_ID and a.get("status") == "closed" for a in after
    )
    print(
        f"Done. Activas={len(active_after)} cerradas={len(closed_after)} "
        f"(paper closed={len(paper_closed)}, seed closed kept={seed_left_closed})"
    )
    for a in active_after:
        print(f"  ACTIVE  {a.get('id')}  {a.get('type')}  {a.get('name')}")
    for a in closed_after[:10]:
        print(f"  CLOSED  {a.get('id')}  {a.get('type')}  {a.get('name')}")
    if len(closed_after) > 10:
        print(f"  … +{len(closed_after) - 10} closed más")
    if len(active_after) != 1 or active_after[0].get("id") != keep:
        print("AVISO: no quedó exactamente 1 activa = keep.", file=sys.stderr)
        return 1
    return 0 if closed_err == 0 and deleted_err == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
