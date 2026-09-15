# Arranque auditor externo — V2.39.3 (Cierre P1/N1 + P2/N2 + fix `totalSamples`) (2026-09-15)

Copia en chat nuevo (auditor):

---

Eres auditor externo de Bolsa V1 **candidato V2.39.3**. Auditas **desde GitHub**, sin acceso al
entorno local.

- **Delta:** `v2.39.2-beta` (`9444b364`) → tag **`v2.39.3-beta`** (anotado) → peeled al commit de
  sellado de `main` `b77a36aa`. El **código** auditado es el commit del tag.
- **`main`:** incluye, por encima del código, el commit de documentación de auditoría; el tag
  re-sellado apunta a ese commit final (el auditor lo resuelve con
  `git rev-list -n 1 v2.39.3-beta`).
- **Package:** `1.64.3-beta` · **CHANGELOG:** `[1.64.3-beta]`.
- **Alembic head:** `039_research_trials_regime` — esta fase **no añade migración**.
- **Flags:** sin cambios. `AUTO_ORCHESTRATOR_ADAPTIVE_REGIME` sigue **OFF** por defecto.

**Regla:** NINGÚN estado ambiguo → NO COMPRAR. No inventes PASS. Compara **línea por línea**
`v2.39.2-beta` → `v2.39.3-beta` y registra P0/P1/P2/P3 con evidencia `archivo:línea`.

**Punto de entrada único:** [`audit-pack-v2.39.3-cierre-ledger-2026-09-15.md`](./audit-pack-v2.39.3-cierre-ledger-2026-09-15.md)

---

## Resumen del delta (qué cambió y por qué)

La auditoría interna cerró **tres** hallazgos sobre `v2.39.2-beta` y confirmó un detalle que **no**
es fallo.

| #   | Sev   | Hallazgo                                                                                        | Naturaleza      |
| --- | ----- | ----------------------------------------------------------------------------------------------- | --------------- |
| 1   | P1/N1 | `next_executed_at` es por cuenta pero el lock que lo protegía era de **cartera**                | Producción      |
| 2   | P2/N2 | `append_trade`/`append_fee`/`append_custody_fee`/`append_cash_movement` aceptaban `executed_at` | Contrato débil  |
| 3   | P2    | `totalSamples` sumaba familias descartadas por `min_samples`                                    | Cálculo         |
| 4   | —     | `custody_obligation` (005) y `custody_obligations` (006) coexisten (la 006 no borra la 005)     | **No es fallo** |

---

## Foco 1 — Mutex financiero por cuenta, no por cartera (P1/N1)

**Lee (fuentes reales, no solo docs):**

- `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/account_repository.py`
  (`lock_account`)
- `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/ledger_repository.py`
  (`next_executed_at`)
- `packages/py/application/src/bolsa_application/accounts/trade.py`
- `packages/py/application/src/bolsa_application/accounts/cash.py`
- `packages/py/application/src/bolsa_application/accounts/custody.py`

**Foco:**

1. ¿`lock_account(account_id)` hace `SELECT ... FOR UPDATE` sobre `investment_accounts` y **falla**
   (`ValueError`) si la cuenta no existe?
2. ¿Se invoca **antes** de cualquier `with_for_update` sobre `PortfolioRow` en las **cuatro** rutas
   (trade, depósito, retiro, custodia), de modo que el orden de lock es determinista **cuenta → cartera**?
3. ¿El `next_executed_at` se lee con el lock de **cuenta** ya tomado, de modo que dos carteras de la
   misma cuenta **no** puedan leer el mismo `MAX(executed_at)` y emitir `executed_at` duplicado?
4. ¿La unidad de locking (cuenta) coincide ahora con la unidad de secuenciación (`account_id`)?
5. **Verifica por mutación:** revertir `lock_account` (o el orden cuenta → cartera) ¿hace **fallar**
   el test nuevo de concurrencia multi-portfolio?

---

## Foco 2 — El secuenciador es obligatorio por infraestructura (P2/N2)

**Lee:**

- `packages/py/infrastructure/src/bolsa_infrastructure/database/repositories/ledger_repository.py`
  (`append_trade`, `append_fee`, `append_custody_fee`, `append_cash_movement`)
- `packages/py/application/src/bolsa_application/accounts/trade.py` (ya sin `_ledger_ordering`)

**Foco:**

1. ¿Los cuatro `append_*` **ya no** aceptan `executed_at` y obtienen internamente
   `await self.next_executed_at(account_id)`?
2. ¿Queda **algún** caller que pase `executed_at` o un camino que use `datetime.now()` como instante
   del asiento?
3. ¿`append_trade` produce X y `append_fee` produce X+1 µs de forma natural, conservando el orden
   trade → fee?
4. ¿Los fakes de tests y los callers directos (`scripts/verify/`, tests de infraestructura) siguen la
   nueva firma?

---

## Foco 3 — `totalSamples` publica solo evidencia útil (Auditoría 2)

**Lee:**

- `packages/py/application/src/bolsa_application/discovery_evidence.py`
  (`_effective_total_samples`, `compute_lane_weights`, payload `"totalSamples"`)
- `packages/py/application/tests/test_discovery_evidence.py`

**Foco:**

1. ¿`_effective_total_samples` suma **solo** las familias presentes en `family_weights` (las que
   superaron `min_samples`)?
2. ¿Se usa en **ambos** sitios — `compute_lane_weights()` y el payload `"totalSamples"` — de modo que
   la puerta de decisión y lo publicado al operador **no divergen**?
3. ¿El test de invariante falla si se revierte el filtro (es decir, cubre realmente la regresión)?
4. Reproduce el ejemplo de la auditoría: 5 familias de 2 trials + 1 de 3, `min_total_samples=12`.

---

## Foco 4 — Detalle del script de limpieza (no es fallo)

**Lee:** `scripts/ops/cleanup_residual_accounts.py` (`ACCOUNT_CHILD_TABLES`).

**Foco:** ¿`custody_obligation` (005) y `custody_obligations` (006) **coexisten** legítimamente (la
006 no borra la 005) y la lista es correcta tal cual? Confirma que **no** hay que tocar nada.

---

## No pedir

LIVE · bump · unificar ledger/mesa · re-diseñar ADR · cerrar los chaos en CI sin PG ·
`transfer_cash` (fuera de alcance, anotado) · Opción B (tabla `account_ledger_sequence`, alternativa
documentada) · features fuera del alcance. La regla de fail-closed y los gates CPCV/PBO/DSR/WFE/OOS
**no se relajan**.

---

## Respuesta esperada

**(Pendiente — no inventar PASS).** Informe con `[severidad]` y veredicto **por cada foco**, con
evidencia `archivo:línea` y el delta real `v2.39.2-beta` → `v2.39.3-beta`. Marca explícitamente lo
que **no** puedas verificar desde GitHub y requiera entorno local (en particular, los tests chaos
con PostgreSQL y la verificación por mutación del secuenciador).
