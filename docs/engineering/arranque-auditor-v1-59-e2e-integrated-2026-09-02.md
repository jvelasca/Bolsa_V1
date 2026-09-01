# Arranque auditor externo — V1.58→V1.59 stack (E2E Integrated) (2026-09-02)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **stack V1.58 Adversarial Execution → V1.59 E2E Integrated**. Producto bajo revisión **`V1.59` implementación local CERRADA**, tag **`v1.59-beta` pendiente**. Partida certificada **`v1.58-beta` → `4c42f1fc`**. El stack **no** abre LIVE ni cambia Confirm SEMI. `PAPER_D_EXECUTE` default **off**. Package congelado **`1.35.0-beta`**.

**Alcance:** V1.58 stack **intacto** · V1.59 enfoque **A**: pytest + `httpx.AsyncClient` + PostgreSQL real (`@pytest.mark.integration`) · GP-V159-01..07 contra rutas FastAPI (trade/portfolio operational · paper-desk dry-run/gate · ops-self-eval recon · decision-journal · incident resolve/clear · execute-auto dry_run) · fix colateral `opening_gate_seed` (120 barras planas, sanity DS-05). **No** sustituye Golden Session pytest · **no** Playwright CI obligatorio · **no** UX Mercado · **no** motores nuevos.

**Contexto local (2026-09-02):** application V1.58 block **22** · integration V1.59 **7** · ruff OK.

**GitHub (auditor):**

- Partida certificada: [`v1.58-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.58-beta) → `4c42f1fc`
- Tip V1.59: working tree local (tag `v1.59-beta` aún no emitido)

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/spec-v159-e2e-integrated-2026-09-02.md`](./spec-v159-e2e-integrated-2026-09-02.md)
3. [`docs/engineering/plan-v159-e2e-integrated-2026-09-02.md`](./plan-v159-e2e-integrated-2026-09-02.md)
4. [`docs/engineering/traspaso-relevo-v1-59-e2e-integrated-2026-09-02.md`](./traspaso-relevo-v1-59-e2e-integrated-2026-09-02.md)
5. [`docs/engineering/spec-v158-adversarial-execution-2026-09-01.md`](./spec-v158-adversarial-execution-2026-09-01.md)
6. [`docs/engineering/traspaso-relevo-v1-58-adversarial-execution-2026-09-01.md`](./traspaso-relevo-v1-58-adversarial-execution-2026-09-01.md)
7. [ADR-043](../adr/043-position-automation.md)

**Preguntas de foco:**

1. ¿**GP-V159-01** demuestra buy HTTP → `GET /portfolio` con posición y `operational` coherente sin bypass de `check_opening`?
2. ¿**GP-V159-02/03** certifican paper-desk `dryRun=true` sin mutación y `dryRun=false` → **403** `paper_auto_env_blocked` con `PAPER_D_EXECUTE` off?
3. ¿**GP-V159-04** excluye `drift` en cuenta limpia post-trade (`portfolioReconciliation.status` ∈ `ok`/`clean`/`not_wired`)?
4. ¿**GP-V159-06** reproduce DEX-3 por HTTP: resolve con nota → clear **409** si recon drift → heal → clear **200** — sin auto-heal?
5. ¿El fix **`opening_gate_seed`** (serie plana 120d) elimina veto sanity split/dividendo sin relajar DS-05?
6. ¿V1.58 block (**22** tests) sigue verde sin regresión?
7. ¿Freeze intacto: Confirm SEMI · `PAPER_D_EXECUTE` off · package **`1.35.0-beta`** · **no LIVE**?

**Deuda aparcada:** V1.60 UX Mercado · encolar STRUCTURAL_STOP a apertura (LIVE) · thaw Accept (0/5 PASS) · TRUSTED_PROXIES IPs de producción (`BLOCKED_ON_OWNER`) · CI integration job en Release-tag.

**No pedir:** LIVE · bump package · Playwright full stack obligatorio · re-certificar GOLDEN-DAY-ADV vía HTTP · scheduler · Alembic · rediseño Mesa/Mercado.

---
