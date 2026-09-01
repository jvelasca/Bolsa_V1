# Arranque auditor externo — V1.59→V1.60 stack (UX Mercado POV) (2026-09-02)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **stack V1.59 E2E Integrated → V1.60 UX Mercado**. Producto bajo revisión **`V1.60` implementación CERRADA**, tag **`v1.60-beta`**. Partida certificada **`v1.59-beta` → `b5c5c6ab`**. El stack **no** abre LIVE ni cambia Confirm SEMI. `PAPER_D_EXECUTE` default **off**. Package congelado **`1.35.0-beta`**.

**Alcance:** V1.59 stack **intacto** · V1.60 cierra brecha UI post-V1.57: panel **DECISIÓN** (`operativa-cockpit-card`) muestra **`PositionOperationalView`** en tarjeta estrella (`position-operational-star-card.tsx`) vía `positionOperationalViewFromBlob` / `buildPositionOperationalView`. GP-V160-01..04: POV state · T2_READY/T2_EXECUTED · RECONCILIATION_DRIFT · stopHistory colapsable · vitest + testids. **No** motores nuevos · **no** layout dock nuevo · **no** Playwright CI obligatorio.

**Contexto local (2026-09-02):** shared POV **18** · web Mercado **40** · V1.59 integration **7** · V1.58 block **13** · tsc OK.

**GitHub (auditor):**

- Partida certificada: [`v1.59-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.59-beta) → `b5c5c6ab`
- Tip V1.60: [`v1.60-beta`](https://github.com/jvelasca/Bolsa_V1/releases/tag/v1.60-beta)

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/spec-v160-ux-mercado-2026-09-02.md`](./spec-v160-ux-mercado-2026-09-02.md)
3. [`docs/engineering/plan-v160-ux-mercado-2026-09-02.md`](./plan-v160-ux-mercado-2026-09-02.md)
4. [`docs/engineering/traspaso-relevo-v1-60-ux-mercado-2026-09-02.md`](./traspaso-relevo-v1-60-ux-mercado-2026-09-02.md)
5. [`docs/engineering/spec-v159-e2e-integrated-2026-09-02.md`](./spec-v159-e2e-integrated-2026-09-02.md)
6. [`docs/engineering/spec-v157-operational-truth-2026-09-01.md`](./spec-v157-operational-truth-2026-09-01.md)
7. [ADR-042](../adr/042-operating-excellence.md)

**Preguntas de foco:**

1. ¿**GP-V160-01** construye POV desde blob `position.operational` y muestra `operatingState` + `primaryAction` display-only (sin BUY)?
2. ¿**GP-V160-02** distingue `T2_READY` vs `T2_EXECUTED` en copy y chip fase (`Posición · T2 listo` / `T2 ejecutado`)?
3. ¿**RECONCILIATION_DRIFT** usa copy alineada a Hoy (`reconPhraseFromPortfolioStatus`) y chip recon **CRITICAL** — **≠** `RECONCILIATION_ERROR`?
4. ¿**GP-V160-03** lista stop history con orígenes protect/trail/reduce/override/stop y deltas, colapsable por defecto?
5. ¿**GP-V160-04** vitest cubre fixtures GP-V157-01 T2 + drift con `data-testid` auditor?
6. ¿V1.59 integration (**7** tests) y V1.58 block (**13** tests) siguen verdes sin regresión?
7. ¿Freeze intacto: Confirm SEMI · `PAPER_D_EXECUTE` off · package **`1.35.0-beta`** · **no LIVE** · una CTA primaria intacta?

**Deuda aparcada:** encolar STRUCTURAL_STOP a apertura (LIVE) · thaw Accept (0/5 PASS) · TRUSTED_PROXIES IPs de producción (`BLOCKED_ON_OWNER`) · CI integration job en Release-tag · drag entry/T1/T2 en gráfico · segundo Mercado.

**No pedir:** LIVE · bump package · Playwright full stack obligatorio · motores ranking/decision nuevos · redesign Mesa cubos.

---
