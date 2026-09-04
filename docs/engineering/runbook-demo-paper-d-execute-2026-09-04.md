# Runbook — DEMO PAPER_D_EXECUTE (un ciclo real fuera de pytest)

> **AsOf:** 2026-09-04 · **V2.0.1** Honesty DEMO execute.  
> **Padre:** [ADR-023](../adr/023-camino-d-thaw.md) · [plan cierre PAPER AUTO](./traspaso-relevo-post-v199-plan-cierre-paper-auto-2026-09-04.md).  
> **Freeze:** default repo **off** · **≠ LIVE** · arm UI ≠ execute env.

Un operador local puede correr **un** ciclo `PaperDeskCycle` real (EntryTick + PositionTick) sin fingir LIVE y sin dejar el flag encendido en el repo.

## 0. Precondiciones

- API Python en local (`:8000`) + web.
- Cuenta DEMO conocida (`accountId`).
- `PAPER_D_EXECUTE` **no** está en `.env.example` como on (solo comentado).
- Arm UI (`ACTIVAR AUTO`) es localStorage — **no** enciende el servidor.

## 1. Opt-in env (local, gitignored)

En el `.env` de la API (nunca commit):

```bash
PAPER_D_EXECUTE=1
PAPER_D_ACCOUNT_ID=<tu-account-id-demo>
```

Reinicia el proceso API. Comprueba eco:

```bash
# health / risk kill — debe reportar paperDExecuteEnv=true
curl -s -b cookies.txt http://127.0.0.1:8000/api/risk/kill-switch | jq .
```

## 2. Arm UI (≠ execute)

1. Cuentas → Config → Operativa → frase `ACTIVAR AUTO` (doble confirmación).
2. Badge esperado: **«AUTO armado · ejecución off|on»**.
3. En Mesa header: **«PAPER_D execute (env)»** = on solo si el env está activo — **no** confundir con «AUTO armado (UI)».

## 3. Dry-run (seguro, default)

```bash
curl -s -X POST "http://127.0.0.1:8000/api/paper-desk/cycle?accountId=<ACCOUNT>" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"dryRun":true,"templateId":"moderate"}' | jq '.data.cycle,.data.autoDesk'
```

`GET /api/paper-desk/daily-report` siempre evalúa en dry-run (nunca muta).

## 4. Ciclo real (`dryRun: false`)

Solo con env on + arm UI (producto) + kill switch **off**:

```bash
curl -s -X POST "http://127.0.0.1:8000/api/paper-desk/cycle?accountId=<ACCOUNT>" \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"dryRun":false,"templateId":"moderate"}' | jq '.data.cycle'
```

Esperado: filas `executed|denied|blocked|held|…` (no silent success vacío). Kill ON → AUTO deniega (`kill_switch`).

## 5. Fail-closed si env off

Con `PAPER_D_EXECUTE` unset/off y `dryRun:false` → **403** `paper_auto_env_blocked`.

## 6. Apagar

1. Quitar o comentar `PAPER_D_EXECUTE` / `PAPER_D_ACCOUNT_ID` del `.env` local.
2. Reiniciar API.
3. Disarmar AUTO en Cuentas.
4. Verificar header: Automatización / PAPER_D execute = OFF.

## Copy honesty

| Señal                 | Significado                                  |
| --------------------- | -------------------------------------------- |
| AUTO armado (UI)      | localStorage arm — no execute                |
| PAPER_D execute (env) | servidor opt-in `PAPER_D_EXECUTE=1`          |
| dryRun true           | evalúa; no Router fill                       |
| Kill ON               | AUTO DENY incluso protector (H2 intencional) |

Consola operativa: CTA «Correr auto-propose» = **dry-run**; no es este ciclo execute.
