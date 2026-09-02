# Relevo — V1.76 Certification Hardening

> **AsOf:** 2026-09-02 · **Estado:** CERRADA (código + E2E mock locales) · **Auditor:** [`arranque-auditor-v1-76-certification-hardening-2026-09-02.md`](./arranque-auditor-v1-76-certification-hardening-2026-09-02.md) · **Partida:** V1.75 `b5b114ff` · **sin stamp CI GREEN**

## Hecho

- DailyDesk `reasonCode` + `data-reason-code` (deny `ENTRY_STALE_DATA`)
- Fixture stale: notes sin «AUTO armado»; UNKNOWN aislado (`hoyUnknown` / `ord-unknown-001`)
- Mock `/data-status` echo del `instrumentId` pedido
- Badge `chart-data-status` · cockpit `data-execution-lifecycle`
- E2E: GP-V175-01/03/04 endurecidos (4 passed) · GP-V176-01 causalidad (1 passed) · GP-V174 regresión (5 passed)
- Spec/plan/auditor V1.76 · CURRENT_SYSTEM · engineering-index

## Reservas

- Certificación cierre = **mock E2E** + unitarios locales
- **No** stamp CI GREEN · **No** `dryRun=false` browser
- Pytest GP-V175-05..07 intactos (no reabiertos)

## Next candidato

**V1.77** Session Reliability / Operational Truth — docs abiertos:

- [`spec-v177-session-reliability-2026-09-02.md`](./spec-v177-session-reliability-2026-09-02.md)
- [`plan-v177-session-reliability-2026-09-02.md`](./plan-v177-session-reliability-2026-09-02.md)

Journey mock: A→B→C→A→refresh→stale→recovery→UNKNOWN→recon→clean. **NO LIVE**. Golden MERCADO→EXIT = V1.78+.
