# Traspaso de relevo — D0 V2.14 foundation (handover agente)

Fecha: 2026-09-07 · Rama: `v2-13-1-rc-honesty-remediation` (HEAD `08cada82`; base del audit formal `da5c4b2a`)
Repo root: `C:/Users/josea/Documents/Informatica/Typescript/Bolsa_V1`
Shell: PowerShell → **NO usar `&&`** (usar `;`). CRLF→LF warn al editar `.md` (normal por `autocrlf`; diff vacío = sin contenido real).

> Pega este texto en el agente que continúe V2.14 tras la faena D0.
> V2.14 = **Financial Execution & Full Reconciliation** (decreto de numeración fijado). Shadow LIVE → V2.15. LIVE cert → V2.16.

---

## RESULTADO de D0 (docs, sin código)

1. **[Decreto/plan V2.14]** `docs/engineering/plan-v2-14-financial-execution-reconciliation-2026-09-07.md` —
   sella la numeración y desglosa faenas D0..C1 contra la localización real de código en HEAD `08cada82`.
2. **Roadmap** `docs/engineering/roadmap-live-execution-core-2026-09-07.md`: tabla §2 "Versiones siguientes"
   corregida (V2.14 = Financial Execution & Full Reconciliation; V2.15 Shadow LIVE; V2.16 LIVE cert),
   con nota de la colisión histórica de dos etiquetas V2.14.
3. **Índice** `docs/engineering/engineering-index-2026-08-03.md`: entradas nº 89+ registrando la tanda
   V2.12/V2.13 post-`88` (traspaso-tag-v2-12-beta, audit-ext-v2-13, deuda-anotada-v2-13, roadmap LIVE core,
   decree V2.14) — el índice quedaba anclado en el **#88** (XL-3 wire persist-only).

---

## Qué queda por hacer (retomar en el agente siguiente)

1. **Commit de esta faena** (solo los archivos D0; nunca `git add -A`).
2. **B1 (P1-03/P2-03/P2-02)** — Decimal al boundary financiero:
   `XtbBridgeOrderState`/`XtbBridgeAccountCash`/`XtbBridgePosition`/`BrokerOrderQueryResult`/`LiveOrderDrift`
   → `Decimal`; política de `PositionState` documentada; tests unit + mypy.
3. **B2 (P2-04/P2-05)** — lease configurable + columnas `attempt_count/last_error/claim_expires_at`;
   XTB cancel real round-trip (o PARKED honesto).
4. **E1 (P1-01)** — ExecutionEvent (RFC + migración `022_*`) + llenado LIVE→Position→Ledger con idempotencia
   `execution_id` (`ON CONFLICT`), jugando dentro del kernel Decimal de `ExecuteTrade`; tests partial/multi-fill/duped.
5. **E2 (P1-02/P2-01)** — reconciliación completa + `OperationalIncident` durable (fix double-worker OPEN) + OR-4 deny.
6. **C1 (P1-04)** — migración 021/022 en PostgreSQL real + multi-worker + recon; Release-tag CI → GREEN SOLO
   si se observa `conclusion=success` (no afirmar de otro modo).

Regla de oro: por faena, `git status` debe cuadrar con su lista de archivos antes de commitear; preserva
`apps/api-python/logs/**` y `packages/py/application/logs/**` (`.jsonl`) y los cambios de worktree e2e/web ajenos.
Nota herramienta: code references `startLine:endLine:filepath` solo código confirmado. Arranca leyendo estado real
(`git status` + `git diff --stat HEAD`) antes de proponer, para no alucinar.

FIN DE TRASPASO D0
