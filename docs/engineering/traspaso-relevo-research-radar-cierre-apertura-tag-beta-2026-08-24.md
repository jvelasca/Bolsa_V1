# RELEVO — Research→Radar copy CERRADA → tag v1.7.0-beta

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1 (Product / Ops).
> **Propósito:** texto de paso para el **NUEVO CHAT** tras unificación copy Research→Radar. **Siguiente = tag `v1.7.0-beta`** (secuencia pactada: DS-03 → higiene → Research→Radar → tag beta).
> **AsOf:** 2026-08-24. Ancla post-higiene **`ea9a985`**. Research→Radar en working tree (sin commit).
> **Protocolo:** máx. 1 writer + 1 verifier RO. Coordinador re-lee file:line. Pre-commit: batería de la fase + update-last.

---

## 1. Qué quedó hecho (Research→Radar copy)

| Entrega          | Detalle                                                                                                                          |
| ---------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| Vocabulario nav  | **Asesor** (`ASESOR_PATH=/research`) vs **Señales** (`SEÑALES_PATH=/screeners`) — sin fusión de páginas                          |
| CTAs alineados   | «Ver en Research» / «Ledger Research →» → **Ver en Asesor** / **Ledger Asesor →**                                                |
| Helpers          | `asesorHistoryHref(trialId?)`, `VER_EN_ASESOR_LABEL`, `LEDGER_ASESOR_LINK_LABEL` en `daily-nav.ts`                               |
| Cross-links hub  | `research-page.tsx` → Señales · `screeners-page.tsx` → Asesor historial                                                          |
| Nav menú         | `app-top-bar.tsx` RESEARCH_MENU usa `ASESOR_PATH`                                                                                |
| Herencia F4′–F6′ | `240c846` ya unificó hub Señales + `screenersHrefAfterTrackerCreate`                                                             |
| Tests            | `daily-nav.test.ts` **8/8** (+ deep-link Asesor)                                                                                 |
| Freeze           | Intacto — Lab fuera spine (D3) · sin OrderProposal · sin Belief · sin `contract:gen` · sin spine changes · `PAPER_D_EXECUTE` off |

**Ficheros tocados (UI/copy):**

- `apps/web/src/features/confirm/daily-nav.ts` + `.test.ts`
- `apps/web/src/features/research/research-page.tsx`
- `apps/web/src/features/research/research-trial-result-block.tsx`
- `apps/web/src/features/backtests/backtest-history-tab.tsx`
- `apps/web/src/features/backtests/backtest-result-view.tsx`
- `apps/web/src/features/screeners/screeners-page.tsx`
- `apps/web/src/components/layout/app-top-bar.tsx`
- `docs/engineering/backlog-trabajo-2026-08-20.md` §0
- `docs/engineering/PROJECT_STATE.md` §2b
- `docs/CURRENT_SYSTEM.md`

---

## 2. Residuales honestos

| Hueco               | Estado               | Notas                                                                                                             |
| ------------------- | -------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Rutas backend       | Sin cambio           | `/research` y `/screeners` permanecen; solo copy UI                                                               |
| Objeto «rastreador» | Terminología interna | Paneles/trackers siguen «rastreador»; toasts Camino B siguen «Radar · …» (contrato B0)                            |
| Help/registry       | Parcial              | `app-help-menu.tsx` ya dice Señales/Asesor; no re-auditado línea a línea en este slice                            |
| Plan draft          | Histórico            | `plan-unificacion-research-radar-2026-08-21.md` sigue como referencia; producto copy cerrado en §2b PROJECT_STATE |
| Fusión hubs         | Fuera de alcance     | Dos páginas separadas por diseño (D3 + plan §1.2)                                                                 |
| DS-03 commit        | Coordinador          | Mandate gate puede seguir en working tree según secuencia previa                                                  |

---

## 3. Freeze (sigue intacto)

OrderProposal · Journal · Attribution · orquestador · Daily Mission · Track B B1–B12 · Belief · `PAPER_D_EXECUTE` **off** · sin broker live · Lab→spine · `contract:gen` salvo fase pactada · **no bypass human confirm** · **no cambio H3 orphan execute** · Decision Spine sin reabrir.

---

## 4. Siguiente · tag v1.7.0-beta

Secuencia pactada por propietario:

```
DS-03  →  higiene dev  →  Research→Radar (este relevo)  →  tag v1.7.0-beta
```

**Abrir chat tag beta** con:

```
CONTEXTO: Research→Radar copy CERRADA (working tree sin commit). Ancla ea9a985 post-higiene.
Asesor/Señales alineados; CTAs Ver en Asesor; cross-links hub. F4′–F6′ heredado 240c846.
Freeze intacto. Siguiente = tag v1.7.0-beta (no más producto Research→Radar salvo hueco real).
Relevo: traspaso-relevo-research-radar-cierre-apertura-tag-beta-2026-08-24.md
```

---

## 5. Commit sugerido (coordinador — web + docs)

```
feat(web): align Research→Radar copy Asesor vs Señales

CTAs and hub cross-links use Asesor (/research) vs Señales (/screeners);
add asesorHistoryHref helper. No route/API fusion. Next = tag v1.7.0-beta.
```

**Batería mínima antes de commit:**

```bash
pnpm --filter @bolsa/web typecheck
pnpm --filter @bolsa/web lint
pnpm --filter @bolsa/web test
```
