# RELEVO — V1.53 Golden Session (2026-09-01)

> **Padre:** [`spec-v153-golden-session-2026-09-01.md`](./spec-v153-golden-session-2026-09-01.md) · [ADR-043](../adr/043-position-automation.md) · tip certificado previo **`v1.52-beta` → `9725e9e7`**.  
> **Estado:** **CÓDIGO** — commit `e93c4b9a` · tip `v1.53-beta` → `9725e9e7` **certificado** ([relevo tag](./traspaso-relevo-tag-v1-53-beta-2026-09-01.md)). Package `1.35.0-beta` congelado. **No** LIVE.

---

## 0. Qué cierra

| Pieza                                                  | Estado   |
| ------------------------------------------------------ | -------- |
| GP-SESSION-01 Estudio 09:00 → 1 Position (identidades) | DONE     |
| GP-SESSION-02 protect → T1 → TRAIL×2 → exit            | DONE     |
| GP-SESSION-03 TargetLeg + revision enrich en sesión    | DONE     |
| GP-SESSION-04 `PaperDailyReport` `position_exited=1`   | DONE     |
| V1.48 Golden Session (HonestStub)                      | intacto  |
| V1.52 lifecycle GPs                                    | intactos |

```text
09:00 EstudioPaperDeskEntry → fill → Position
10:00 protect
11:00 T1 reduce → target1Leg.executed
12:00–13:00 TRAIL×2 (decisionId + policyId)
16:00 stop → CLOSED → build_paper_daily_report
```

## 1. Pre-flight

```bash
pytest packages/py/application/tests/test_paper_desk_golden_session_estudio.py packages/py/application/tests/test_paper_desk_golden_session.py packages/py/application/tests/test_paper_desk_lifecycle.py -q
uv run ruff check packages/py apps/api-python --config pyproject.toml
pnpm --filter @bolsa/web exec tsc --noEmit
```

Bloque V1.52 + GP-SESSION-01..04 · regresión V1.48/V1.52 · ruff OK · tsc OK · Release-tag CI **GREEN** (tip mypy-unblock `9725e9e7`).

## 2. Freeze

Confirm = firma · `PAPER_D_EXECUTE` off · no LIVE · sin UI Mesa · sin scheduler · package `1.35.0-beta`.

## 3. OUT / parked

- **V1.54** Operating Desk (UI Mesa · excepción cubo)
- browser E2E Journal · scheduler · LIVE · rankingEngineId

## 4. Next

1. Tip `v1.53-beta` **certificado** (CI GREEN) — golden session en `e93c4b9a`, tip en `9725e9e7` (mypy retag como v1.52).
2. **V1.54** Operating Desk — **NO LIVE**.
