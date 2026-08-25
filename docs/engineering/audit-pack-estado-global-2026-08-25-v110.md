# Audit pack — estado global v1.10-beta (Operational Authority)

> **AsOf:** 2026-08-25 · **Tag:** `v1.10-beta` → `047ddb6`.
> **Padre:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · roadmap [`roadmap-v110-operational-authority-2026-08-25.md`](./roadmap-v110-operational-authority-2026-08-25.md) · ADR-033 · triage [`audit-ext-v19-ops-discontinuity-triage-2026-08-25.md`](./audit-ext-v19-ops-discontinuity-triage-2026-08-25.md).
> **Partida:** `v1.9-beta` → `7d90d965` · pack previo [`audit-pack-estado-global-2026-08-25-v19.md`](./audit-pack-estado-global-2026-08-25-v19.md).
> **Para:** auditoría externa / GitHub Actions Release tag CI.

---

## 0. Veredicto interno

Operational Authority v1.10 **CERRADA (H1→P4)**: el plan **sobrevive al fill** (Position persistida), el ticket **firma el riesgo del plan** (P2), la salida sigue **una cadena** (P3), y la mesa abre por **posiciones primero** (P4 Consola P4.1+P4.2). Producto sigue **BETA / no producción**. Broker **no**. Auto-exit producto **no**. Thin 5.x/8.x **congelados**. Confirm = **única** firma transaccional.

| Slice | Nombre                | Estado              |
| ----- | --------------------- | ------------------- |
| D0    | Triage + ADR-033      | CERRADO             |
| H1    | Honesty pending       | CERRADO             |
| H2    | Invariantes factories | CERRADO             |
| P1    | Position durable      | CERRADO             |
| P2    | Riesgo al firmar      | CERRADO             |
| P3    | Una cadena de salida  | CERRADO             |
| P4    | Consola de Mesa       | CERRADO (P4.1+P4.2) |

**Mensaje clave:** v1.9 modeló el post-entrada; v1.10 **gobierna** la operación real (persistencia, firma, salida, mesa). **No** god page `/console`. **No** sexta puerta. **No** broker en este tag.

---

## 1. Batería (local, pre-tag / verificación 2026-08-25)

| Gate                               | Resultado                                                 |
| ---------------------------------- | --------------------------------------------------------- |
| `pnpm test:decision-spine`         | **260** passed                                            |
| `pnpm --filter @bolsa/shared test` | **156** passed                                            |
| Vitest P4 Consola (7 ficheros)     | **21** passed                                             |
| Release tag CI                     | `release-tag-ci.yml` — tag `v1.10-beta` (sin path-filter) |

Comando P4 UI (referencia):

```bash
pnpm --filter @bolsa/web exec vitest run \
  src/features/operations/mesa-operational-bar.test.tsx \
  src/features/operations/mesa-entry-queue-panel.test.tsx \
  src/features/operations/propose-position-exit.test.ts \
  src/features/confirm/confirm-drawer.test.ts \
  src/features/help/hoy-en-la-mesa.test.tsx \
  src/features/help/mesa-tip-button.test.tsx \
  src/features/trading/f3-protect-stop-block.test.tsx
```

---

## 2. Qué entra en el tag

### Autoridad (H1→P3)

- **H1:** pending ≠ stop de posición (copy + HELP).
- **H2:** guards factories (`from_fill` TRIGGERED, stop no empeora, short close=buy, kill switch asimétrico).
- **P1:** Alembic `011` · tabla `position_states` · wire fill SEMI/pending → Position persistida.
- **P2:** ticket firma qty/riesgo del TradePlan · gate `risk_signature`.
- **P3:** ExitPlan → ExitPermission → Confirm cierre · persist `applyReduce` · `session-verdict` no_trade.

### Consola de Mesa (P4.1 + P4.2)

- Superficie **`/operations`** (Operaciones / Libro): posiciones enriquecidas (R, stop, T1/T2, salida advisory).
- CTAs **Revisar / Reducir / Salir** → cola Confirm (drawer); **no** ejecutan solos.
- Barra operativa + **barra estado global** (patrimonio, P&L, Confirm, excepciones, régimen).
- Cola entradas **read-only** + filtros (status, gate, símbolo).
- «No operar hoy» → Journal.
- **Proteger** CTA + preview stop/override en Confirm (**UI-only**; ticket `wait`).

### Infra / docs

