"""Alta / cierre / borrado / restauración de datos desechables por API (CTA-*).

Uso (desde la raíz del repo):

    python <ruta>/api-cuentas.py create --name "CU-REV A"
    python <ruta>/api-cuentas.py close --account <id>
    python <ruta>/api-cuentas.py delete --account <id>
    python <ruta>/api-cuentas.py venue --account <id> --venue paper
    python <ruta>/api-cuentas.py restore-seed
    python <ruta>/api-cuentas.py list

Sin dependencias externas (urllib). API por defecto: http://localhost:8000
(``API_BASE``). El E2E crea/limpia sus propios datos; este script existe para
reproducir la preparación y la restauración a mano y para el orquestador.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request

API_BASE = os.environ.get("API_BASE", "http://localhost:8000").rstrip("/")
SEED_ID = "default-account-seed"


def call(method: str, path: str, body: dict | None = None) -> tuple[int, object]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        return exc.code, (json.loads(raw) if raw else None)


def create(name: str) -> dict:
    status, payload = call(
        "POST",
        "/api/accounts",
        {"name": name, "currency": "EUR", "initialDeposit": 10_000},
    )
    if status not in (200, 201):
        raise SystemExit(f"alta fallida ({status}): {payload}")
    return payload["data"]  # type: ignore[index]


def close(account_id: str) -> None:
    status, payload = call("POST", f"/api/accounts/{account_id}/close")
    if status not in (200, 204):
        raise SystemExit(f"cierre fallido ({status}): {payload}")


def delete(account_id: str) -> None:
    status, payload = call("DELETE", f"/api/accounts/{account_id}")
    if status not in (200, 204):
        raise SystemExit(f"borrado fallido ({status}): {payload}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    create_cmd = sub.add_parser("create")
    create_cmd.add_argument("--name", required=True)

    for name in ("close", "delete"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--account", required=True)

    venue_cmd = sub.add_parser("venue")
    venue_cmd.add_argument("--account", required=True)
    venue_cmd.add_argument("--venue", choices=["paper", "live"], required=True)

    sub.add_parser("restore-seed")
    sub.add_parser("list")

    args = parser.parse_args()

    if args.command == "create":
        print(json.dumps(create(args.name), indent=2, ensure_ascii=False))
    elif args.command == "close":
        close(args.account)
        print(f"cerrada {args.account}")
    elif args.command == "delete":
        delete(args.account)
        print(f"borrada {args.account}")
    elif args.command == "venue":
        status, payload = call(
            "PATCH", f"/api/accounts/{args.account}/broker-venue", {"venue": args.venue}
        )
        print(status, json.dumps(payload, ensure_ascii=False))
    elif args.command == "restore-seed":
        status, payload = call("POST", f"/api/accounts/{SEED_ID}/make-default")
        print(status, json.dumps(payload, ensure_ascii=False))
    elif args.command == "list":
        _, accounts = call("GET", "/api/accounts")
        _, profiles = call("GET", "/api/investor-profiles")
        print(json.dumps({"accounts": accounts, "profiles": profiles}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
