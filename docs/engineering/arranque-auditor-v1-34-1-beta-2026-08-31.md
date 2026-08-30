# Arranque auditor externo — v1.34.1-beta (2026-08-31)

Copia este bloque en un **chat nuevo** (auditor):

---

Eres auditor externo de Bolsa V1 post-tag **`v1.34.1-beta` → `4b2e3751`** (producto V1.34 Frente B-γ + tip CI GREEN).

Lee en este orden:

1. [`docs/CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)
2. [`docs/engineering/traspaso-relevo-tag-v1-34-1-beta-2026-08-31.md`](./traspaso-relevo-tag-v1-34-1-beta-2026-08-31.md)
3. [`docs/engineering/traspaso-relevo-v1-34-frente-b-drag-b-gamma-2026-08-30.md`](./traspaso-relevo-v1-34-frente-b-drag-b-gamma-2026-08-30.md)
4. [`docs/engineering/diseno-operativa-auto-grafico-ACORDADO-2026-08-30.md`](./diseno-operativa-auto-grafico-ACORDADO-2026-08-30.md)
5. [`docs/engineering/traspaso-relevo-tag-v1-34-beta-2026-08-30.md`](./traspaso-relevo-tag-v1-34-beta-2026-08-30.md) (histórico; CI tag RED)
6. Tag POM: [`docs/engineering/traspaso-relevo-v1-27-position-operating-model-2026-08-28.md`](./traspaso-relevo-v1-27-position-operating-model-2026-08-28.md)
7. Pack histórico: [`docs/engineering/audit-pack-estado-global-2026-08-27-v121.md`](./audit-pack-estado-global-2026-08-27-v121.md)

Python CI tip: [GREEN](https://github.com/jvelasca/Bolsa_V1/actions/runs/33339216149). Release-tag CI: pin tras push.

**Preguntas de foco (V1.34 B-γ + integridad CI — no nuevos motores ni nav L1):**

1. ¿El drag de stop solo en fases `preparada`/`posicion` y nunca en `disparada`?
2. ¿Commit G4 solo abre Confirm con `signedStop` (sin protect/execute API ni PositionRevision desde chart)?
3. ¿Geometría del ghost reutiliza `validateOperationalLevels` (fail-closed si inválido)?
4. ¿Freeze intacto: Confirm = firma · `PAPER_D_EXECUTE` off · AUTO execute off · Ranking ≠ BUY · LLM no ejecuta?
5. ¿Tip CI (ruff/mypy/pytest offline) GREEN y tags `v1.27-beta` / `v1.34.1-beta` coherentes con `CURRENT_SYSTEM`?

**Deuda explícita a validar como aparcada (no implementar):** B-δ · OCO · entry/T1/T2 drag · flip execute · UI histórico rico A6 · thaw estricto · OpportunityScore.

**No pedir:** nav L1 nueva · thaw · promover thin trail a autoridad · retag destructivo de `v1.34-beta`.

---

Opcional (solo si el owner lo pide): Bugbot / Security Review sobre el tip vs `v1.34-beta`.
