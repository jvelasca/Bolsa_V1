# Paquete de auditoría — ESTADO GLOBAL post-ciclo beta v1.7.0-beta (2026-08-24c)

> **Propósito:** documento **único** para auditoría externa general tras el ciclo beta slice **U6 → DS-05 → ops → DS-03 → higiene → Research→Radar → stamp tag v1.7.0-beta**. Consolida identidad, freeze, arcos cerrados desde el pack 2026-08-24b, verificación y riesgos ops.
> **AsOf:** 2026-08-24 · HEAD **`ea9a985`** + stamp tag v1.7.0-beta en working tree · R-13 **CERRADA** · Track B **CERRADO** · Fase 0 spine **COMPLETA** · UX mesa **U0–U6 CERRADA** · **DS-05/DS-03 CERRADAS** · **ops propietario CERRADA** · **Research→Radar copy CERRADA** · **tag `v1.7.0-beta` stamp preparado; tag git pendiente coordinador**.
> **Repo:** `https://github.com/jvelasca/Bolsa_V1`
> **Fuentes vivas:** [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · [`backlog-trabajo-2026-08-20.md`](./backlog-trabajo-2026-08-20.md) §0 · [`traspaso-relevo-audit-stamp-ciclo-u6-ds05-ops-2026-08-24.md`](./traspaso-relevo-audit-stamp-ciclo-u6-ds05-ops-2026-08-24.md) · [`PROJECT_STATE.md`](./PROJECT_STATE.md)
> **Histórico:** [`audit-pack-estado-global-2026-08-24b.md`](./audit-pack-estado-global-2026-08-24b.md) (pre-U6/DS-05/ops; supersedido) · [`audit-pack-estado-global-2026-08-24.md`](./audit-pack-estado-global-2026-08-24.md) · [`audit-pack-estado-global-2026-08-22.md`](./audit-pack-estado-global-2026-08-22.md) · R-1→R-8: [`audit-pack-estado-global-2026-08-20.md`](./audit-pack-estado-global-2026-08-20.md).

---

## 0. Resumen ejecutivo

| Pieza                       | Estado                                                                                                           |
| --------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| **Rama**                    | HEAD **`ea9a985`** · tag **`v1.7.0-beta`** (stamp; **tag git pendiente**) · previo **`v1.6.0-beta` → `c3964fc`** |
| **Identidad**               | QROS + Investment OS + **Decision Spine** · Lab/Radar **fuera** (D3)                                             |
| **R-1..R-13**               | ✅ CERRADOS (money-path + JWT + BETA)                                                                            |
| **Track B split backtests** | ✅ CERRADO (B0–B12)                                                                                              |
| **Fase 0 Decision Spine**   | ✅ COMPLETA (Fit · Decision Board · D1/D2/D3 · Prove · H5 · **DS-05** · **DS-03**)                               |
| **UX mesa U0–U6**           | ✅ CERRADA (`04e441e` U0–U5 · U6 `9e9a346`)                                                                      |
| **Spine residual DS-05**    | ✅ CERRADA (`15e86a4`) — Data Freshness Gate en `check_opening`                                                  |
| **Spine residual DS-03**    | ✅ CERRADA (`41adb8e`) — Account Mandate Gate en `check_opening`                                                 |
| **Ops propietario**         | ✅ CERRADA (`5100d23`) — secret scanning + push protection enabled · runbook `TRUSTED_PROXIES`                   |
| **Higiene dev**             | ✅ CERRADA (`ea9a985`, dato local) — residuos R8C + verify EXIT 0                                                |
| **Research→Radar copy**     | ✅ CERRADA (working tree) — Asesor vs Señales; sin fusión hubs                                                   |
| **Release tag**             | **`v1.7.0-beta`** stamp preparado; **tag git pendiente coordinador**                                             |
| **Ciclo activo**            | **Ninguno — idle / decisión de ciclo**                                                                           |
| **Freeze**                  | Sin OrderProposal · `PAPER_D_EXECUTE` off · sin broker live · Belief frozen · Track B no reabrir                 |

**Mensaje clave:** el núcleo financiero R-7→R-13, el Decision Spine (SEMI=AUTO risk, Fit VETO, confirm contrato, **freshness DS-05**, **mandate DS-03**), la mesa U0–U6, ops ejecutable, copy Research→Radar y el stamp **`v1.7.0-beta`** están listos en HEAD **`ea9a985`** + working tree. **Tag git pendiente coordinador.** **BETA / no producción.** Sin fase de implementación abierta.

---

## 1. Identidad del sistema

- **QROS** (Lab / backtests, ADR-011) y **Investment OS** (mesa SEMI/AUTO) unidos por el **Decision Spine**.
- Lab/Radar **recomiendan**; **no** entran en la columna autoritativa de decisión (**D3**, ADR-019).
- LLM **nunca** ejecuta. Auth viva = **JWT + cookie HttpOnly** (ADR-027); `APP_PASSWORD` = overlay opcional de login en dev.

Camino de ejecución (resumen): `Assessment → DecisionPackage → Policy Gate + check_opening (Fit + DS-05 freshness + DS-03 mandate) → Confirm SEMI | AUTO router → ExecuteTrade (paper)`.

Detalle file:line: [`decision-spine-cadena-2026-08-24.md`](./decision-spine-cadena-2026-08-24.md).

---

## 2. Mapa de releases (tags)

| Tag           | Commit      | Nota                                                                      |
| ------------- | ----------- | ------------------------------------------------------------------------- |
| `v1.2.0`      | `b28e956`   | R-9                                                                       |
| `v1.2.1`      | `2093296`   | R-10                                                                      |
| `v1.3.0`      | `b778292`   | R-11                                                                      |
| `v1.5.0-beta` | `5e52bd6`   | R-12                                                                      |
| `v1.6.0-beta` | `c3964fc`   | R-13                                                                      |
| `v1.7.0-beta` | _pendiente_ | beta slice post-R-13 — **stamp preparado; tag git pendiente coordinador** |

HEAD **`ea9a985`** incluye DS-03 + higiene; Research→Radar copy + stamp tag en working tree (ahead del tag release).

---

## 3. Arcos cerrados desde pack 2026-08-24b (`04e441e` → stamp v1.7.0-beta)

| Arco                | Qué entrega                                                                | Anclas típicas |
| ------------------- | -------------------------------------------------------------------------- | -------------- |
| UX mesa U6          | Preview ticket margen/comisión en Confirm/drawer (UI-only)                 | `9e9a346`      |
| Spine residual      | **DS-05** Data Freshness Gate fail-closed (SEMI ohlcv + AUTO signal ts)    | `15e86a4`      |
| Spine residual      | **DS-03** Account Mandate Gate fail-closed (tenure BD + mismatch AUTO)     | `41adb8e`      |
| Ops propietario     | Secret scanning + push protection enabled · runbook `TRUSTED_PROXIES` prod | `5100d23`      |
| Higiene dev         | Residuos R8C eliminados · verify EXIT 0 (dato local)                       | `ea9a985`      |
| Research→Radar copy | Asesor vs Señales CTAs/cross-links; sin fusión hubs                        | working tree   |
| AUDIT-STAMP         | Living SoT + audit pack alineados                                          | docs-only      |
| Tag beta            | Stamp **`v1.7.0-beta`** (CHANGELOG + update-last + relevo)                 | working tree   |

Arcos previos (pack 24b): Fase 0 spine · Prove · H5 · UX U0–U5 · ops residual símbolos `/`.

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

**Firma:** `git rev-parse HEAD` → **`ea9a985`** (post DS-03 + higiene; fetch para `origin/main`)

```bash
pnpm test:decision-spine   # cadena decisión (confirm, Fit, risk, DS-05, DS-03, AUTO veto, Golden) — 53 tests
pnpm test:semi             # UI/libro DEMO F3 — NO es el spine
```

Docs de lectura rápida: [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md) · relevo ciclo [`traspaso-relevo-audit-stamp-ciclo-u6-ds05-ops-2026-08-24.md`](./traspaso-relevo-audit-stamp-ciclo-u6-ds05-ops-2026-08-24.md) · backlog §0.

Batería money/contrato completa (opcional, pack 2026-08-24 §11): `pnpm contract:check` · web typecheck/lint/test · ruff/mypy/pytest application · `verify_ledger_balance_chain.py`.

**Ops (propietario):** UI GitHub → Settings → Code security and analysis → confirmar Secret scanning + Push protection **Enabled**. Runbook: [`ops-trusted-proxies-prod-runbook-2026-08-24.md`](./ops-trusted-proxies-prod-runbook-2026-08-24.md).

---

## 6. Open risks (ops, propietario)

1. **`TRUSTED_PROXIES` en prod** — IPs/CIDR reales del edge proxy **bloqueado en el propietario** (runbook listo; valor no va en repo).
2. **Secret scanning UI** — habilitado vía API 2026-08-24; **recomendado confirmar en UI** del repo.
3. **Purga historial git dev** (opcional) — decisión explícita pendiente.

---

## 7. Limitaciones conocidas (honestas; no son bugs de esta rebanada)

Copiado de [`CURRENT_SYSTEM.md`](../CURRENT_SYSTEM.md):

- Ranking IO sigue en cliente (`operativa-index.ts`).
- Dos call-sites a `ExecuteTrade` (TO-BE: convergencia **antes** del fill).
- Dictamen (`DailyOpinionService`) no entra solo al Runtime; puede acabar en SEMI por alarma.
- Aperturas orphan sin package: `contract=absent`, **sí ejecutan** (H3).
- Confirm SEMI: perfil vía `active_profile_id` → `check_opening` (H5 CERRADA). Sin perfil → defaults moderate.
- Composite `portfolioConstraints` sigue `not_evaluated`; Fit vive al lado.
- DS-03 Account Mandate Gate **CERRADA** (`41adb8e`); OperatingMandate playbook ticker sigue siendo concepto distinto.
- Sin OrderProposal / Journal / Attribution.

---

## 8. Índice de fuentes

| Tema          | Doc                                                          |
| ------------- | ------------------------------------------------------------ |
| SoT corto     | `docs/CURRENT_SYSTEM.md`                                     |
| Relevo vivo   | `traspaso-relevo-tag-v1-7-0-beta-cierre-ciclo-2026-08-24.md` |
| Cadena spine  | `decision-spine-cadena-2026-08-24.md`                        |
| Backlog §0    | `backlog-trabajo-2026-08-20.md`                              |
| Pack previo   | `audit-pack-estado-global-2026-08-24b.md` (U0–U5 era)        |
| Pack R-13 era | `audit-pack-estado-global-2026-08-22.md`                     |

---

## Ap. A — Quick lookup

| Pieza             | Commit / nota                               |
| ----------------- | ------------------------------------------- |
| HEAD / ancla      | `ea9a985`                                   |
| Tag latest        | `v1.7.0-beta` _pendiente_ (stamp preparado) |
| Tag previo        | `v1.6.0-beta`=`c3964fc`                     |
| DS-03 mandate     | `41adb8e`                                   |
| U6 ticket preview | `9e9a346`                                   |
| DS-05 freshness   | `15e86a4`                                   |
| U0–U5 mesa        | `04e441e`                                   |
| Prove Spine       | `5e81350`                                   |
| H5 código         | `f56af2f`                                   |
| D2 confirm pkg    | `f7b1f6c`                                   |
| D3 Lab fuera      | `ea0c93f`                                   |

## Ap. B — Lectura sugerida (20–30 min)

1. Este doc §0 + §4 + §5 + §6
2. `CURRENT_SYSTEM.md`
3. Relevo AUDIT-STAMP §1–§3
4. (Opcional) pack 2026-08-24b para contexto U0–U5 pre-U6
