# Plan — OR-6 SEMI operational certification

> **Padre:** [`roadmap-v112-operational-reliability-2026-08-26.md`](./roadmap-v112-operational-reliability-2026-08-26.md) · ADR-035.
> **AsOf:** 2026-08-26.
> **Estado:** **CERRADO** (código + tests + docs). Spine **433**.
> **Relevo:** [`traspaso-relevo-or6-semi-operational-certification-2026-08-26.md`](./traspaso-relevo-or6-semi-operational-certification-2026-08-26.md).

---

## Objetivo

Certificar SEMI con **cuatro estados discretos** y venue **explícito en el CTA**:

```text
PAPER_READY | PAPER_DEGRADED | LIVE_EXPERIMENTAL | LIVE_BLOCKED
CTA: Ejecutar en PAPER | Ejecutar en LIVE
```

Un FAIL crítico (recon drift, kill, path SEMI caído) **no** se promedia a «50 % listo». OE-1 PASS/FAIL/WARN sigue **measure ≠ Accept**. AUTO **no** entra en la fórmula.

## Decisiones

| ID  | Decisión                                                                                                                                                                                      |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | Kernel puro `derive_operational_readiness` (PY) + espejo TS. Cuatro estados; `reasons[]` + `notes[]`. **Sin** porcentaje.                                                                     |
| D2  | AUTO lane (P1–P5) **ignorado**. SEMI certification ≠ thaw. `PAPER_READY` con AUTO FAIL es válido. LIVE **nunca** `READY` (experimental, no accepted).                                         |
| D3  | Críticos (cualquiera basta): `portfolio_drift` · `kill_switch` · `recon_not_certified` · `semi_path_unavailable` · live `drift`/`unavailable`/`not_wired`.                                    |
| D4  | Paper + críticos → `PAPER_DEGRADED`. Live + críticos → `LIVE_BLOCKED`. Paper limpio → `PAPER_READY`. Live limpio → `LIVE_EXPERIMENTAL`.                                                       |
| D5  | OE-1 añade campo aditivo `operationalReadiness` (`ops_self_eval_v0`). No `contract:gen`. Chip mesa **aparte** del Autoeval PASS/FAIL.                                                         |
| D6  | CTA firma: `Ejecutar en PAPER` / `Ejecutar en LIVE` usando venue **efectivo** (PA-1 coalesce), no solo el toggle global. Protect sigue `Confirmar protección`. Badge LIVE. Gate OR-4 intacto. |
| D7  | UI preferencia cuenta Paper\|Live (PA-1 API ya existe). Mesa toggle = override **global**. **No** Alembic. **No** tipar `AccountSettings.brokerVenue`.                                        |
| D8  | Sin UI resolución recon (parked OR-4) · sin thaw · sin AUTO on · sin pack v112 · sin mass sim.                                                                                                |

## Kernel

```text
AUTO marks                         → ignore
recon drift                        → critical
recon ≠ ok                         → recon_not_certified
kill ON                            → critical
SEMI UNAVAILABLE                   → critical
SEMI WARN                          → note thin_semi_evidence (sigue READY si no hay crítico)
venue live + live drift/unavail    → critical
venue live + adapter not_wired     → critical (si se conoce)

venue=paper + reasons?  PAPER_DEGRADED : PAPER_READY
venue=live  + reasons?  LIVE_BLOCKED   : LIVE_EXPERIMENTAL
```

## Ficheros

- [`operational_readiness.py`](../../packages/py/application/src/bolsa_application/operational_readiness.py) + espejo TS
- OE-1 [`ops_self_eval.py`](../../packages/py/application/src/bolsa_application/ops_self_eval.py)
- Mesa barra · Confirm F3 · ticket manual · preferencia cuenta
- Tests: `test_operational_readiness.py` · OE-1 · shared · mesa bar
- Spine: `pnpm test:decision-spine`

## DoD

- [x] Cuatro estados verdes; drift no se promedia; AUTO FAIL no tumba PAPER_READY.
- [x] CTA `Ejecutar en PAPER|LIVE`; badge LIVE; Autoeval OE-1 intacto.
- [x] Preferencia cuenta Paper\|Live (API PA-1).
- [x] Sin Alembic / `contract:gen` / thaw / AUTO on / pack v112 / UI resolución recon.
- [x] Docs: plan · CURRENT_SYSTEM · ADR-035 · CHANGELOG · roadmap · relevo OR-6.

## Freeze (intactos)

ADR-034 · Confirm = única firma · `PAPER_D_EXECUTE` off · LIVE experimental · no broker producción · no auto-heal · thin 5.x/8.x congelados · Lab ≠ mesa · OR-1…OR-5 intactos.

## E1

Tras OR-6: pack + tag **`v1.12-beta`** (chat aparte) **o** operar SEMI. **No** thaw estricto · **no** AUTO on.
