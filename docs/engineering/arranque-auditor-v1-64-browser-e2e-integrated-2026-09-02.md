# Arranque auditor externo — V1.59→V1.64 stack (E2E Integrated + Mercado UI) (2026-09-02)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 **stack V1.59 E2E Integrated → V1.64 Browser E2E Integrated**, incluyendo UX Mercado V1.60–V1.63. Producto bajo revisión **`V1.64` implementación CERRADA**. Partida certificada **`v1.59-beta`**. El stack **no** abre LIVE ni cambia Confirm SEMI. `PAPER_D_EXECUTE` default **off**. Package congelado **`1.35.0-beta`**.

**Alcance:**

- **V1.59** pytest + PostgreSQL (`GP-V159-01..07`) — **intacto**
- **V1.60–V1.62** Mercado POV + Entry Decision Surface — **intacto**
- **V1.63** panel vs gráfico Decision Surface (`GP-V163-01..06`)
- **V1.64** Playwright UI journeys: **GP-V164-UI-01** Journal · **GP-V164-UI-02** Consola · **GP-V164-UI-03** Mercado (`GP-E2E-03` mock + integración opt-in)

**Contexto local (2026-09-02):** ver pre-flight en [`traspaso-relevo-v1-64`](./traspaso-relevo-v1-64-browser-e2e-integrated-2026-09-02.md).

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/spec-v164-browser-e2e-integrated-2026-09-02.md`](./spec-v164-browser-e2e-integrated-2026-09-02.md)
3. [`docs/engineering/traspaso-relevo-v1-64-browser-e2e-integrated-2026-09-02.md`](./traspaso-relevo-v1-64-browser-e2e-integrated-2026-09-02.md)
4. [`docs/engineering/spec-v163-decision-surface-placement-2026-09-02.md`](./spec-v163-decision-surface-placement-2026-09-02.md)
5. [`docs/engineering/spec-v159-e2e-integrated-2026-09-02.md`](./spec-v159-e2e-integrated-2026-09-02.md)
6. [`docs/engineering/arranque-auditor-v1-61-market-decision-surface-2026-09-02.md`](./arranque-auditor-v1-61-market-decision-surface-2026-09-02.md)

**Preguntas de foco:**

1. ¿**GP-V164-UI-01/02** cargan Journal y Consola contra API real (`E2E_INTEGRATION=1`) sin mocks?
2. ¿**GP-E2E-03** demuestra toggle Panel/Gráfico en configuración Mercado (misma pref que cockpit)?
3. ¿V1.63 **no duplica** superficie en panel cuando `placement === chart`?
4. ¿**GP-V159-01..07** siguen verdes sin regresión?
5. ¿Freeze intacto: Confirm SEMI · `PAPER_D_EXECUTE` off · **no LIVE**?

**Comandos auditor (reproducibles):**

```bash
# Browser mock (sin PG)
E2E_RUN=1 pnpm --filter @bolsa/web e2e

# Browser integrado (requiere API :8000 + PG)
E2E_INTEGRATION=1 E2E_RUN=1 pnpm --filter @bolsa/web e2e -- gp-v164-ui

# HTTP integrado V1.59
python -m pytest apps/api-python/tests/integration/test_v159_e2e_paper_desk.py apps/api-python/tests/integration/test_v159_e2e_operational_wire.py -m integration -q
```

**Deuda aparcada:** CI Playwright obligatorio · LISTA→GRÁFICO→ACCIÓN · LIVE · DTO HTTP POV Python.

**No pedir:** LIVE · bump package · Confirm live en E2E · scheduler.

---
