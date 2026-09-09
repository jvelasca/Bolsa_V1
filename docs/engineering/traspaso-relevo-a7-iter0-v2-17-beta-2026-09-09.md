# RELEVO — Iter-0 de LIVE Certification / A7 (marco + gap-map documental) — 2026-09-09

> **Base:** `main` en `b8858c2f` (v2.16.1-beta GREEN registrado: SHA `1596f4ad`, tag `v2.16.1-beta`,
> Release-tag CI `#34331846887` certify success).
> **Este ciclo:** `v2.17-beta`, **1.47.0-beta**. Iter-0 de A7 **SOLO documental** (marco + mapa de gaps),
> según el veredicto de la auditoría externa V2.16.1 (P0=0/P1=0/Global 9.3): **no añadir features**.
> Núcleo financiero congelado **intacto**. Alembic head `023_ohlcv_bars_unique_reconcile` (sin migración).

## 1. Qué entrega la Iter-0

No hay código ni tests nuevos. El entregable es **frameworks + gap-map** que decide los gates de la Iter-1:

1. **`docs/engineering/plan-a7-live-certification-gap-map-2026-09-09.md`** — mapeo de los **16 escenarios**
   del auditor (Grupos A/B/C) con fuente `ruta:línea`, dobles a reutilizar y estado
   `🟢 cubierto / 🟡 parcial / 🔴 gap`. Verificaciones de ruta hechas 1ª mano (no inferidas).
2. **Cierre del hallazgo P2-05 (punto 9 de la auditoría):** la incoherencia doc(code-estado) ya estaba
   resuelta en `b8858c2f`; se constata aquí y en el plan (§1bis) para el auditor.
3. **Home de la batería (Iter-1) registrado:** `packages/py/infrastructure/tests/chaos/live_a7/` (PG-real),
   gate en el job `lifecycle-pg` del release-tag CI; dobles canónicos a reutilizar.
4. **Backlog A7 priorizado (Iter-1+):** vers §5 del plan (C3 🔴 crash-injection sobre `scheduler_worker`,
   A3 timeout/network real, B2 partial-fill, P2-01 Applied durable).
5. **Deuda pos-p3 actualizada** en `deuda-p3-nucleo-aceptada-c2-2026-09-09.md`: el ítem
   `[runtime/aislamiento] LIVE A7` pasa de "cola" a "Iter-0 en curso → Iter-1 backlog con home definido".

## 2. Mapa de gaps (resumen para el relevo)

| Grupo                                  | Escenarios                                                                                                                   | Estado dominante |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| A — Orden/FSM/adaptadores              | A1 Kill Switch 🟢 · A2 Order FSM 🟡 · A3 Broker timeout 🟡                                                                   | 🟡               |
| B — Fills/idempotencia/materialización | B1 Idempotencia/Dup 🟢 · B2 Partial fill 🟡 · B3 Capture→apply 🟢 · B4 Dup materialización 🟢 · B5 Reconcile/ledger/drift 🟢 | 🟢               |
| C — Crash/restart/multi-worker         | C1 Unknown/recovery 🟡 · C2 Multi-worker 🟢 · **C3 Crash-injection `scheduler_worker` 🔴**                                   | 🔴 (C3)          |

El único 🔴 probado (no suite agregada) es **C3** → primer item de la Iter-1.

## 3. Verificación del ciclo

- Sin cambios de código/tests → ruff/mypy/import-linter no aplican.
- Mapa con rutas verificadas (Glob) contra el checkout real; cero afirmaciones de "batería pasando".
- Checklist manual §3 del plan: cada escenario con evidencia ruta:línea.

## 4. Elevación completada en GitHub (2026-09-09) y GREEN final

Ejecutado hasta dejar el repo dispuesto, con **elevación GREEN del ciclo v2.17-beta**:

- `origin/main` avanzado a **`79df594c`** (commit `docs(v2.17-beta / 1.47.0-beta): Iter-0 de LIVE
Certification A7`, trabajado limpio).
- Bump root **`1.47.0-beta`** (`1.46.1-beta → 1.47.0-beta`).
- Tag anotado remoto **`v2.17-beta`** → `79df594c` (creado vía push → evento `tag push`).
- **Release-tag CI `#34334824584`** — `conclusion: success`, jobs GREEN (~8 min):
  - `security (gitleaks)` ✓ · `shared` ✓ · `decision-spine` ✓ · `dr-verify` ✓
  - `python (ruff/imports/mypy/pytest offline)` ✓ · `lifecycle-pg` (alembic/auth/golden/identity + iso
    real-PG 43) ✓ · `frontend (+contract:check)` ✓ · `playwright (mock E2E)` ✓
  - agregador **`certify (aggregate + artifact)` ✓ = GREEN**.
  - `playwright (integrated E2E, opt-in)` skipped (job opt-in; no es requisito de GREEN).
- Trabajo local limpio; `main` sincronizado con `origin/main`, sin ahead/behind.

**GREEN FINAL CERTIFICADO para `v2.17-beta` (Iter-0 de LIVE Certification / A7)**, únicamente documental
(marco + gap-map), núcleo financiero congelado intacto → listo para decidir la Iter-1 (batería A7) con el
home y el backlog ya fijados.

FIN DEL RELEVO — Iter-0 de **LIVE Certification / A7** definida y elevada a `v2.17-beta`
(origin/main `79df594c` + tag remoto). Release-tag CI `#34334824584` GREEN (`certify` success). Backlog
y home de la batería listos para Iter-1.
