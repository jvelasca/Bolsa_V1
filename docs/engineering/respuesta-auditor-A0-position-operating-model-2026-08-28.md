# Respuesta — A0 producto — Position Operating Model

> **Fecha:** 2026-08-28  
> **Lector:** Auditoría externa (producto/arquitectura) sobre el repo actual + marco Operative Flow.  
> **Complementa:** no usa solo la plantilla §7.2; vota implícitamente AUTO/gráfico y fija el salto de calidad.  
> **Padre:** [`estudio-operativa-auto-y-grafico-2026-08-28.md`](./estudio-operativa-auto-y-grafico-2026-08-28.md) · [`analisis-vs-apps-top-operative-flow-2026-08-28.md`](./analisis-vs-apps-top-operative-flow-2026-08-28.md)

---

## Diagnóstico

La infraestructura de continuidad (OI-4/5/6, Confirm, PositionState, ExitPlan, ExitPermission) **ya está construida**. El hueco no es arquitectónico: es convertirla en **operativa de posición** (`¿qué hago ahora?`).

Shell Mercado `LISTAS | GRÁFICO | OPERATIVA` y nav L1: **congelados**. No otra pantalla.

Eje diferencial: contexto + continuidad + simplicidad de acción + **memoria** (por qué entré, qué esperaba, qué cambió).

## Voto Frente A / B (mapeo a plantilla §7.2)

### AUTO

- **Opción:** no ampliar ahora. Destino alineado con A-β **después** de cerrar el contrato operativo de posición (V1.32–V1.33 producto). Arranque implícito tipo A-α/A-δ.
- **A-γ:** implícitamente rechazada (un solo cerebro; PaperBroker no dicta reglas).
- **Top riesgos:** AUTO prematuro; PaperBroker filtrando negocio; backtest ≠ `risk_policy` live.

### Gráfico

- **Opción ahora:** B-α (toasts/fase; chart read-only).
- **Destino:** drag **después** de PositionDecision + risk signature; nunca segunda lógica; nunca mutar `PositionRevision` directo (B-δ no).
- **Shell:** no tocar.

## P0 que pide esta auditoría

1. **PositionDecision único** — no un segundo motor de salida. Evento (T1 tocado) ≠ decisión (REDUCE según perfil).
2. **Golden Path** entrada → protect → T1 → reduce → exit → recon → journal, conservando IDs y niveles.
3. **Snapshot al nacimiento** — ya cubierto en V1.26 (`test_v126_semi_position_birth`); el hueco es el tramo de **gestión**.

## P1

4. Perfil inversor → ExitPolicy (no otro catálogo de perfiles; las plantillas `conservative / moderate / aggressive_swing` ya existen).
5. Next Event + cola de atención.
6. Reconciliación como estado de mesa (OI-6 detecta; OR-4 ya veta aperturas; falta comunicarlo).
7. Backtest con la misma `risk_policy` que paper/SEMI.

## Qué no hacer

No otro ExitPlan, no otro ExecutionPlan, no `position_policies` Lab como autoridad de mesa, no lógica de política en React, no drag ni AUTO en este tramo.
