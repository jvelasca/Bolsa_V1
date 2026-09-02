# Relevo — V1.72 Decision Explainability TOP

> **AsOf:** 2026-09-02 · **Estado:** CERRADA (código + tests locales) · **Auditor:** [`arranque-auditor-v1-72-decision-explainability-top-2026-09-02.md`](./arranque-auditor-v1-72-decision-explainability-top-2026-09-02.md) · **Partida:** V1.71 `b70849bd`

## Hecho

- `DecisionExplainView` schema **1.1.0**: score X/10 · `thesisDirection` LONG/SHORT/ESPERAR/REDUCIR/SALIDA (**nunca COMPRAR**) · factors pass/fail/unknown · levels · entryGeometry · authorization
- Panel Mercado TOP + testids; unknown no se pinta como check verde
- `markPrice` en plan de estudio / EntryOperatingTruth; Entry Compact muestra Precio actual + Distancia solo si hay mark; **sin** Ideal/Máxima
- Espejo Python + goldens
- `T2_READY` headline «T2 alcanzado» · frase «mesa MONITOR»; `resolvePaperDeskNextAction` **intacto**
- Cockpit pasa `markPrice` (prop + `position.lastPrice`); panel DECISIÓN lee lastClose del catálogo en caché (sin feed nuevo)

## Reservas que V1.72 **no** cierra

- TA `momentum`/`volume` siguen `unknown` si el cockpit no recibe `taComponents` (fail-closed correcto)
- Distancia omitida si no hay `plan.entry` (AAF demo: Precio actual sí, distancia no)
- Playwright integrado sigue opt-in; **no** stamp CI GREEN

## Next candidato

Post-V1.72 aparcado: ~~Multi-instrument integrity (V1.73)~~ **CERRADA** · Paper Autonomous Day (V1.74) · bump package · **NO LIVE**.
