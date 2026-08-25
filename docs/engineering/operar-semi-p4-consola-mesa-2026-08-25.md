# Operar SEMI — Consola de Mesa (P4.1 + P4.2) · 2026-08-25

> **Padre:** [`traspaso-relevo-p4-consola-mesa-2026-08-25.md`](./traspaso-relevo-p4-consola-mesa-2026-08-25.md) · [`plan-p4-consola-mesa-2026-08-25.md`](./plan-p4-consola-mesa-2026-08-25.md) · ADR-033 §7.
> **AsOf:** 2026-08-25.
> **Estado:** **LISTO PARA OPERAR SEMI** (documentación + verificación en código; sin cambios de producto).
> **Arranque:** este fichero + `CURRENT_SYSTEM.md` + HELP «Hoy en la mesa».

---

## 0. Verificación en código (prerrequisitos SEMI)

| Prerrequisito                                                               | Verificado  | Evidencia                                                                                                                                          |
| --------------------------------------------------------------------------- | ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Libro DEMO en modo **SEMI** (default `semi`; MANUAL bloquea encolar)        | **Sí**      | `demo-book-prefs.ts`: `defaultDemoBookPrefs().mode === "semi"`; `demoBookAllowsEnqueueConfirm("semi")`; `buildPositionExitPayload` lanza si MANUAL |
| CTAs **Revisar / Reducir / Salir / Proteger** encolan Confirm (no ejecutan) | **Sí**      | `operations-panel.tsx`: `enqueue` + `openConfirmDrawer()`; copy «no ejecutan solos» en `operations-page.tsx`                                       |
| Drawer Confirm (misma firma que `/confirm`)                                 | **Sí**      | `confirm-drawer.ts` + `supervised-f3-panel.tsx` montado en drawer host                                                                             |
| Cadena desriesgo **ExitPlan → ExitPermission → Confirm execute**            | **Sí**      | `confirm_recommendation.py` + `semi_exit_permission`; motivo `exit_permission` en P3                                                               |
| Kill switch **asimétrico** (bloquea entradas/AUTO; desriesgo SEMI OK)       | **Sí**      | `exit-permission.ts` H2; barra `mesa-operational-bar.tsx`; cola entradas copy en `mesa-entry-queue-panel.tsx`                                      |
| Cola entradas **read-only** + filtros P4.2                                  | **Sí**      | `mesa-entry-queue-panel.tsx`: «Solo lectura», filtros status/gate/símbolo                                                                          |
| «No operar hoy» → `POST session-verdict` → Journal                          | **Sí**      | `no-trade-session-button.tsx` → `api.recordSessionVerdict`                                                                                         |
| `PAPER_D_EXECUTE` **off** (AUTO execute bloqueado)                          | **Sí**      | `demo-book-prefs.ts` · `paper-d.ts` · kill-switch API expone lectura env                                                                           |
| **Proteger** preview + override stop en Confirm                             | **Sí (UI)** | `f3-protect-stop-block.tsx` · ticket `action: "wait"` — ver §5 limitación                                                                          |

**Spine y UI P4 (2026-08-25):**

| Batería                        | Resultado      |
| ------------------------------ | -------------- |
| `pnpm test:decision-spine`     | **260 passed** |
| Vitest P4 (7 ficheros, ver §8) | **21 passed**  |

---

## 1. Precondiciones (antes de abrir la mesa)

1. **Cuenta activa** DEMO con posiciones o candidatos en Decision Board.
2. **Modo libro = SEMI** — Trading → Operativa → Configuración (`DemoBookModePanel`). Default al instalar: `semi`. Si está en **MANUAL**, los CTAs de Operaciones fallan con _«cambia a SEMI…»_.
3. **`PAPER_D_EXECUTE` off** — no definir la variable en el entorno API (default off). AUTO armado ≠ permiso de execute.
4. **Arranque local:**

   ```text
   pnpm doctor          # opcional: puertos / DB
   pnpm dev             # web + api-python
   ```

