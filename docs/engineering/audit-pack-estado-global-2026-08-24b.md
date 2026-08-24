# Paquete de auditoría — ESTADO GLOBAL post-spine + mesa U0–U5 (2026-08-24b)

> **Superseded by** [`audit-pack-estado-global-2026-08-24c.md`](./audit-pack-estado-global-2026-08-24c.md) **for post-ciclo U6+DS-05+ops** (`origin/main` = `5100d23`). Conservar este archivo como histórico post-spine/mesa U0–U5.
> **Propósito:** documento **único** para auditoría externa general tras Decision Spine + UX mesa U0–U5. Consolida identidad, freeze, arcos cerrados desde el pack 2026-08-24, verificación y riesgos ops.
> **AsOf:** 2026-08-24 · `origin/main` = **`04e441e`** · árbol limpio (asumido tras fetch) · R-13 **CERRADA** · Track B **CERRADO** · Fase 0 spine **COMPLETA** · UX mesa **U0–U5 CERRADA**.
> **Repo:** `https://github.com/jvelasca/Bolsa_V1`
> **Fuentes vivas:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [`backlog-trabajo-2026-08-20.md`](./backlog-trabajo-2026-08-20.md) §0 · [`traspaso-relevo-ux-mesa-u5-cierre-apertura-ciclo-2026-08-24.md`](./traspaso-relevo-ux-mesa-u5-cierre-apertura-ciclo-2026-08-24.md) · [`PROJECT_STATE.md`](./PROJECT_STATE.md)
> **Histórico:** [`audit-pack-estado-global-2026-08-24.md`](./audit-pack-estado-global-2026-08-24.md) (pre-spine/mesa; supersedido) · [`audit-pack-estado-global-2026-08-22.md`](./audit-pack-estado-global-2026-08-22.md) · R-1→R-8: [`audit-pack-estado-global-2026-08-20.md`](./audit-pack-estado-global-2026-08-20.md).

---

## 0. Resumen ejecutivo

| Pieza                       | Estado                                                                                           |
| --------------------------- | ------------------------------------------------------------------------------------------------ |
| **Rama**                    | `main` = `04e441e` · tag **`v1.6.0-beta` → `c3964fc`** (latest)                                  |
| **Identidad**               | QROS + Investment OS + **Decision Spine** · Lab/Radar **fuera** (D3)                             |
| **R-1..R-13**               | ✅ CERRADOS (money-path + JWT + BETA)                                                            |
| **Track B split backtests** | ✅ CERRADO (B0–B12)                                                                              |
| **Fase 0 Decision Spine**   | ✅ COMPLETA (Fit · Decision Board · D1/D2/D3 · Prove · H5)                                       |
| **UX mesa U0–U5**           | ✅ CERRADA en `04e441e`                                                                          |
| **Ciclo activo**            | Ninguno — **decisión de ciclo** (auditoría lista)                                                |
| **Freeze**                  | Sin OrderProposal · `PAPER_D_EXECUTE` off · sin broker live · Belief frozen · Track B no reabrir |

**Mensaje clave:** el núcleo financiero R-7→R-13 y el Decision Spine (SEMI=AUTO risk, Fit VETO, confirm contrato) están en `origin/main`. La mesa U0–U5 (help, S/R, Confirm drawer, Fit chips, proyección chart F3) está cerrada. **BETA / no producción.** Sin fase de implementación abierta.

---

## 1. Identidad del sistema

- **QROS** (Lab / backtests, ADR-011) y **Investment OS** (mesa SEMI/AUTO) unidos por el **Decision Spine**.
- Lab/Radar **recomiendan**; **no** entran en la columna autoritativa de decisión (**D3**, ADR-019).
- LLM **nunca** ejecuta. Auth viva = **JWT + cookie HttpOnly** (ADR-027); `APP_PASSWORD` = overlay opcional de login en dev.

Camino de ejecución (resumen): `Assessment → DecisionPackage → Policy Gate + check_opening (Fit) → Confirm SEMI | AUTO router → ExecuteTrade (paper)`.

Detalle file:line: [`decision-spine-cadena-2026-08-24.md`](./decision-spine-cadena-2026-08-24.md).

---

## 2. Mapa de releases (tags)

| Tag           | Commit    | Nota              |
| ------------- | --------- | ----------------- |
| `v1.2.0`      | `b28e956` | R-9               |
| `v1.2.1`      | `2093296` | R-10              |
| `v1.3.0`      | `b778292` | R-11              |
| `v1.5.0-beta` | `5e52bd6` | R-12              |
| `v1.6.0-beta` | `c3964fc` | R-13 — **latest** |

No hay tag nuevo post-spine/mesa; HEAD `04e441e` está **ahead** del tag release.

---

## 3. Arcos cerrados desde pack 2026-08-24 (`47a3b58` → `04e441e`)

