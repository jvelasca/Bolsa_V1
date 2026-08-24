# RELEVO / TRASPASO — cierre tag v1.7.0-beta → idle / decisión de ciclo (2026-08-24)

> **Padre:** `docs/engineering/engineering-index-2026-08-03.md` §1.
> **Propósito:** texto de paso oficial para el **NUEVO AGENTE / NUEVO CHAT** tras el stamp del ciclo beta slice post-`v1.6.0-beta`. Leer este doc + backlog §0 + `PROJECT_STATE.md` + premisas ⭐§0 **antes de tocar nada**.
> **Fuente de coordinación:** GitHub [`jvelasca/Bolsa_V1`](https://github.com/jvelasca/Bolsa_V1) `origin/main`. SHA vivo = `git fetch && git rev-parse origin/main` (no asumir SHA de este fichero).
> **Estado al redactar (verificado):** HEAD **`ea9a985`** · working tree con Research→Radar copy + stamp tag v1.7.0-beta (sin commit) · tag **`v1.7.0-beta`** stamp preparado · **tag git pendiente coordinador** · tag **`v1.6.0-beta` → `c3964fc`** · tag **`v1.5.0-beta` → `5e52bd6`** · tag **`v1.3.0` → `b778292`** intactos · **ciclo beta slice CERRADO** · **no hay ciclo activo predefinido**.
> **AsOf:** 2026-08-24.

---

## 1. Estado verificado (firma — no adivinar)

- **HEAD:** `ea9a985` (post DS-03 `41adb8e` + higiene dev). Working tree incluye Research→Radar copy (web) + stamp tag (docs/CHANGELOG).
- **Ciclo beta slice COMPLETO:** secuencia pactada DS-03 → higiene → Research→Radar → stamp tag v1.7.0-beta. **Tag git NO creado en este paso** — lo crea el coordinador tras commit aprobado.
- **Partida release:** tag **`v1.6.0-beta` → `c3964fc`** (R-13, 2026-08-22).
- **Anclas clave del ciclo (de más nuevo a más antiguo post-`c3964fc`):**

  | Commit / estado | Contenido                                                                                        |
  | --------------- | ------------------------------------------------------------------------------------------------ |
  | working tree    | Research→Radar copy Asesor/Señales + stamp tag v1.7.0-beta (CHANGELOG, update-last, este relevo) |
  | `ea9a985`       | docs higiene dev cierre; relevo Research→Radar                                                   |
  | `41adb8e`       | **DS-03** Account Mandate Gate fail-closed en `check_opening`                                    |
  | `5100d23`       | audit-stamp living SoT; ops secret scanning + runbook TRUSTED_PROXIES                            |
  | `15e86a4`       | **DS-05** Data Freshness Gate en `check_opening`                                                 |
  | `9e9a346`       | **U6** ticket preview margen/comisión en Confirm/drawer                                          |
  | `04e441e`       | **U0–U5** mesa (help, S/R, drawer, Fit chips, proyección chart F3)                               |
  | `f56af2f`       | **H5** perfil SEMI → `check_opening`                                                             |
  | `5e81350`       | Prove Decision Spine S0–S3                                                                       |
  | Fase 0          | Fit · Decision Board · D1/D2/D3 · confirm SEMI deuda                                             |
  | Track B         | F4′–F6′ + B1–B12 split backtests (`240c846`…`3f9bd7e`)                                           |

- **Herencia R-13 (no repetir):** A0–A3 cerradas · tag `v1.6.0-beta` = `c3964fc` · Track B desbloqueado post-R-13 · purge V2 T+0 19/19 (E8 N).

---

## 2. PROTOCOLO OBLIGATORIO del nuevo agente — VIGENTE

> Premisas **E1–E9** en `docs/PROJECT_PREMISES.md` ⭐§0 y §4.

1. **Read-first:** backlog §0/§1 · `PROJECT_STATE.md` · plan de la fase que se abra. Si el repo no coincide → **PARAR**.
2. **Una fase = un subagente acotado + verificación del coordinador + batería + aprobación por commit + push `main`.**
3. **Anti-saturación:** relevo con texto de paso firmado si el hilo se degrada.

### Batería mínima

- **Backend:** `ruff check packages/py apps/api-python` → 0 · mypy gate CI · pytest zona.
- **Frontend/shared:** `pnpm --filter @bolsa/web typecheck|lint|test` · `pnpm --filter @bolsa/shared typecheck|lint|test|build` · `contract:check` si cambia OpenAPI.
- **Spine:** `pnpm test:decision-spine` → **53** (incluye DS-05 + DS-03).
- **Verificadores:** `scripts/verify/verify_ledger_balance_chain.py` (EXIT 0 en dev limpio).

---

## 3. Deudas / decisiones pendientes (NO auto-cerrar)

| Ítem                     | Origen            | Regla / estado                                                                              |
| ------------------------ | ----------------- | ------------------------------------------------------------------------------------------- |
| **Tag git v1.7.0-beta**  | este relevo       | Stamp preparado; **coordinador crea tag** tras commit aprobado: `git tag v1.7.0-beta <sha>` |
| **Purge storage V2**     | R-12/R-13 A1 §4.3 | **MONITOR** 4–8 semanas · T+0 19/19 · E8 **N** (sin purge).                                 |
| **Apply F7b prod**       | R-12 F7b          | Solo ventana mantenimiento + URL explícita. Local `bolsa_v1` ya aplicado (103→0 NULL).      |
| **TRUSTED_PROXIES prod** | ops `5100d23`     | Runbook listo; **valor real bloqueado en propietario** (sin IPs en repo).                   |
| **Gobernanza IA**        | freeze E7         | NO tocar salvo decisión.                                                                    |
| **`contract:gen`**       | freeze            | NO salvo fase pactada.                                                                      |
| **Motor money**          | freeze            | NO tocar (`ExecuteTrade`, custodia apply).                                                  |
| **Track B B1–B12**       | cierre 2026-08-24 | **CERRADO** — no reabrir sin plan nuevo.                                                    |

### Candidatos próximos (aparcado — requieren decisión del propietario)

| Candidato                       | Plan / evidencia                                        |
| ------------------------------- | ------------------------------------------------------- |
| OrderProposal / Journal         | freeze spine — requiere ADR + decisión explícita        |
| R-9 F9 analytics↔market         | `plan-r9` + traspaso R-9 F9                             |
| Auditoría externa estado global | `audit-pack-estado-global-2026-08-24c.md` (actualizado) |
| Modo monitor puro               | Purge V2 + ops checklist, sin commits de código         |
| F-IND-1 causalidad indicadores  | backlog §3 — diferido desde F2 backtest                 |

> **Punto de decisión:** el ciclo beta slice quedó **CERRADO** (stamp `v1.7.0-beta`). La próxima tarea requiere **definir el siguiente ciclo**. No abrir código sin plan/decisión aprobada (E1).

---

## 4. TEXTOS DE PASO PARA EL NUEVO AGENTE (pegar directamente)

### 4.1 Brief de arranque (nuevo chat principal)

> CONTEXTO (2026-08-24, firma verificada): repo `Bolsa_V1`, HEAD **`ea9a985`**, working tree con Research→Radar + stamp tag (sin commit). **Ciclo beta slice CERRADO.** Tag **`v1.7.0-beta`** stamp preparado · **tag git pendiente coordinador** · previo **`v1.6.0-beta` → `c3964fc`** · **`v1.5.0-beta` → `5e52bd6`** · **`v1.3.0` → `b778292`**. **No hay ciclo activo predefinido.**
> **LEE PRIMERO:** este doc (§1–§5) · `docs/engineering/backlog-trabajo-2026-08-20.md` §0 · `docs/PROJECT_PREMISES.md` ⭐§0 · `docs/engineering/PROJECT_STATE.md` · `docs/CURRENT_SYSTEM.md`.
> **Tarea inmediata (decisión, NO fase abierta):** confirmar con el propietario **qué ciclo se abre** (OrderProposal · auditoría · monitor purge/ops · F9/V2 · otro). NO abrir código sin plan/decisión (E1).
> **NO tocar:** purge storage alto · gobernanza IA · motor money · apply F7b prod · `contract:gen` salvo fase · Track B B1–B12 reabrir.

### 4.2 Brief subagentes (patrón)

> Una fase = subagente acotado: read-first backlog §0 + premisas E1–E9 + archivos exactos + qué NO tocar + mapa consumidores + batería esperada + **NO commits ni push** + reporte file:line. Coordinador re-verifica antes de proponer commit.

### 4.3 Coordinador — crear tag (post-commit)

> Tras commit aprobado del stamp + Research→Radar (si aún pendiente):
>
> ```bash
> git tag v1.7.0-beta <sha-del-commit-de-cierre>
> git push origin v1.7.0-beta
> ```
>
> Anotar SHA en backlog §0 y audit-pack 24c (sustituir `_pendiente_`).

---

## 5. Enlaces (fuentes de verdad)

- Backlog: `docs/engineering/backlog-trabajo-2026-08-20.md` (§0 · §6)
- CHANGELOG: `CHANGELOG.md` § `[1.7.0-beta]`
- Premisas: `docs/PROJECT_PREMISES.md` ⭐§0
- Estado vivo: `docs/CURRENT_SYSTEM.md` · `docs/engineering/PROJECT_STATE.md`
- Audit pack: `docs/engineering/audit-pack-estado-global-2026-08-24c.md`
- Índice: `docs/engineering/engineering-index-2026-08-03.md` §5
- Relevo Research→Radar (histórico): `traspaso-relevo-research-radar-cierre-apertura-tag-beta-2026-08-24.md`
- Relevo R-13 (histórico): `traspaso-relevo-cierre-r13-consolidacion-beta-siguiente-2026-08-22.md`
- Pending-delete alto: `docs/engineering/pending-delete/README.md`
- Ops: `docs/engineering/ops-r1-seguridad-operaciones-2026-08-19.md`

---

## 6. Cierres del ciclo beta v1.7.0-beta registrados

| Fecha      | Hito                                  | Commits / nota                       |
| ---------- | ------------------------------------- | ------------------------------------ |
| 2026-08-23 | Track B F4′–F6′ + B1–B12 split        | `240c846`…`3f9bd7e`                  |
| 2026-08-24 | Fase 0 spine (Fit · Board · D1/D2/D3) | `3670a09`…`ea0c93f`                  |
| 2026-08-24 | Prove Spine + H5 + confirm SEMI deuda | `5e81350` · `f56af2f` · `2281903`    |
| 2026-08-24 | UX mesa U0–U6                         | `6f26f9d`…`9e9a346`                  |
| 2026-08-24 | Ops residual símbolos `/`             | `3c53f4e`…`7363ec6`                  |
| 2026-08-24 | DS-05 freshness + ops propietario     | `15e86a4` · `5100d23`                |
| 2026-08-24 | DS-03 mandate gate                    | `41adb8e`                            |
| 2026-08-24 | Higiene dev                           | `ea9a985` (dato local)               |
| 2026-08-24 | Research→Radar copy                   | working tree                         |
| 2026-08-24 | **Stamp tag v1.7.0-beta**             | working tree — **tag git pendiente** |

> Producto sigue **BETA / no producción.** Freeze intacto. **Siguiente = idle / decisión de ciclo.**
