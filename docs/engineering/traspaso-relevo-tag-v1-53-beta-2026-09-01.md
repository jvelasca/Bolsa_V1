# RELEVO — tag v1.53-beta → auditoría / CI (2026-09-01)

> **Padre:** [`traspaso-relevo-v1-53-golden-session-2026-09-01.md`](./traspaso-relevo-v1-53-golden-session-2026-09-01.md) → [`traspaso-relevo-tag-v1-52-beta-2026-09-01.md`](./traspaso-relevo-tag-v1-52-beta-2026-09-01.md) → [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md).  
> **Estado:** **CI GREEN** — tip `v1.53-beta` → `9725e9e7` → Release-tag CI **GREEN** → previo certificado **`v1.52-beta` → `9725e9e7`** (CI GREEN).  
> **Fuera:** LIVE · `PAPER_D_EXECUTE` default on · UI Mesa (V1.54) · scheduler · OCO · package bump.

---

## 0. Confirmación

Sobre tip previo `v1.52-beta` → `9725e9e7`:

| Pieza                                               | Entrega                                      |
| --------------------------------------------------- | -------------------------------------------- |
| Lab `evaluate-exits?executeTrades=true`             | 403 `lab_exit_execute_retired` (env on ⇒ OK) |
| `TargetLeg` pending/triggered/executed/failed       | JSONB TS+Py                                  |
| `PositionRevision.decisionId` + `policyId`          | protect/trail/reduce                         |
| `opening_fill_handle` + `RecoverOrphanOpeningFills` | GP-CRASH-01                                  |
| GP-EXIT-01/02/03 · GP-TRAIL-01/02 · GP-CRASH-01     | Estudio-born                                 |
| GP-DESK-07/08/05b / V1.48 CAOS                      | intactos                                     |

V1.53 Golden Session (código `e93c4b9a`; tip mypy-unblock como v1.52):

| Pieza                                                  | Entrega                                             |
| ------------------------------------------------------ | --------------------------------------------------- |
| GP-SESSION-01 Estudio 09:00 → 1 Position (identidades) | `test_paper_desk_golden_session_estudio.py`         |
| GP-SESSION-02 protect → T1 → TRAIL×2 → exit            | mismo día 09:00–16:00                               |
| GP-SESSION-03 TargetLeg + revision enrich en sesión    | `target1Leg.executed` · trail `decisionId/policyId` |
| GP-SESSION-04 `PaperDailyReport` `position_exited=1`   | store `CLOSED` → journal projection                 |
| V1.48 Golden Session (HonestStub)                      | intacto                                             |

Freeze: Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · no UI Mesa · package `1.35.0-beta`.

## 1. Release

| Pieza      | Valor                                                                                                            |
| ---------- | ---------------------------------------------------------------------------------------------------------------- |
| Tag tip    | `v1.53-beta` → `9725e9e7` (was `e93c4b9a`; mypy unblock — patrón v1.52 retag)                                    |
| Código     | `e93c4b9a` feat(v1.53) golden session + `9725e9e7` mypy fix (compartido con v1.52-beta)                          |
| Previo tip | `v1.52-beta` → `9725e9e7` (CI GREEN)                                                                             |
| CI tag     | **GREEN** — [Release tag CI](https://github.com/jvelasca/Bolsa_V1/actions/runs/33504130161) · `headSha=9725e9e7` |

Primer push `v1.53-beta` → `e93c4b9a` falló mypy ([run 33503637655](https://github.com/jvelasca/Bolsa_V1/actions/runs/33503637655)). Retag 2026-09-01 reutiliza el mismo `headSha` que v1.52-beta certificado ([run 33502192108](https://github.com/jvelasca/Bolsa_V1/actions/runs/33502192108)).

Jobs del push `v1.53-beta` (retag mypy 2026-09-01), todos **success**:

| Job            | Resultado |
| -------------- | --------- |
| python         | success   |
| shared         | success   |
| frontend       | success   |
| decision-spine | success   |
| security       | success   |
| certify        | success   |

## 2. Pre-flight

Bloque V1.52 + `test_paper_desk_golden_session_estudio.py` + regresión V1.48/V1.52 · ruff OK · tsc OK · Release-tag CI **GREEN**.

## 3. Residuals parked

- **V1.54** Operating Desk (UI Mesa)
- browser E2E Journal · scheduler · LIVE · rankingEngineId · perfil→política

## 4. Next

1. Tip `v1.53-beta` **certificado** (CI GREEN).
2. **V1.54** Operating Desk — **NO LIVE**.
