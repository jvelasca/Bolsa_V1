# Arranque auditor externo — V1.62→V1.63 stack (Decision Surface Placement) (2026-09-02)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **stack V1.62 Entry Decision Surface → V1.63 Decision Surface Placement**. Producto bajo revisión **`V1.63` implementación CERRADA**. Partida certificada **`V1.62` cerrada** (sin tag). El stack **no** abre LIVE ni cambia Confirm SEMI. `PAPER_D_EXECUTE` default **off**. Package congelado **`1.35.0-beta`**.

**Alcance:** V1.61/V1.62 **intactos** · V1.63 preferencia `bolsa-mercado-decision-surface-v1` (`panel` default · `chart` HUD) · `DecisionSurfaceCompact` compartido · `ChartDecisionSurfaceHud` · toggle cockpit + card Mercado en configuración · GP-V163-01..06. **No** motores nuevos · **no** sync cross-device · **no** drag niveles desde HUD.

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/spec-v163-decision-surface-placement-2026-09-02.md`](./spec-v163-decision-surface-placement-2026-09-02.md)
3. [`docs/engineering/plan-v163-decision-surface-placement-2026-09-02.md`](./plan-v163-decision-surface-placement-2026-09-02.md)
4. [`docs/engineering/traspaso-relevo-v1-63-decision-surface-placement-2026-09-02.md`](./traspaso-relevo-v1-63-decision-surface-placement-2026-09-02.md)
5. [`docs/engineering/spec-v162-entry-decision-surface-2026-09-02.md`](./spec-v162-entry-decision-surface-2026-09-02.md)
6. [`docs/UI_PREFS_LOCALSTORAGE.md`](../UI_PREFS_LOCALSTORAGE.md) §3

**Preguntas de foco:**

1. ¿**GP-V163-01** default `panel` sin regresión V1.61/V1.62?
2. ¿**GP-V163-02/03** panel muestra superficie · chart muestra hint sin duplicar cards en ESTADO?
3. ¿**GP-V163-04** HUD `chart-decision-surface-hud` gated por `showOperationalPlanLevels && placement === "chart"`?
4. ¿**GP-V163-05** ACCIÓN CTA en ambos modos · sin COMPRAR?
5. ¿**GP-V163-06** toggle cockpit y configuración comparten pref persistida?
6. ¿V1.59 integration (**7**) y V1.58 block (**13**) sin regresión?

**Deuda aparcada:** V1.64 Browser E2E integrado · LISTA→GRÁFICO→ACCIÓN · LIVE.

**No pedir:** LIVE · bump package · sync cross-device prefs · drag HUD.

---
