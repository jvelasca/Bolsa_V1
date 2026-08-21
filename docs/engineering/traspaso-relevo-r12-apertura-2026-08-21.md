# RELEVO / TRASPASO — R-12 apertura (2026-08-21)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1.
> **Propósito:** texto de paso anti-alucinación para el **siguiente chat**. Leer este doc + backlog §0 + `PROJECT_STATE.md` §2ac + premisas ⭐§0 **antes de tocar nada**.
> **Fuente de coordinación:** GitHub [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) `origin/main`. SHA vivo = `git fetch && git rev-parse origin/main` (no asumir un SHA de este fichero).
> **Firma de partida R-12:** `f7a86cc` · tag `v1.3.0` → `b778292` · rama `main`.

---

## 1. Qué está hecho (Track A + B)

- A0/A1 docs: premisas R-12 (GitHub = fuente de coordinación), plan, SHA vivos, README `v1.3.0 BETA`, CHANGELOG tag `b778292`.
- A2 test PG `test_custody_default_portfolio_policy.py`.
- A3 `scripts/verify/verify_financial_invariants.py` (A–E) + unit tests en python-ci.
- A4 `test_http_retry_idempotency.py` (deposit/withdraw retry misma key).
- A5 inventario pending-delete (sin purge). Hallazgo: `presetRuleGroups` es API viva.
- A6 higiene: índice histórico en engineering-index; script `cleanup_dev_test_residues.py` (8 cuentas `m7-win-*` + 9 instrumentos `M2 *` borrados por path canónico 2026-08-21); relevo R-10 `-obsoleto` movido a `docs/engineering/archive/`. **mypy analytics:** fuera de gate; medición 2026-08-21 muestra errores en `knowledge/dia_d_session_evidence.py`, `core_r_review_evidence.py`, `cognitive/weight_rules.py` (mypy 1.x INTERNAL ERROR al final del barrido). **No se pone a 0 en este ciclo.**
- Track B estudio teórico `estudio-flujo-semi-vs-tops-2026-08-21.md`.
- Track C **BLOQUEADO**. Gates documentados, no abiertos.

## 2. NO tocar

`pending-delete` riesgo alto · gobernanza IA · `PAPER_D_EXECUTE` · scheduler-vs-worker · `contract:gen` · producción `ExecuteTrade` cash_before · split `accounts.py` · frontend mesa/Confirm.

## 3. Texto de paso (pegar en el chat nuevo)

> CONTEXTO: repo Bolsa_V1, ciclo **R-12**. Lee `docs/engineering/traspaso-relevo-r12-apertura-2026-08-21.md` · `docs/engineering/plan-r12-auditoria-ux-2026-08-21.md` · `docs/PROJECT_PREMISES.md` ⭐§0 · `docs/engineering/PROJECT_STATE.md` §2ac · backlog §0.
> Firma: **GitHub `origin/main`** — ejecutar `git fetch && git rev-parse HEAD origin/main` y `git status`. Partida del ciclo: `f7a86cc`. Tag `v1.3.0` → `b778292`.
> Tarea viva: Track C **no** se abre sin aprobación línea a línea de Track B. Gates (409, ExecuteTrade post-lock, scheduler) siguen en decisión. Higiene E8 continua (residuos/docs obsoletos) sin purge de `pending-delete` alto. Coordinación SIEMPRE desde GitHub (commit+push; working tree ≠ estado).
> Batería: ruff 0 · mypy zona · pytest A2/A3/A4 · `verify_financial_invariants.py` EXIT 0 · `verify_ledger_balance_chain.py` EXIT 0.

## 4. Siguiente producto (decisión del propietario)

1. Aprobar o rechazar hipótesis Track B (mesa 5 puertas: Universo · Señales · Dictamen · Confirmar · Libro).
2. Si se aprueba: abrir Track C como fases FE acotadas (una por subagente).
3. Opcional: tag `v1.4.0` BETA **solo** si el propietario lo pide.