5. Ruta principal: **`/operations`** (Libro · Operaciones). La misma barra operativa aparece embebida en **Trading** (`trading-layout.tsx`).

---

## 2. Flujo diario (Consola de Mesa)

Orden recomendado — **posiciones primero**:

1. **Abrir Operaciones** (`/operations`).
2. **Leer la barra operativa** (`MesaOperationalBar`): régimen, caja, patrimonio, P&L, nº posiciones, cola Confirm, excepciones, kill switch, veto entradas.
3. **Posiciones** (panel izquierdo): por fila — R, stop, T1/T2, advisory Salida, P&L holding. Sin `operational.tradePlanId` → CTAs deshabilitados (_sin plan persistido_).
4. **Cola de entradas** (panel derecho): solo lectura; filtrar por Vigilar…Descartado / gate / símbolo. No hay botón BUY aquí — las entradas siguen el camino Trading → Proponer F3.
5. **Firmar en Confirm** — drawer (CTA desde Operaciones/Trading) o página `/confirm`. Única firma transaccional.

Entradas nuevas (camino clásico SEMI, complementario a P4):

- Trading → tira **Hoy** → Proponer F3 → Confirmar.

---

## 3. Desriesgo — Revisar / Reducir / Salir

| CTA         | Acción encolada             | Execute en SEMI                             |
| ----------- | --------------------------- | ------------------------------------------- |
| **Revisar** | `wait` (nota revisión)      | No — solo encola aviso                      |
| **Reducir** | `reduce` (~50 % qty, min 1) | **Sí** — tras firmar + ExitPermission ALLOW |
| **Salir**   | `exit_hint` (qty total)     | **Sí** — cadena P3 intacta                  |

**Pasos operador:**

1. Clic CTA en fila de posición → ticket en cola Confirm + abre drawer.
2. Revisar preview (precio ref., qty, advisory Salida).
3. **Confirmar + ejecutar** (modo SEMI).
4. Si **DENY** → leer `exit_permission` / `risk_veto` / `risk_signature` — no forzar.

**Requisitos:** posición con plan persistido (fill P1). Side de cierre derivado del package de la sesión original (deuda confirm SEMI cerrada).

---

## 4. Proteger (P4.2)

Cuando ExitPlan sugiere `protect` o `protectPlan.status === protect_hint`:

1. CTA **Proteger** visible en la fila.
2. Encola ticket con meta `operativaIntent: "protect"`, stop sugerido y flag `stopOverrideRequired` si el stop **empeora** el actual (H2).
3. En Confirm: bloque **Proteger · stop sugerido** (`F3ProtectStopBlock`) — stop actual vs propuesto, dirección, textarea override si aplica.

**Limitación conocida (no bloqueante para SEMI salida/reducción):**

- El ticket usa `action: "wait"`. El botón **Confirmar + ejecutar** queda deshabilitado (`supervised-f3-panel.tsx`). **No persiste stop en backend** — enqueue + preview es **UI-only** (plan P4.2; persist protect fuera de scope P3/P4.1).
- Operación real de desriesgo hoy: **Reducir** o **Salir**.

---

## 5. «No operar hoy»

1. Botón **No operar hoy** (cabecera Operaciones).
2. Modal → nota opcional → **Registrar veredicto**.
3. `POST /api/accounts/{id}/session-verdict` con `verdict: "no_trade"`.
4. Aparece en Decision Journal. **No ejecuta órdenes ni inventa BUY.**

0 operaciones puede ser un día excelente.

---

## 6. Kill switch y veto de entradas

| Señal                              | Efecto en entradas                              | Efecto en desriesgo SEMI                                    |
| ---------------------------------- | ----------------------------------------------- | ----------------------------------------------------------- |
| **Kill switch ON**                 | Bloqueadas (copy + gates apertura)              | **Permitido** — CTAs Reducir/Salir/Proteger siguen visibles |
| **Veto entradas** (Decision Board) | Cola entradas muestra aviso; no abre posiciones | Desriesgo no bloqueado por copy P4                          |
| **AUTO + kill switch**             | DENY (`exit-permission` tests)                  | N/A — no operar AUTO                                        |

