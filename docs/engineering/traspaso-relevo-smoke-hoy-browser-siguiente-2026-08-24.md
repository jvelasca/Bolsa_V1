# RELEVO — smoke Hoy en navegador (siguiente chat, 2026-08-24)

> **Padre:** [`traspaso-relevo-adr-031-tradeplan-hoy-cierre-apertura-siguiente-2026-08-24.md`](./traspaso-relevo-adr-031-tradeplan-hoy-cierre-apertura-siguiente-2026-08-24.md).
> **AsOf:** 2026-08-24.
> **Chat origen:** este hilo de commit ADR-031 + stamp (browser no inyectado al Agent).

---

## 0. Pegar en el chat Agent NUEVO (bloque único)

```
CONTEXTO (2026-08-24): repo Bolsa_V1.
HEAD local `593cbd1` (stamp docs) sobre `818b0c7` (ADR-031 Ciclos 0–3). origin/main = `020975c`. Ahead 2. SIN PUSH.
Tag v1.7.0-beta → e3b943a. Working tree LIMPIO.

LEE PRIMERO:
- docs/engineering/traspaso-relevo-smoke-hoy-browser-siguiente-2026-08-24.md
- docs/engineering/traspaso-relevo-adr-031-tradeplan-hoy-cierre-apertura-siguiente-2026-08-24.md
- docs/adr/031-operational-model-tesis-plan-permiso.md
- docs/CURRENT_SYSTEM.md
- docs/engineering/backlog-trabajo-2026-08-20.md §0
- docs/PROJECT_PREMISES.md ⭐§0
- docs/engineering/PROJECT_STATE.md (header)

IDENTIDAD: QROS (Lab) + Investment OS (mesa) + Decision Spine.
TradePlan EXTIENDE el spine, no lo sustituye. Ranking ≠ BUY. LAB ≠ TRADING. LLM nunca ejecuta.

HECHO: ADR-031 Ciclos 0–3 commiteados. TTL + precio 2% + H3 orphan fail-closed + pending fill vía check_opening + TradePlan mapper A/B/C/H + strip Hoy (proyección Decision Board, NO mapper live). Spine 63.

TAREA INMEDIATA (una sola): smoke Hoy EN NAVEGADOR.
1) Arranca `pnpm dev` si no hay API :8000 + web :5173.
2) Usa herramientas de browser (cursor-ide-browser o playwright). Si no están, PARA y dilo; no inventes clicks.
3) Abre http://localhost:5173/trading (pide login al usuario si el gate aparece; no inventes password).
4) Verifica tira Hoy (data-testid=hoy-command-strip).
5) Clic en un chip → diálogo Why / Why not.
6) Clic Firmar → drawer Confirmar.
7) Si hay pending en mesa: fill (api.fillPendingOrder). Si no hay, anótalo; no forces fill.
NO abrir Ciclo 4+ (Entry / NO_NEW_LONGS / thesis health / MFE / Shadow AUTO / broker).
NO commit/push salvo que el propietario lo pida.
NO TOCAR: F9-B · purge storage · motor money internals · gobernanza IA · PAPER_D_EXECUTE · Track B B1–B12 · 5ª puerta extra · god-page Command Center.

Protocolo: una fase = subagente acotado + batería + aprobación por commit.
```

---

## 1. Firma

| Campo                       | Valor                                                                                                                                   |
| --------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| HEAD                        | **`593cbd1`** (docs stamp). Código ADR-031 = **`818b0c7`**.                                                                             |
| origin/main                 | **`020975c`**. Local **ahead 2**. **Sin push.**                                                                                         |
| Tag                         | `v1.7.0-beta` → `e3b943a`                                                                                                               |
| Árbol                       | limpio                                                                                                                                  |
| Browser en el chat anterior | Tab visible en Cursor; **Agent sin MCP** (`cursor-ide-browser` no inyectado). Fallback: `C:\Users\josea\.cursor\mcp.json` → playwright. |

---

## 2. Cómo abrir el hilo (humano, 30 s)

1. En Cursor, **este mismo repo** (`Bolsa_V1`).
2. Panel Agent → icono **+** / **New Chat** (no continúes el hilo viejo).
3. Modo **Agent** (no Ask).
4. En la caja del mensaje, icono de herramientas: marca **Browser** (y **playwright** si aparece).
5. `Ctrl+Shift+P` → **Open Browser Tab** (misma ventana que el chat).
6. Pega el bloque de §0. Envíalo.

Si el agente nuevo dice que no tiene `browser_navigate` / `browser_snapshot` / playwright: `Settings` → `Tools & MCP` → Browser Automation ON + playwright Approve → **otro** New Chat.

---

## 3. Tras el smoke (E1, no adelantar)

- OK → informar y preguntar: cablear TradePlan en propose/confirm (plan acotado) **o** push de `818b0c7`+`593cbd1`.
- Fallo UI → un fix mínimo + re-smoke. Sin Ciclo 4+.
