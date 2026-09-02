# Plan — V1.88 Lifecycle Integrated Golden + Restart + Recon

> **Padre:** [`spec-v188-lifecycle-integrated-golden-2026-09-02.md`](./spec-v188-lifecycle-integrated-golden-2026-09-02.md).  
> **Estado:** **CÓDIGO LISTO** · pendiente stamp CI GREEN / tag. Partida V1.87 PASS operacional [`646b97ac`](https://github.com/jvelasca/Bolsa_V1/commit/646b97ac).

| ID  | Entrega                                                        | Estado    |
| --- | -------------------------------------------------------------- | --------- |
| D0  | respuesta auditor V1.87 + spec/plan V1.88                      | **DONE**  |
| P0  | Golden HTTP trail JWT + PG (OPEN→CLOSED)                       | **DONE**  |
| P0  | Restart: lifespan teardown → nueva app → GET ≡ snapshot        | **DONE**  |
| P1  | Recon drift incident mid-journey + recovery + continue EXIT    | **DONE**  |
| P1  | User B 403 en el mismo golden · CI lifecycle-pg incluye golden | **DONE**  |
| —   | Docs CURRENT_SYSTEM · index · relevo                           | **DONE**  |
| —   | Tag `v1.88-beta` / CI remoto GREEN                             | posterior |

## OUT

- LIVE · bump · browser integrated obligatorio · unificar ledger · market quote producción
- Commitear `**/logs/`
