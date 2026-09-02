# Spec — V1.88 Lifecycle Integrated Golden + Restart + Recon

> **AsOf:** 2026-09-02 · **Estado:** **CERRADA (CI GREEN)** · tip [`v1.88-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.88-beta) → [`33685242`](https://github.com/jvelasca/Bolsa_V1/commit/33685242) · [run 33691233738](https://github.com/jvelasca/Bolsa_V1/actions/runs/33691233738).  
> **Padre:** [`respuesta-auditor-v187-lifecycle-operational-2026-09-02.md`](./respuesta-auditor-v187-lifecycle-operational-2026-09-02.md).  
> **Partida tip:** `v1.87-beta` → [`646b97ac`](https://github.com/jvelasca/Bolsa_V1/commit/646b97ac). **No** LIVE · **no** bump. Pendiente auditoría externa.

```text
USER A (JWT)
  → ACCOUNT A
  → POSITION_OPENED → T1 → TRAIL → [RECON DRIFT] → [RECOVERY] → EXIT → CLOSED
  → PostgreSQL (sequence_no)
STOP API (lifespan teardown)
START API (nueva app / nueva sesión)
GET snapshot ≡ mismo accounting + mismos sequence_no

USER B (JWT) → GET position A → 403
POST concurrent T1 → exactamente uno
```

## 0. Freeze

Confirm SEMI · `PAPER_D_EXECUTE` **off** · **NO LIVE** · sin scheduler · sin bump `1.35.0-beta`.  
**No** Playwright en `frontend-ci`. **No** sustituir `/portfolio` ni unificar ledger.  
`last_price_for_stage` permanece certificación golden (no market quote de producción).

## 1. Golden HTTP (obligatorio)

Suite ASGI + PostgreSQL (mismo job `lifecycle-pg` o extensión):

1. Crear users A/B + cuentas · JWT A.
2. Trail completo vía `POST /api/lifecycle/events`.
3. Tras T1: abrir `OperationalIncident` drift (o status recon drift) en cuenta A · GET snapshot sigue OK · clear/resolve · continuar EXIT/CLOSED.
4. Teardown lifespan (API “muerta”) · `create_app` + lifespan nuevo · GET con JWT A → mismo `stage`/`accounting`/`sequenceNo`.
5. JWT B → GET → 403.
6. Concurrent duplicate T1 (ya en V1.87) permanece en la batería.

## 2. Recon (alcance honesto)

Lifecycle **no** es autoridad de equity de cartera. V1.88 certifica:

- el log lifecycle sobrevive drift/recovery de cuenta;
- exits/lectura de snapshot no se corrompen;
- sin auto-heal de libros.

## 3. CI

`lifecycle-pg` ejecuta el golden (además de Alembic + concurrent + auth).  
Integrated browser E2E sigue **opt-in** (no obligatorio en certify).

## 4. IN / OUT

**IN:** golden HTTP JWT+PG · restart lifespan · recon incident en camino · CI lifecycle-pg ampliado · docs.

**OUT:** LIVE · bump · Playwright frontend-ci · browser integrated obligatorio · unificar ledger · market quote real · thaw estricto.
