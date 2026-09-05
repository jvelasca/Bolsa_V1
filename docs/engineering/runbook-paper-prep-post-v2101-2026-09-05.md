# Runbook — Preparación PAPER post V2.10.1 (honesty, flags OFF) (2026-09-05)

> **Relevo:** [preparación PAPER](./traspaso-relevo-paper-prep-post-v2101-2026-09-05.md).  
> **Padre tip:** [`v2.10.1-beta`](./traspaso-relevo-tag-v2-10-1-beta-2026-09-05.md).  
> **Freeze:** NO LIVE · `PAPER_D_EXECUTE` **default off** · Arm ≠ Execute · Confirm = firma · **PRODUCT FREEZE**.  
> **No es** el [runbook DEMO execute](./runbook-demo-paper-d-execute-2026-09-04.md) (opt-in). Este runbook deja el sistema **como shipped**.

## Léxico (no mezclar)

| Término             | Significado aquí                                        |
| ------------------- | ------------------------------------------------------- |
| **DEMO**            | Cuenta `simulated` local / mesa paper                   |
| **PAPER (venue)**   | Broker venue paper · default mesa                       |
| **PAPER_D_EXECUTE** | Opt-in servidor para Router AUTO fill — **OFF** en prep |
| **LIVE**            | Venue live / adapter — **bloqueado** en freeze          |

Preparación PAPER ≠ thaw LIVE. No Accept estricto ([deuda](./deuda-thaw-estricto-runbook-2026-08-25.md)).

## 1. Precondiciones

- Stack local up (API `:8000` + web).
- Cuenta DEMO limpia (`simulated`).
- `.env`: `PAPER_D_EXECUTE` **unset/comentado**.
- Venue mesa = paper.

## 2. Verificar defaults OFF

1. Header / kill-switch: `paperDExecuteEnv` falsy.
2. `POST /api/paper-desk/cycle` con `dryRun:false` → **403** `paper_auto_env_blocked`.
3. Arm UI OFF (o, si se arma para prueba visual: «ejecución off»).

## 3. SEMI path (Confirm = firma)

```bash
node scripts/ops_seed_cabin_smoke.mjs birth-structural --apply --account-id <id>
node scripts/ops_seed_cabin_smoke.mjs journal-mfe-mae --apply --account-id <id>
```

Browser: Planificado / MANTENER / stop ≠ bootstrap −5 % · Journal MFE/MAE finito.  
Detalle: [seed runbook](./runbook-v2-10-seed-ops-cabin-smoke-2026-09-05.md).

## 4. AUTO path — solo dry-run

```bash
# dryRun true — no Router fill
curl -s -X POST "http://127.0.0.1:8000/api/paper-desk/cycle?accountId=<ACCOUNT>" \
  -H "Content-Type: application/json" -b cookies.txt \
  -d '{"dryRun":true,"templateId":"moderate"}'
```

No encender `PAPER_D_EXECUTE` en esta prep.

## 5. Opt-in execute (opcional, fuera de prep)

Solo si el owner lo pide: seguir [runbook-demo-paper-d-execute](./runbook-demo-paper-d-execute-2026-09-04.md) y **apagar** al terminar (§6 allí).

## 6. Fail-closed / LIVE

| Check                    | Esperado                                 |
| ------------------------ | ---------------------------------------- |
| Env off + `dryRun:false` | 403 `paper_auto_env_blocked`             |
| Venue live / mock        | `not_wired` / `LIVE_BLOCKED` — no operar |
| Kill ON                  | AUTO DENY                                |

Código de referencia: `paper_d_execute_allowed()` · `operational_readiness.py` · `broker_venue_runtime.py` (default paper).

## 7. Dejar el sistema shipped

1. Sin `PAPER_D_EXECUTE` en `.env`.
2. AUTO desarmado.
3. Venue paper.
4. Stamp local: PASS/PARTIAL de este runbook (sin inventar).
