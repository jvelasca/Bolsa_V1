# Arranque auditor externo — v1.25-beta (2026-08-28)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 post-tag **`v1.25-beta` → `d3c2fd6b`**.

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-tag-v1-25-beta-2026-08-28.md`](../engineering/traspaso-relevo-tag-v1-25-beta-2026-08-28.md)
3. [`docs/engineering/traspaso-relevo-v1-25-operational-safety-2026-08-28.md`](../engineering/traspaso-relevo-v1-25-operational-safety-2026-08-28.md)
4. [`docs/engineering/contrato-confirm-v125-ticket-2026-08-28.md`](../engineering/contrato-confirm-v125-ticket-2026-08-28.md)
5. [`docs/engineering/analisis-vs-apps-top-operative-flow-2026-08-28.md`](../engineering/analisis-vs-apps-top-operative-flow-2026-08-28.md)
6. [`docs/adr/040-user-information-architecture.md`](../adr/040-user-information-architecture.md) §10 (Operative Flow)
7. Pack histórico: [`docs/engineering/audit-pack-estado-global-2026-08-27-v121.md`](../engineering/audit-pack-estado-global-2026-08-27-v121.md)

CI release tag: [GREEN](https://github.com/jvelasca/Bolsa_V1/actions/runs/33149344989).

**Preguntas de foco (V1.25 operational safety — no nuevos motores ni nav L1):**

1. ¿Confirm default muestra riesgo €, R y % cartera cuando hay TradePlan TRIGGERED (no `riskPct` oculto)?
2. ¿What-if Antes→Después en ticket reutiliza el mismo modelo que Mesa (`buildPortfolioScenario`)?
3. ¿Propose con plan TRIGGERED usa qty del plan (no `% caja` como autoridad)?
4. ¿Stop editable invalida firma stale y recalcula R (`signedStop`)?
5. ¿Assessments y trailing quedan bajo «Ajustes avanzados» (ticket slim intacto)?

**Deuda explícita a validar como aparcada (no implementar):** V1.26 lifecycle · V1.27 Mercado operativo/drag · V1.28 UX 10/10 · Lab `risk_policy` · OpportunityScore · VaR/correlación · thaw · AUTO.

**No pedir:** nav L1 nueva · drag gráfico · móvil · AUTO/thaw · OpportunityScore · promover thin trail a autoridad · colapsar Hoy.

---

Opcional en paralelo (solo si el owner lo pide): Bugbot / Security Review sobre `branch changes` del release.
