# RELEVO — gate iso V2.15.4: causa raíz CONFIRMADA (contaminación entre pasos del job) + GREEN de v2.16-beta — 2026-09-09

> Bitácora de relevo. Causa raíz confirmada y corrección aplicada con evidencia reproducible
> en PG real (Docker). El tag `v2.16-beta` quedó GREEN tras aislar el gate iso en su propia BD.

## Cómo llegar a la evidencia (Docker + PG real, replicación exacta del job `lifecycle-pg`)

Sobre una BD scratch migrada (`bolsa_v1_iso_test`, `alembic upgrade head`, env del job idéntico):

| #   | Paso                                                                                                                                                                       | Resultado                                             |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| 1   | **Solo** gate iso (`test_account_isolation` + workspaces + platform_events + trackers) sobre BD recién migrada **limpia**                                                  | **43 passed**                                         |
| 2   | (drop/recreate BD limpia) **Paso 7 del job**: lifecycle_pg + auth + golden V188/190/191/195/196 + outbox_worker + financial_integrity + health (real-PG) sobre la misma BD | 36 passed (deja **residuo persistente** en la BD)     |
| 3   | **Gate iso (paso 8)** sobre la MISMA BD ya con el residuo del paso 7                                                                                                       | **3 failed / 40 passed** = los 3 exactos del CI run 2 |

Los 3 que fallan (idénticos al run `34322567613` del CI):

```
FAILED test_account_isolation.py::test_accountless_decision_sessions_scoped_to_principal_default_account
       assert 'DS-...' in set()
FAILED test_account_isolation.py::test_accountless_scoped_by_principal_default_not_a_when_b_principal
       assert 'DS-...' in set()
FAILED test_account_isolation.py::test_refresh_observed_accountless_does_not_read_foreign_or_orphan_memory
       assert 200 == 404
```

## Diagnóstico final

**NO es bug funcional de V2.15.4.** Es **contaminación cruzada entre pasos dentro del mismo
job `lifecycle-pg` de `release-tag-ci.yml`**: los pasos 7 (Lifecycle/golden/outbox/financial\_
integrity/health real-PG) y 8 (gate iso) compartían la **misma base `bolsa_v1`**. El paso 7
escribe datos persistentes de otros owners/cuentas/sesiones/recuerdos antes de la iso; 3 tests
de la iso asumen una BD sin datos ajenos → se rompen por el residuo.

- Prueba A (BD limpia): iso **verde** → el código de V2.15.4 aísla correctamente.
- Prueba B (misma BD tras paso 7): iso **roja 3/43** → es orden/aislamiento de la BD del job.

## Corrección aplicada (commit `39b16f4a`)

En el job `lifecycle-pg` se aisló la iso en una **BD dedicada `bolsa_v1_iso`**:

- Paso nuevo "Prepare dedicated iso scratch DB": `DROP DATABASE IF EXISTS bolsa_v1_iso WITH (FORCE)` + `CREATE DATABASE ... OWNER bolsa` + `alembic upgrade head`, con **override de `env:`** (`DATABASE_URL`/`DB_NAME`) solo para ese step.
- El pytest del gate iso ahora corre contra `bolsa_v1_iso` (override `env:` solo en ese step).
- El paso 7 y el resto del job siguen contra `bolsa_v1` sin cambios. Es un cambio de estructura/
  higiene de estado del workflow; **no se tocó código de producción, drivers ni tests**.

## Estado final verificado

- `origin/main` y `origin/tags/v2.16-beta` → **`39b16f4a`**.
- Run `release-tag-ci` **34324471322** sobre `headSha=39b16f4a`: **success** — gate iso "43
  passed" sobre `bolsa_v1_iso`, `lifecycle-pg` ✓ y `certify` (gate agregado) GREEN.
  URL: https://github.com/jvelasca/Bolsa_V1/actions/runs/34324471322

## Deuda NO bloqueante (no tocada en este bloque)

1. **3er medio off-site** del backup 3-2-1: guía MVP en
   `docs/engineering/guia-off-site-3er-medio-2026-09-09.md`; requiere `rclone config` del owner
   - apuntar `DB_BACKUP_MIRROR_DIR` a un mount sincronizado + el job de sync.
2. Retención off-site sin estado propio (la poda `retentionPrune` solo actúa en local).
3. El doc `relevo-elevacion-v2-16-beta-2026-09-09.md` describe además la estampa del bloque
   de elevación NO-GREEN previa; este relevo documenta su resolución.
