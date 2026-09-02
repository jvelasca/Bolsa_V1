# Relevo — V1.71 Identity & Certification

> **AsOf:** 2026-09-02 · **Estado:** CERRADA (código + tests locales) · **Auditor:** [`arranque-auditor-v1-71-identity-certification-2026-09-02.md`](./arranque-auditor-v1-71-identity-certification-2026-09-02.md) · **Partida:** V1.70 `960383d2` · **Commit:** pendiente (no stamp CI GREEN)

## Hecho

- POV backend recibe recon OI-6; cliente overlay live drift/unavailable sobre wire (`BLOQUEADO`)
- `source` wire=`canonical` vs rebuild=`blob` + `data-pov-source`
- Copy `REVISAR` para unknown/failed/recon; headlines T2 ejecutado / Recon drift
- `assertNever` en Decision Surface, F2 `formatExecutionStateCopy`, POV labels
- E2E: SKIP solo entorno; fixture/producto ausente o buy no-OK = FAIL
- Identidad DOM lista/HUD/chart/cockpit; GP-V170 aserta IDs + niveles
- Focus único: open-hit, Asesor, Estilos, lista multi/search
- Golden POV TS/Python (T2_EXECUTED→MONITOR, DRIFT→BLOQUEADO, 5 orígenes, origin inválido drop)
- Python POV `resolve_paper_desk_next_action` alineado al subconjunto TS (protected/reduced/exited → MONITOR)

## Reservas que V1.71 **no** cierra

- Playwright integrado sigue **opt-in** en CI (`run_e2e_integration` default false)
- V1.70 `960383d2` **no** se reetiqueta CI GREEN
- Parse drop vs factory coerce (`build_position_revision` origin inválido → `"stop"`) — contrato: parse = drop

## Next candidato

Post-V1.71 aparcado: WHY rico (V1.72) · Paper Autonomous Day (V1.74) · bump package · **NO LIVE**.