- `.github/workflows/release-tag-ci.yml`
- ADR-033 · roadmap v1.10 · planes + relevos H1–P4 · HELP sync · `CURRENT_SYSTEM.md`

---

## 3. Qué no entra / parked

| Excluido                        | Notas                              |
| ------------------------------- | ---------------------------------- |
| Broker live / OCO / `stopPrice` | Fase explícita posterior           |
| Ruta `/console` god page        | No existe; mesa = `/operations`    |
| Auto-exit CTA producto          | CTAs encolan; Confirm = firma      |
| Protect persist backend         | P4.2 enqueue + preview only        |
| `PAPER_D_EXECUTE` default on    | Opt-in local; repo default **off** |
| Thaw estricto 60d/50/70/55      | Deuda abierta (runbook)            |
| ActionabilityScore predictivo   | Ordinal v0 only                    |
| Mappers thin 5.x/8.x nuevos     | Línea congelada                    |
| `contract:gen` / Alembic nuevos | Sin shape nuevo en este tag        |

---

## 4. Cadena de autoridad

```text
CURRENT_SYSTEM → ADR-033 → código → tests → HELP

Antes del fill:
  DecisionPackage → TradePlan → check_opening → Confirm SEMI (única firma apertura)

Después del fill:
  Position persistida (SoT plan) → ExitPlan → ExitPermission → Confirm SEMI (cierre)
  holding ledger = contabilidad (qty/P&L), no sustituye el plan

Mesa (P4):
  /operations — posiciones primero · cola entradas read-only · strip Hoy intacto (no sexta puerta)
```

Distinciones críticas para auditor:

- `check_opening` = veto **apertura** · `ExitPermission` = veto **salida** (distintos).
- Ranking / TOP / dictamen **≠ BUY**.
- Lab `EvaluatePositionExits` **≠** ExitPlan producto.
- Kill switch: bloquea entradas/AUTO; **desriesgo SEMI permitido** (H2).

---

## 5. Freeze (v1.10)

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · TradePlan ≠ permiso · ExitPlan ≠ auto-exit · SETUP Wyckoff cerrada · thin 5.x/8.x congelados · I1–I3 + RX1 intactos · `PAPER_D_EXECUTE` **off** · broker **no** · **BETA / no producción**.

---

## 6. Docs clave (lectura auditor)

| Tipo        | Documento                                                                                                        |
| ----------- | ---------------------------------------------------------------------------------------------------------------- |
| SoT vivo    | [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md)                                                                      |
| Contrato    | [`033-operational-authority-position-persistence.md`](../adr/033-operational-authority-position-persistence.md)  |
| Triage orig | [`audit-ext-v19-ops-discontinuity-triage-2026-08-25.md`](./audit-ext-v19-ops-discontinuity-triage-2026-08-25.md) |
| Roadmap     | [`roadmap-v110-operational-authority-2026-08-25.md`](./roadmap-v110-operational-authority-2026-08-25.md)         |
| Relevo tag  | [`traspaso-relevo-tag-v1-10-beta-2026-08-25.md`](./traspaso-relevo-tag-v1-10-beta-2026-08-25.md)                 |
| P4 cierre   | [`traspaso-relevo-p4-consola-mesa-2026-08-25.md`](./traspaso-relevo-p4-consola-mesa-2026-08-25.md)               |
| Operar SEMI | [`operar-semi-p4-consola-mesa-2026-08-25.md`](./operar-semi-p4-consola-mesa-2026-08-25.md)                       |
| Planes      | `plan-h1-*` … `plan-p4-consola-mesa-2026-08-25.md`                                                               |
| Relevos     | `traspaso-relevo-h1-*` … `traspaso-relevo-p4-*`                                                                  |

---

## 7. Checklist auditor (E1)

1. Checkout tag **`v1.10-beta`** (`047ddb6`).
2. Verificar GitHub Actions **`release-tag-ci.yml`** GREEN en el push del tag.
3. Ejecutar `pnpm test:decision-spine` → esperar **260** passed.
4. Contrastar ADR-033 §1–§7 con código: Position persistida, P2 firma, P3 cadena, P4 mesa.
5. Confirmar freeze §3: sin broker, sin auto-exit producto, sin god page.
6. Emitir triage/findings (formato histórico: `audit-ext-*-triage-*.md`).

**Preguntas que este pack no resuelve (fuera de scope):** broker adapter · protect persist · thaw estricto · ranking canónico versionado · reconciliación bróker plena.
