# Roadmap — v1.10 Operational Authority

> **Padre:** [`audit-ext-v19-ops-discontinuity-triage-2026-08-25.md`](./audit-ext-v19-ops-discontinuity-triage-2026-08-25.md) · ADR-033 · gap [`adr-032-ops-authority-gap-2026-08-25.md`](./adr-032-ops-authority-gap-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **FASE CERRADA — H1→P4 CERRADOS.** Tag **`v1.10-beta` → `2ea53be2`**. Partida **`v1.9-beta` → `7d90d965`**. Broker adapter **no**.
> **Método:** operación **realmente gobernada**, no otra factory ni god page. No thaw. No broker. No LLM.

---

## 0. Por qué esta fase

v1.9 dejó el post-entrada **modelado**. El siguiente salto no es un panel ni un OrderIntent nuevo: es que el plan **sobreviva al fill** y sea la única autoridad de la posición viva.

```text
HONESTY (pending ≠ stop)
    │
    ▼
INVARIANTES (factories que no mienten)
    │
    ▼
POSITION PERSISTIDA  ← SoT post-fill
    │
    ├──────────┬──────────┐
    ▼          ▼          ▼
 FIRMA RIESGO  SALIDA     MESA (después)
 ticket≠%caja  una cadena  posiciones primero
```

Autoridad normativa:

```text
CURRENT_SYSTEM → ADR-033 → código → tests → HELP
```

ADR-032 sigue siendo el contrato de **objetos** v1.9. No se reabre.

---

## 1. Secuencia (no se salta)

| Slice  | Nombre                       | Qué                                                                                                                                 | Estado ahora            |
| ------ | ---------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| **D0** | Diseño / triage + ADR-033    | Congelar autoridad (gap) · **no código**                                                                                            | **CERRADO**             |
| **H1** | Honesty pending              | Renombrar UI a «orden pendiente a precio». HELP: pending ≠ stop de posición.                                                        | **CERRADO**             |
| **H2** | Invariantes factories        | `from_fill` exige TRIGGERED (o override). Stop no empeora. T2 ≠ T1 a ciegas. Short close=`buy`. Kill switch asimétrico.             | **CERRADO**             |
| **P1** | Position durable + wire fill | Alembic + snapshot TradePlan + `transactionId`. Fill SEMI y pending → persistir PositionState. Operaciones enseña tesis/stop/T1/T2. | **CERRADO**             |
| **P2** | Riesgo al firmar             | Ticket muestra y bloquea: qty sugerida/máx, pérdida € y R, stop técnico, costes, exposición. Override con motivo + revalidación.    | **CERRADO**             |
| **P3** | Una cadena de salida         | Producto = ExitPlan → ExitPermission → (SEMI / paper). `EvaluatePositionExits` permanece Lab.                                       | **CERRADO**             |
| **P4** | Consola de Mesa              | Posiciones antes que candidatos. Cola Vigilar/Preparado/Propuesto/Bloqueado/Descartado. «No operar» → Journal. Barra estado.        | **CERRADO** (P4.1+P4.2) |

**Fuera de v1.10 (siguen parked):** broker live · OCO / grupo bracket · thaw estricto · ActionabilityScore predictivo · ranking canónico versionado · alertas servidoras · simulación impacto cartera · import bróker · automatización paper por etapas · reconciliación plena (dividendo / desviación vs plan más allá de ledger fees).

Cada slice: plan D1–D8 que cite ADR-033 + tests de invariante + HELP si el concepto es de usuario + stamp CURRENT_SYSTEM.

Confusión de nombres: **ticket F3** = confirm SEMI. **ExitPlan** = objeto v1.9. Los slices de esta fase se llaman **H1/H2/P1–P4**, no «F3».

---

## 2. Freeze de fase

LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · TradePlan ≠ permiso · ExitPlan ≠ auto-exit · SETUP Wyckoff cerrada · 5.x + 8.0–8.2 thin **congelados** · I1–I3 + RX1 intactos · `PAPER_D_EXECUTE` **off** · broker **no** · **no** `contract:gen` hasta shape P1 estable · **no** optimizar con DEMO · **no** inflar tests por conteo · **no** OrderIntent-dios · **no** fusionar Lab `position_policies` con ExitPlan.

Hoy / ActionQueue / C1 honesty **intactos** hasta que P1+ActionIdentity lo justifiquen.

F1–F4 + ExitPermission **no se reabren** para añadir campos del auditor a ciegas. H2 solo invariantes.

---

## 3. Qué hace cada slice (y qué no)

| Slice  | Hace                                               | No hace                                     |
| ------ | -------------------------------------------------- | ------------------------------------------- |
| **H1** | Etiqueta + copy Operaciones/listas + HELP          | `stopPrice`, OCO, trigger real, Alembic     |
| **H2** | Tests + guards en factories TS/Py                  | Wire Confirm, persistencia, UI mesa         |
| **P1** | Tabla/versión Position + snapshot plan + wire fill | Consola nueva, bracket, ranking             |
| **P2** | UI+gate de firma alineados al TradePlan            | Pisar qty a ciegas; % caja como SoT         |
| **P3** | Un puerto de salida de producto                    | Auto-exit CTA; apagar Lab                   |
| **P4** | Superficie de mesa (posiciones primero)            | God page; sexta puerta; sustituir Confirmar |

Cadena de salida de producto (P3):

```text
evento → ExitPlan propone → ExitPermission valida
  → SEMI confirma (o paper según política)
  → fill actualiza Position persistida + ledger
  → Journal plan vs resultado
```

---

## 4. Siguiente rebanada

El siguiente chat **elige**:

1. **Opción A (recomendada):** plan D1–D8 **P4 Consola de Mesa** citando ADR-033 §7. Posiciones primero. **No** god page. **No** sexta puerta. Confirmar sigue siendo la firma.
2. **Opción B:** operar SEMI (firma de riesgo + cadena de salida). No reabrir thin.
3. **Opción C:** owner — tag/release `v1.9-beta` ya existente. No bloquea P4.

**No** Consola + broker en el mismo chat. **No** ExecutionPlan→broker. **No** ActionabilityScore. **No** `stopPrice` / OCO.

Relevo: [`traspaso-relevo-p3-cadena-salida-2026-08-25.md`](./traspaso-relevo-p3-cadena-salida-2026-08-25.md).