Barra: badge **Kill switch ON** / **Veto entradas (N)**. Tooltip kill: _«bloquea aperturas y AUTO; desriesgo SEMI permitido»_.

Toggle kill: Cuentas → Config (o API `POST /api/risk/kill-switch`).

---

## 7. Qué NO hacer

| Prohibido                                                    | Por qué                                        |
| ------------------------------------------------------------ | ---------------------------------------------- |
| **AUTO execute** / armar sin checklist thaw                  | `PAPER_D_EXECUTE` off-by-default; BETA-D       |
| **Broker / OCO / stopPrice**                                 | Fuera roadmap P4; no cableado                  |
| **God page `/console`**                                      | No existe; usar `/operations`                  |
| **Thin «Salida» / Lab evaluate-exits** como puerto de cierre | ≠ ExitPlan canónico (P3)                       |
| **CTAs esperando auto-exit**                                 | CTAs solo encolan; Confirm = única firma       |
| **Forzar execute con veto**                                  | Fail-closed spine (DS-03, DS-05, Escalón 3/D1) |
| **Operar en MANUAL**                                         | No encola Confirm para desriesgo mesa          |

---

## 8. Smoke verification (comandos)

```bash
# Spine completo (backend + analytics cognitive)
pnpm test:decision-spine
# → 260 passed (2026-08-25)

# UI/copy P4 Consola de Mesa
pnpm --filter @bolsa/web exec vitest run \
  src/features/operations/mesa-operational-bar.test.tsx \
  src/features/operations/mesa-entry-queue-panel.test.tsx \
  src/features/operations/propose-position-exit.test.ts \
  src/features/confirm/confirm-drawer.test.ts \
  src/features/help/hoy-en-la-mesa.test.tsx \
  src/features/help/mesa-tip-button.test.tsx \
  src/features/trading/f3-protect-stop-block.test.tsx
# → 21 passed · 7 files (2026-08-25)
```

Ficheros clave si falla algo:

- `apps/web/src/features/operations/*`
- `apps/web/src/features/trading/operations-panel.tsx`
- `packages/shared/src/cognitive/exit-permission.ts`
- `packages/py/application/tests/test_confirm_exit_chain.py`
- `packages/py/application/tests/test_record_session_verdict.py`

---

## 9. Blockers / deuda conocida para operación SEMI

| Ítem                                    | Severidad   | Notas                                                       |
| --------------------------------------- | ----------- | ----------------------------------------------------------- |
| **Proteger no ejecuta** (ticket `wait`) | Baja        | Preview/override OK; usar Reducir/Salir para desriesgo real |
| Posición **sin plan persistido**        | Media       | CTAs ocultos; necesita fill previo con TradePlan (P1)       |
| **Revisar** no es execute               | Info        | Encola nota; no cierra posición                             |
| Venta directa diálogo orden             | Info        | P1 deuda: no actualiza Position (fuera P4)                  |
| Protect/BE persist backend              | Fuera scope | Plan P4+ / post v1.10                                       |

**Conclusión:** SEMI operable para **entradas (F3 + Confirm)**, **salida/reducción (CTAs P4 + cadena P3)**, **veredicto no_trade** y **lectura mesa**. Proteger es advisory/enqueue hasta persist stop.

---

## 10. Docs relacionados

- [`traspaso-relevo-p4-consola-mesa-2026-08-25.md`](./traspaso-relevo-p4-consola-mesa-2026-08-25.md)
- [`traspaso-relevo-p3-cadena-salida-2026-08-25.md`](./traspaso-relevo-p3-cadena-salida-2026-08-25.md)
- [`traspaso-relevo-operar-semi-post-exit-permission-2026-08-25.md`](./traspaso-relevo-operar-semi-post-exit-permission-2026-08-25.md)
- [`semi-demo-book-impl-slice1-2026-08-03.md`](./semi-demo-book-impl-slice1-2026-08-03.md)
