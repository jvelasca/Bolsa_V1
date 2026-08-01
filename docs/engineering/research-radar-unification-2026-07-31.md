# Research → Radar → Paper — unificación (2026-07-31)

> Pausa estratégica convertida en contrato de producto.  
> Complementa [FIE](./fundamental-intelligence-engine-2026-07-30.md), [ADR-010](../adr/010-platform-kernel-radar-execution.md), [research-lifecycle](./research-lifecycle.md).

**AsOf:** 2026-07-31

---

## 1. Decisiones bloqueadas (esta iteración)

| # | Tema | Decisión |
|---|------|---------|
| 1 | Backtest de estrategias | **Solo TA** (precio/volumen/indicadores). FA no entra en el motor BT. |
| 2 | Coach FA paralelo | **No.** Score_FUND + Composite ya puntúan. Coach = embudo técnico. |
| 3 | Horizontes | FA = qué / estructural (lento). TA = cuándo / timing (TF del kernel `1d`/`1wk`). |
| 4 | Puertas Paper | **A ≠ B ≠ C ≠ D** (no unificar en un solo «auto»). |
| 5 | Puente vital | **Finalistas → Rastreador** (estrategia #1 u slot con `strategyDefinitionId`). |
| 6 | LLM | Explica / narra; **nunca** calcula ratios ni firma órdenes. Botón **IA** informativo en superficies LLM. |
| 7 | Cuenta | **Una activa**; hoy solo **DEMO** (`simulated`). Tipo Paper = broker real futuro. |

```text
Universo → [Gate / Score FA] → Embudo técnico (Coach/Lab) → Finalistas
         → Composite (Monitor)
         → Rastreador (Radar B) · Checklist demo (A) · Proponer F3 (C) · Plan D
         → Ledger de la cuenta ACTIVA (DEMO)
```

---

## 2. Benchmark (resumen)

| Plataforma | Fortaleza | Hueco | Cómo ganamos |
|------------|-----------|-------|--------------|
| TradingView | Charts, alertas, paper, estrategias | FA flojo; auto vía webhook | Embudo + FA determinista en la misma app |
| Finviz | Screener FA+TA rápido | Sin coach TOP ni cartera | FA whitelist + Coach + Radar |
| Trade Ideas | Scanner + Holly timing | FA secundario; US-first | Radar sobre Finalistas EU+US |
| Stock Rover | FA + portfolios | Sin BT/Coach pro | FA ya + Paper modes |
| TipRanks / tOS | Scores / PaperMoney+TA | Mitades del puzzle | Bucle Research→Radar→Execution cerrado |

---

## 3. Contrato Finalistas → Rastreador (Camino B)

**Entrada:** `InstrumentStrategyTop` slot con `strategyDefinitionId` (prioridad `#1`).  
**Salida:** `CreateTrackerDefinitionDto` con:

| Campo | Valor |
|-------|--------|
| `name` | `Radar · {symbol} · #{rank} {label}` |
| `strategyDefinitionId` | del slot |
| `universe` | `{ instrumentIds: [instrumentId] }` (o `listId` si se pasa) |
| `timeframe` | TOP TF si es kernel (`1d`/`1wk`); si no → `1d` |
| `schedule` | `manual` por defecto (usuario puede pasar a `on_bar_close`) |
| `origin` | `assisted` |
| `sourcePrompt` | `finalist:{instrumentId}:{timeframe}:r{rank}:v{version}` |
| `defaultExecutionPolicyId` | opcional (inform/alert/paper_auto) |

**No hace:** desplegar paper, ejecutar órdenes, mezclar con Checklist (A) ni Paper D.

**UI:** CTA **Rastreador** en Finalistas → crea tracker → deep-link `/screeners`.

---

## 3b. Alarmas B1 (inform / alert)

Tras `POST /trackers/{id}/scan` (sync) o job async con `trackerDefinitionId`:

1. Si `defaultExecutionPolicyId` apunta a modo **`inform_only`** o **`alert`**, se auto-enruta.
2. `paper_auto` / `live_auto` **no** se auto-ejecutan (CTA manual «Ejecutar política»).
3. Respuesta incluye `alarmRoute`; la UI emite toasts «Radar · SYMBOL: Entrada/Salida».
4. **Inbox Trading (B1.1):** las mismas alarmas se guardan en el cliente (`bolsa-tracker-alarm-inbox-v1`), filtradas por **cuenta activa DEMO**. Campana en la barra de estado Trading → abrir valor / marcar leídas.
5. **Poller schedule (B1.2):** `TrackerAlarmInboxPoller` en `PlatformShell` consulta `GET /api/scans/jobs` (~12s). Jobs de rastreador `completed` con `alarmRoute` (p. ej. `on_bar_close`) alimentan el inbox **sin** tener Screeners abierto.
6. **F3 desde alarma (B1.3):** CTA **F3** en cada fila del inbox → `proposeRecommendation` → cola Supervisado (origen `alarm`) → Confirm humano. No ejecuta sola.

Código: `bolsa_application.tracker_alarms` · `apps/web/.../tracker-alarms.ts` · `stores/tracker-alarm-inbox-store.ts` · `trading-alarm-inbox-button.tsx` · `tracker-alarm-inbox-poller.tsx`.

Premisa cuentas: [account-premises-demo-vs-paper-2026-07-31.md](./account-premises-demo-vs-paper-2026-07-31.md).

---

## 4. Fases de producto

| Fase | Qué | Estado |
|------|-----|--------|
| A | Research TA + FA panel + Composite | ✅ |
| B0 | CTA Finalistas → Tracker | ✅ |
| B1 | Alarmas entrada/salida (inform/alert) auto tras scan | ✅ |
| B1.1 | Inbox Trading (barra estado · cuenta activa DEMO) | ✅ |
| B1.2 | Schedule `on_bar_close` → inbox (poller global) | ✅ |
| B1.3 | Proponer Supervisado F3 desde fila de alarma | ✅ |
| C | Screeners FA + TA → listas vivas | parcial (FA ✅) |
| D | Paper modes cableados a trackers | parcial (policies ✅; execute off) |
| E | Botón IA informativo en LLM | ✅ |

---

## 5. Relacionados

- Premisa cuentas: [`account-premises-demo-vs-paper-2026-07-31.md`](./account-premises-demo-vs-paper-2026-07-31.md)
- Hub Instrumentos (vista por valor; seguimiento = Radar): [`instruments-hub-2026-07-31.md`](./instruments-hub-2026-07-31.md)
- Copy: `apps/web/src/features/settings/paper-paths-copy.ts`
- Helper Finalistas→Tracker: `apps/web/src/features/backtests/promote-finalist-to-tracker.ts`
- IA UX: `docs/engineering/pending-delete/NEXT-IA-BUTTON.md`