| Arco                      | Qué entrega                                                               | Anclas típicas                                                                            |
| ------------------------- | ------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Fase 0 spine docs+código  | AS-IS/TO-BE/Mapping/Descarga · PortfolioFit · Decision Board (RO) · D1–D3 | Fit `3670a09` · Board `8df8a65`/`672e88f` · D2 `f7b1f6c` · Esc.3 `7530556` · D3 `ea0c93f` |
| Prove Spine               | CURRENT_SYSTEM · `pnpm test:decision-spine` · Golden · H1/H2              | `5e81350`                                                                                 |
| H5                        | SEMI `active_profile_id` → `check_opening` (mismo SoT AUTO)               | código `f56af2f` · stamp `76679d2`                                                        |
| UX mesa U0–U5             | Help · S/R · Confirm drawer · Fit chips · proyección orden chart F3       | U0 `c1c4bbd` · U5+stamp `04e441e`                                                         |
| Ops residual (ejecutable) | Fix símbolos `/` · re-sync FTSE · backup corrupt drop                     | ver backlog RELEVO ops                                                                    |

R-1→R-13 + Track B: ver pack histórico 2026-08-24.

---

## 4. Freeze vigente

| Ítem                                                | Estado                          |
| --------------------------------------------------- | ------------------------------- |
| OrderProposal / Journal / Attribution / orquestador | **No**                          |
| `PAPER_D_EXECUTE`                                   | **off**                         |
| Broker live                                         | **No**                          |
| Track B B1–B12                                      | **Cerrado** — no reabrir        |
| Belief / gobernanza IA                              | **Freeze**                      |
| `contract:gen`                                      | Solo fase pactada               |
| Features nuevas                                     | Solo tras **decisión de ciclo** |

---

## 5. Cómo verificar

**Firma:** `git fetch && git rev-parse origin/main` → **`04e441e`**

```bash
pnpm test:decision-spine   # cadena decisión (confirm, Fit, risk, AUTO veto, Golden)
pnpm test:semi             # UI/libro DEMO F3 — NO es el spine
```

Docs de lectura rápida: [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · relevo ciclo [`traspaso-relevo-ux-mesa-u5-cierre-apertura-ciclo-2026-08-24.md`](./traspaso-relevo-ux-mesa-u5-cierre-apertura-ciclo-2026-08-24.md) · backlog §0.

Batería money/contrato completa (opcional, pack 2026-08-24 §11): `pnpm contract:check` · web typecheck/lint/test · ruff/mypy/pytest application · `verify_ledger_balance_chain.py`.

---

## 6. Open risks (ops, propietario)

1. **GitHub secret scanning + push protection** — activar en UI del repo (no código).
2. **`TRUSTED_PROXIES` en prod** — IPs/CIDR reales del edge proxy.

---

## 7. Limitaciones conocidas (honestas; no son bugs de esta rebanada)

Copiado de [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md):

- Ranking IO sigue en cliente (`operativa-index.ts`).
- Dos call-sites a `ExecuteTrade` (TO-BE: convergencia **antes** del fill).
- Dictamen (`DailyOpinionService`) no entra solo al Runtime; puede acabar en SEMI por alarma.
- Aperturas orphan sin package: `contract=absent`, **sí ejecutan** (H3).
- Confirm SEMI: perfil vía `active_profile_id` → `check_opening` (H5 CERRADA). Sin perfil → defaults moderate.
- Composite `portfolioConstraints` sigue `not_evaluated`; Fit vive al lado.
- Sin Data Freshness Gate explícito · sin OrderProposal / Journal / Attribution.

---

## 8. Índice de fuentes

| Tema          | Doc                                                              |
| ------------- | ---------------------------------------------------------------- |
| SoT corto     | `docs/CURRENT_SYSTEM.md`                                         |
| Relevo vivo   | `traspaso-relevo-ux-mesa-u5-cierre-apertura-ciclo-2026-08-24.md` |
| Cadena spine  | `decision-spine-cadena-2026-08-24.md`                            |
| Backlog §0    | `backlog-trabajo-2026-08-20.md`                                  |
| Pack previo   | `audit-pack-estado-global-2026-08-24.md` (R-1→R-13 + Track B)    |
| Pack R-13 era | `audit-pack-estado-global-2026-08-22.md`                         |

---

## Ap. A — Quick lookup

| Pieza           | Commit / nota           |
| --------------- | ----------------------- |
| HEAD / ancla    | `04e441e`               |
| Tag latest      | `v1.6.0-beta`=`c3964fc` |
| Prove Spine     | `5e81350`               |
| H5 código       | `f56af2f`               |
| U5 + stamp mesa | `04e441e`               |
| D2 confirm pkg  | `f7b1f6c`               |
| D3 Lab fuera    | `ea0c93f`               |

## Ap. B — Lectura sugerida (20–30 min)

1. Este doc §0 + §4 + §5 + §7
2. `CURRENT_SYSTEM.md`
3. Relevo ciclo U5 §1–§3
4. (Opcional) pack 2026-08-24 §3–§6 para R-9→R-13 + Track B
