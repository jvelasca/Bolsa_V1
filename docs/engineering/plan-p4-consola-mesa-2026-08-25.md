# Plan — P4 Consola de Mesa (posiciones primero)

> **Padre:** [`roadmap-v110-operational-authority-2026-08-25.md`](./roadmap-v110-operational-authority-2026-08-25.md) · ADR-033 §7 · gap [`adr-032-ops-authority-gap-2026-08-25.md`](./adr-032-ops-authority-gap-2026-08-25.md) §2.1 · relevo [`traspaso-relevo-p3-cadena-salida-2026-08-25.md`](./traspaso-relevo-p3-cadena-salida-2026-08-25.md).
> **AsOf:** 2026-08-25.
> **Estado:** **P4.1 CERRADO (código).** P4.2+ pendiente.
> **Método:** claridad 10s · **no** god page · **no** sexta puerta · Confirmar sigue siendo la firma. Reutiliza P1–P3 (Position + cadena salida). Cero broker · cero `stopPrice` / OCO · cero auto-exit CTA.

---

## 0. Objetivo

La mesa debe abrir por **posiciones vivas** (plan persistido + advisory ExitPlan), no solo por candidatos de entrada. El operador ve en segundos: qué tengo, qué riesgo, qué propone salir, qué entradas esperan — y **firma** en Confirmar. «No operar» es veredicto de sesión, no ausencia de actividad.

### Qué entra vs qué queda fuera (P4 slice 1)

| Incluye (P4.1 propuesto)                                                                 | Excluye                                    |
| ---------------------------------------------------------------------------------------- | ------------------------------------------ |
| Bloque **Posiciones** enriquecido (Operaciones / Libro): R, stop, T1/T2, Salida advisory | Nueva ruta `/console` god page             |
| CTAs **Revisar / Reducir / Salir** → encolan o abren Confirm (no ejecutan solos)         | Auto-exit · `PAPER_D_EXECUTE` on           |
| Barra/resumen operativo: caja, veto/kill-switch visible, posiciones count                | Sustituir strip Hoy como sexta puerta      |
| Cola entradas **read-only** agrupada por status TradePlan (Vigilar…Descartado)           | ActionabilityScore predictivo              |
| «No operar hoy» → evento Journal                                                         | Broker · OCO · `stopPrice` · Alembic nuevo |
| HELP + tests UI mínimos + stamp                                                          | Fusionar Lab evaluate-exits · thin rewire  |

Slices posteriores (P4.2+): barra estado global completa, proteger con override stop, cola interactiva con filtros.

---

## 1. Decisiones (D1–D8) — borrador

| Id     | Decisión                                                                                                                                                                                          |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **D1** | **No** ruta nueva obligatoria. Superficie = ampliar **Operaciones** (Trading + `/operations`) + strip contextual. Confirmar `/confirm` sigue siendo la **única** firma transaccional.             |
| **D2** | Posiciones: datos de `operational` (P1) + `exitPlan` advisory (P3). Holding qty/P&L = contabilidad (honest). Sin plan → «sin plan persistido».                                                    |
| **D3** | CTAs salida: **encolar** `exit_hint` / `reduce` en cola Confirm (mismo SEMI). **No** ExecuteTrade directo. **No** bypass ExitPermission (P3 gate intacto al firmar).                              |
| **D4** | Cola entradas: proyección read-only desde Decision Board / ActionQueue existente. Labels: WATCH→Vigilar · ARMED→Preparado · TRIGGERED→Propuesto · BLOCKED→Bloqueado · EXPIRED/discard→Descartado. |
| **D5** | Veto global (`check_opening` / kill-switch): bloquea **nuevas entradas** en copy/UI; **no** bloquea CTAs desriesgo (coherente H2/P3).                                                             |
| **D6** | «No operar»: acción explícita (botón/modal) → Journal `session_verdict: no_trade` (sin fill). **No** inventa BUY.                                                                                 |
| **D7** | HELP: Consola = posiciones primero; Hoy sigue proyección; Confirm = firma; cadena P3; NO TRADE excelente.                                                                                         |
| **D8** | Tests E (UI/copy) + Journal no_trade · stamp docs · relevo. **E1:** tag `v1.10-beta` (owner) **o** operar SEMI. **No** broker en este chat.                                                       |

Si P4 añade auto-exit, god page, sustituye Confirm, o cablea Lab exits: **parar y replanificar**.

---

## 2. Ficheros (previstos)

- `operations-panel.tsx` · `operations-page.tsx` — filas enriquecidas + CTAs
- Componente cola entradas read-only (Trading o Operaciones)
- `no-trade-session` use-case + ruta Journal (backend mínimo si no existe)
- HELP · stamp · relevo P4

## 3. Freeze (intactos)

Mismos que P3 + P1/P2. Thin 5.x/8.x congelados. Hoy dedup por símbolo intacta. F1–F4 sin campos extra.
