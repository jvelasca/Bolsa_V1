# Arranque auditor externo — v1.21-beta (2026-08-27)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 post-tag **`v1.21-beta` → `dad8f51c`**.

Lee en este orden:

1. [`docs/engineering/audit-pack-estado-global-2026-08-27-v121.md`](../engineering/audit-pack-estado-global-2026-08-27-v121.md)
2. [`docs/engineering/traspaso-relevo-tag-v1-21-beta-2026-08-27.md`](../engineering/traspaso-relevo-tag-v1-21-beta-2026-08-27.md)
3. [`docs/adr/041-operational-coherence.md`](../adr/041-operational-coherence.md)
4. [`docs/adr/040-user-information-architecture.md`](../adr/040-user-information-architecture.md) §7 (AdminRail)
5. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)

CI release tag: [GREEN](https://github.com/jvelasca/Bolsa_V1/actions/runs/33095441423).

**Preguntas de foco (BETA / coherencia — no nuevos motores):**

1. ¿Estudio es el **único** universo Daily Ops (TOP/funnel diario)?
2. ¿Hay **un** stop vigente = `currentStop`?
3. ¿AdminRail ≠ ⚙ (preferencias)?
4. ¿T1 es idempotente (`target1AchievedAt`)?
5. ¿Freeze SEMI intacto (Confirm = firma · trail solo propuesta · Ranking ≠ BUY)?

**Deuda explícita a validar como aparcada (no implementar):** OpportunityScore · correlación/VaR · thaw · AUTO.

**Propuesta post-v1.21 (consenso, no código):** [`traspaso-relevo-hoy-cobertura-estudio-propuesta-2026-08-27.md`](./traspaso-relevo-hoy-cobertura-estudio-propuesta-2026-08-27.md) — Hoy Command Center + Cobertura Estudio; tríada Actuar / Priorizar / Supervisar cobertura.

**No pedir:** OpportunityScore, VaR, thaw, AUTO, nuevas puertas L1, barras en Trading, auto-exit, promocionar thin trail a autoridad, listar 180 en Resumen/Journal.

---

Opcional en paralelo (solo si el owner lo pide): Bugbot / Security Review sobre `branch changes` del release.
