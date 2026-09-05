# Runbook — V2.10 Seed Ops cabin smoke (2026-09-05)

> **Relevo:** [V2.10 Seed Ops](./traspaso-relevo-v2-10-seed-ops-2026-09-05.md).  
> **Script:** `node scripts/ops_seed_cabin_smoke.mjs` (carga `.env`) → `scripts/ops_seed_cabin_smoke.py`  
> **Freeze:** NO LIVE broker · SEMI Confirm = firma · **no** `/portfolio/trade` para birth Planificado.

## Precondiciones

1. Stack local arriba (`BOLSA_API_URL`, default `http://127.0.0.1:8000`).
2. Cuenta DEMO `simulated` activa (`--account-id` o default/`BOLSA_KEEP_ACCOUNT_ID`).
   Preferible cuenta limpia (sin drift/recon veto). Cuenta `ops-v210-seed` creada en smoke local.
3. Preferir wrapper Node (inyecta `DATABASE_URL` desde `.env`):
   `node scripts/ops_seed_cabin_smoke.mjs …`
4. Con `--apply`, birth siembra instrumento + 120 barras planas @ 10 (pasa DS-05) + sesión propose en BD (package `recommend_long`) + Confirm.

## V2.52 — Birth estructural (Planificado + MANTENER)

```bash
# Dry-run
node scripts/ops_seed_cabin_smoke.mjs birth-structural --account-id <id>

# Apply (fixture flat por defecto)
node scripts/ops_seed_cabin_smoke.mjs birth-structural --apply --account-id <id>
```

**Camino canónico**

1. Instrumento sintético + OHLCV flat @ 10 (golden opening_gate_seed / DS-05).
2. Merge mandato (PUT tenures; no borra otras).
3. Inserta `decision_sessions` kind=`propose` con package `recommend_long` + TradePlan `TRIGGERED`.
4. `POST /api/ai/intents/confirm` `execute: true`, `signedStop` = entry×0.97 (**≠** bootstrap ×0.95).
5. Assert API: `operatingState=PROTECTED`, stop presente ≠ floor −5 %. POV puede decir `MONITOR`; cabina Decision Surface → **MANTENER** / fase **Planificado**.

**Browser checklist**

- Mercado / Position Card: protección **Planificado** (no emergencia −5 %).
- NEXT ACTION **MANTENER**.
- `data-protect-kind` ≠ `bootstrap`.
- Stop ≈ `signedStop` (p.ej. 9.7 con entry 10).

### Anti-patterns

| Path                                        | Resultado                                              | No sirve para     |
| ------------------------------------------- | ------------------------------------------------------ | ----------------- |
| `POST /portfolio/trade` buy                 | `OPEN_UNPROTECTED` · sin `structuralStop`              | Birth Planificado |
| Proteger −5 % tras open manual              | `protectKind=bootstrap`                                | Stop estructural  |
| Confirm sin sesión propose `recommend_long` | `orphan_opening_blocked` / `decision_package_conflict` | SEMI opening      |
| Propose live `action=wait` sin seed BD      | no Confirm opening                                     | Seed fiable       |

## V2.53 — Journal MFE·MAE

```bash
node scripts/ops_seed_cabin_smoke.mjs journal-mfe-mae --account-id <id>
node scripts/ops_seed_cabin_smoke.mjs journal-mfe-mae --apply --account-id <id>
```

**Camino:** seed `runtime.mfeMae` en sesión propose (BD) → `GET .../decision-studies` → ficha `journal-mfe-mae`.

**Browser:** `/decision-journal` → Tesis → ficha → spine + MFE/MAE numéricos + caption «foto de sesión».

### Honestidad

- MFE/MAE = foto de sesión, **no** picos de vida de `PositionState`.
- Final R / Realized R en ficha pueden ser **—** (`positionState: null`).
- Status del study puede ser `target_active` (no exige `closed`).

## Exit codes

| Código | Significado                                                   |
| ------ | ------------------------------------------------------------- |
| 0      | PASS / dry-run OK / SKIP API down (si no `OPS_SEED_REQUIRED`) |
| 1      | FAIL asserts · BLOCKED · API down con `OPS_SEED_REQUIRED=1`   |
