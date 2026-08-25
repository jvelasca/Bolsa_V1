# RELEVO — Cierre post E1 (push · deuda estricto · TRUSTED_PROXIES) · 2026-08-25

> **Padre:** [`traspaso-relevo-thaw-beta-d-2026-08-25.md`](./traspaso-relevo-thaw-beta-d-2026-08-25.md).  
> **AsOf:** 2026-08-25.  
> **HEAD:** tip local post E1.2/E1.3 (ver `git log -1`); origin recibió thaw pack en `9afe80b` + push de deuda/proxies si tip ≠ origin.  
> **Estado:** **FASE CERRADA para chat.** Cambiar de chat recomendado.  
> **Arranque chat nuevo:** este fichero + `CURRENT_SYSTEM.md` + ADR-023 + runbook deuda estricto.

---

## 0. Por qué cambiar de chat

Este hilo acumuló: cierre integridad I1–I3 → E1 completo (RX1 · 8.0–8.2 · thaw audit) → thaw palabra → medición FAIL → **adapta** BETA-D Accepted → 3 agentes (push · deuda · proxies). Contexto saturado; el siguiente trabajo es **operar** o una fase nueva con SoT fresco.

## 1. Qué quedó hecho

| Pieza                   | SHA / estado                                                 |
| ----------------------- | ------------------------------------------------------------ |
| I1–I3 + stamps          | en origin (pre-pack)                                         |
| RX1 exits honesty       | `9289b53`                                                    |
| Growth thin 8.0–8.2     | `cf880eb` · `655832c` · `73044a7`                            |
| Thaw BETA-D             | `cb58962` · ADR-023 **Accepted BETA-D** · UI AUTO on         |
| Push pack thaw          | `9afe80b` = origin tip post-push agente 1                    |
| Deuda estricto tracking | `7bbce74` — runbook + `scripts/thaw_estricto_snapshot.mjs`   |
| TRUSTED_PROXIES docs    | `c3c34ef` — exact-string · DONE/OWNER · **IPs siguen owner** |

## 2. Freeze / flags

- `PAPER_D_EXECUTE` **default off** (opt-in local DEMO). Health puede seguir `off` si no hay env en el proceso API.
- Broker live **no**. Thaw **estricto** (60/50/70/55) **FAIL** — W2–W4 vigentes.
- LAB ≠ TRADING · LLM no ejecuta · Ranking ≠ BUY · I1/I3/RX1 gates intactos.

## 3. E1 — fork (chat nuevo)

1. Weekly: `node scripts/thaw_estricto_snapshot.mjs` → tabla runbook deuda.
2. Owner: `TRUSTED_PROXIES=<peer-ip exacto>` solo cuando exista proxy prod.
3. Opt-in execute DEMO: `PAPER_D_EXECUTE=1` + armado UI (si se opera AUTO).
4. **No** broker · **no** Accept estricto hasta P1–P5 verdes · **no** reabrir Wyckoff/5.x por defecto.
5. Push residual (si tip local ahead tras deuda/proxies).

## 4. Docs clave

- [`deuda-thaw-estricto-runbook-2026-08-25.md`](./deuda-thaw-estricto-runbook-2026-08-25.md)
- [`ops-trusted-proxies-prod-runbook-2026-08-24.md`](./ops-trusted-proxies-prod-runbook-2026-08-24.md)
- [`thaw-beta-adapted-remeasure-2026-08-25.md`](./thaw-beta-adapted-remeasure-2026-08-25.md)
- ADR-023 · `CURRENT_SYSTEM.md`
