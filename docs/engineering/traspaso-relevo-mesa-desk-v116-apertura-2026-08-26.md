# RELEVO — apertura Mesa desk V1.16–V1.19 (2026-08-26)

> **Padre:** [`plan-mesa-desk-v116-v119-2026-08-26.md`](./plan-mesa-desk-v116-v119-2026-08-26.md) · [`roadmap-v116-mesa-desk-2026-08-26.md`](./roadmap-v116-mesa-desk-2026-08-26.md).  
> **Partida:** tag **`v1.15-beta` → `fc2ed753`**. HEAD docs: `37f6220f`.  
> **Estado:** **PRE-TAG** — MD-0…MD-7 docs listos; commit + tag pendiente owner.  
> **Owner:** **no elevar** hasta aviso “preparado para auditar”.  
> **Arranque agente:** este relevo + plan § fase asignada + ADR-037.

---

## 0. Qué ya existe (no reimplementar)

Código sin commit (~35 ficheros):

- **Shared:** `mesa-next-action`, `mesa-protection-state`, `decision-journal-relevant-delta`, `mesa-operable-ranking`, cambios `mesa-hoy-model`, `evidence-engine`
- **Web Mesa:** header operativo, alertas, what-if, position-route (no cableado), error boundary, filas/paneles
- **Web Confirm/F3:** `f3-trade-plan-risk-first-block`, boundary Confirm
- **Backend:** pickle checksum, ENV allowlist, router PAPER_D, paper_d account, edge_report, sanity→DS-05 param

**Tests GREEN (2026-08-26, actualizado):**

```bash
pnpm --filter @bolsa/shared exec vitest run mesa-next-action mesa-protection mesa-hoy  # 34 passed
pnpm --filter @bolsa/web test -- mesa-hoy  # 11 passed
pnpm test:decision-spine  # 485 passed
```

Relevos cerrados: MD-0 baseline · MD-1 tests · MD-2 v117 · MD-5 backend — ver roadmap.

**Dev stack:** `pnpm dev` arranca API :8000 + Web :5173 (verificar con `curl.exe http://127.0.0.1:8000/api/health`).

---

## 1. Gaps P0 (bloquean tag)

| #   | Gap                                        | Agente                                                     | Fase      | Estado                    |
| --- | ------------------------------------------ | ---------------------------------------------------------- | --------- | ------------------------- |
| 1   | Matriz tests semánticos V1.16 completa     | [F1 V1.16 tests](a91b2713-fd3e-459a-b5f3-74bb24efdd60)     | MD-1      | **CERRADO**               |
| 2   | Smoke browser Mesa (5 escenarios plan §F6) | [F1-G browser smoke](8f21872f-7f43-4bf0-b5f3-59106103f790) | MD-1/MD-6 | **CERRADO** — 5/5 PASS    |
| 3   | Tests backend nuevos                       | [F5 backend](5587d202-55f1-4a3d-af36-d5fe21750a47)         | MD-5      | **CERRADO**               |
| 4   | `pnpm test:decision-spine` post-cambios    | shell                                                      | MD-6      | **485 passed**            |
| 5   | CHANGELOG + pack v116 + relevo tag         | [MD-7 docs release](b34060f1-2eca-4698-9190-28e928dce699)  | MD-7      | **DOCS LISTOS** — SHA TBD |

---

## 2. Gaps P1 (cerrar o declarar en tag)

| #   | Gap                                               | Fase |
| --- | ------------------------------------------------- | ---- | --------------------------------------- |
| 6   | `showRoute` en posiciones Mesa/Libro              | MD-2 | **CERRADO** en `/mesa` · Libro post-tag |
| 7   | Invalidación riesgo qty/precio en F3              | MD-2 | **CERRADO**                             |
| 8   | Tests `mesa-operable-ranking`                     | MD-4 | **CERRADO** — 13 tests                  |
| 9   | `sanity_warnings` wired a `check_opening` runtime | MD-5 | **P1 post-tag** (relevo backend)        |
| 10  | `require_role` en CURRENT_SYSTEM                  | MD-5 | **CERRADO**                             |

---

## 3. Orden de agentes (no saturar)

```text
1. shell        → baseline + spine (MD-0/MD-6)
2. parallel:
   generalPurpose → MD-1 tests
   generalPurpose → MD-2 showRoute + F3 invalidación
   generalPurpose → MD-5 backend tests + wiring
3. generalPurpose → MD-3/MD-4 cierre + tests
4. shell        → MD-6 full battery
5. generalPurpose → MD-7 docs (pack + relevo tag)
6. Owner        → auditar → tag (MD-7)
```

Cada agente cierra **un relevo** antes de pasar al siguiente epic.

---

## 4. Relevos hijos (crear al cerrar fase)

| Fase | Relevo                                                                                         |
| ---- | ---------------------------------------------------------------------------------------------- |
| MD-1 | `traspaso-relevo-mesa-desk-v116-2026-08-26.md`                                                 |
| MD-2 | `traspaso-relevo-mesa-desk-v117-2026-08-26.md`                                                 |
| MD-3 | `traspaso-relevo-mesa-desk-v118-2026-08-26.md`                                                 |
| MD-4 | `traspaso-relevo-mesa-desk-v119-2026-08-26.md`                                                 |
| MD-5 | `traspaso-relevo-mesa-desk-backend-2026-08-26.md`                                              |
| MD-7 | `traspaso-relevo-tag-v1-16-beta-2026-08-26.md` + `audit-pack-estado-global-2026-08-26-v116.md` |

---

## 5. Freeze recordatorio

- Sin COMPRAR en ranking · Confirm única firma · sin motor ranking nuevo
- AUTO off · `PAPER_D_EXECUTE` off · LIVE experimental
- Proyección UI; dominio intacto (DEX, SubmitIntent, ConfirmRecommendationIntent)
- Honestidad: sin plan → — ; persist None → discrepancia

---

## 6. Señal al owner

**2026-08-26:** MD-0…MD-7 docs **LISTOS** ([MD-7 pack v116](b34060f1-2eca-4698-9190-28e928dce699)). Spine **485**. Limitaciones P1 declaradas (F1-H chip DS-05, sanity E2E, Libro showRoute, what-if sin gates).

> **Preparado para elevar `v1.16-beta` y auditar** — pendiente commit working tree + pin SHA + tag owner.

Hasta commit explícito: **no push de tag**.
