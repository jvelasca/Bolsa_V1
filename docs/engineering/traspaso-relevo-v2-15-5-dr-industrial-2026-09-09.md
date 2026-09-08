# RELEVO — V2.15.5 (DR industrial: snapshot atómico, digest por bloques, OHLCV, C2-01, backup 3-2-1 + RPO/RTO) — 2026-09-09

> **Padre:** revisor de auditoría de certificación **V2.15.3** (tag `5ef9016b`) → plan `auditoría_certificación_v2.15.3_c87386b2.plan.md`, secuencia **V2.15.4 → V2.15.5 → V2.16** (definición V2.15.5 reproducida en el prompt del agente; el fichero `.plan.md` no está en este checkout — decisión owner: usar la definición del prompt).
> **Este fichero**: relevo de bloque de **implementación** (working-tree en `main`, sobre `16d84031` = V2.15.4). **NO es una elevación** — no hay bump de `package.json` ni tag (la elevación/tag es faena aparte con run real de Release-tag CI). Núcleo financiero **congelado intacto**.
> **Alcance V2.15.5 (SOLO infraestructura DR):** `scripts/db-dr-verify.mjs`, `scripts/db-restore.mjs`, `scripts/db-dump.mjs`, `scripts/db-backup-list.mjs`, `scripts/db-backup-cron-win.mjs`, `scripts/lib/backup.mjs`. `.github/workflows/release-tag-ci.yml` evaluado (ver §5: sin cambio necesario).

## 1. Lo que cierra (definición V2.15.5 → entregado)

| Requisito V2.15.5                                                    | Estado                                 |
| -------------------------------------------------------------------- | -------------------------------------- |
| Snapshot **atómico `REPEATABLE READ`** del fingerprint               | RESUELTO (ver §2 + hallazgo de parser) |
| **Digest incremental / por bloques** (no `string_agg` total)         | RESUELTO (ver §3)                      |
| Fingerprint/md5 de **mercado OHLCV** (fuente de verdad)              | RESUELTO (ver §3.1)                    |
| Cierre **C2-01** (`--target-db` validado ANTES del DDL destructivo)  | RESUELTO (ver §4)                      |
| **Backup 3-2-1** + métricas **RPO/RTO** + restore-test **periódico** | RESUELTO (ver §5)                      |

## 2. Snapshot atómico `REPEATABLE READ` + hallazgo real de parser

**Hallazgo (verificado 1ª mano, no inferido):** la db-dr-verify previa leía cada tabla con un psql/transacción INDEPENDIENTE por tabla (imagen potencialmente inconsistente entre tablas) y, además, el parser de la línea de digest esperaba separador `\t` cuando `psql -A -t` emite `|`, de modo que para TODA tabla no vacía devolvía `count=0, digest=""` → el chequeo de integridad de contenido **pasaba en vacío**. Es exactamente el tipo de cobertura-no-real que V2.15.5 busca cerrar.

- **`atomicCoverageSnapshot(db, entries)`**: todas las tablas (financieras + mercado) se leen en **UNA transacción `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; … COMMIT;`** enviada por stdin a un único psql. REPEATABLE READ congela la snapshot al abrir → count y digest de todas las tablas del mismo run ven el **mismo estado commitado** (imagen consistente; ya no hay mezcla de instantes).
- **Parser arreglado**: cada SELECT devuelve `SENTINEL|count|digest`; la línea se parte por `|`. Verificado contra BD real: la snapshot ahora reporta `accounts=13 ledger=22 … instruments=134 ohlcv_bars=167136 data_sync_log=262` (antes 0/vacío).
- **md5** se mantiene (built-in core PG16, sin `pgcrypto` en restore a scratch). Guard NO-adversarial; la falsificación la cubre el sidecar SHA-256 del dump en Node.

## 3. Digest por bloques (determinista, memoria acotada)

Sustituye `md5(string_agg(fila::text,…))` (agregaba TODO el contenido en un solo agregado) por:

```
orden estable por rowtxt → bloques fijos CHUNK_SIZE (5000) filas
  → por bloque md5(string_agg(bloque ordenado))
  → digest total = md5(concat(block_digests en orden))   +   count(*) por tabla
```

- Memoria de servidor acotada por bloque (ya no O(tamaño de la tabla)).
- Determinista: idéntico contenido ⇒ idéntico digest; una fila perdida/alterada/añadida cambia el digest (no es un SUM; sin cancelación simétrica).
- **Mismo método** en BEFORE (principal) y AFTER (scratch) del mismo run → comparación válida.

### 3.1 Cobertura de mercado

`MARKET_ENTITIES` suma a la cobertura de datos: `instruments` (catálogo), `ohlcv_bars` (OHLCV fuente de verdad) y `data_sync_log`. Antes `ohlcv_bars` quedaba fuera del digest por riesgo 7b (desborde del `string_agg`); con bloques ya se incluye. Verificado: `ohlcv_bars=167136` se fingerprinta y replica fiel a la scratch.

### 3.2 RTO

Tiempo real del restore completo (`rto-observado`, p.ej. ~12.3 s) registrado en el agent-log con la cobertura.

## 4. Cierre C2-01 (`db-restore.mjs`)

`--target-db` ahora se valida con la regex estricta `^[a-zA-Z0-9_.-]+$` **inmediatamente tras parsearlo y ANTES** de cualquier `DROP/CREATE DATABASE` destructivo (antes la validación quedaba solo en `redirectDatabaseUrlTo`, demasiado tarde). Verificado: `--target-db "evil;DROP DATABASE bolsa_v1;…"` aborta (exit 1) **sin tocar la BD**; `bolsa_v1` quedó intacta.

## 5. Backup 3-2-1 + RPO/RTO + restore-test periódico (decisión owner)

Decisión owner (opción "honesto/descopla"): copia local `db-backups/` **+ espejo a un DIR off-site configurable por env** + manifest registra ambas; RPO/RTO medidos; el 3er medio queda documentado como pendiente.

- **3-2-1:** `pgDumpToFile` copia el artefacto y su `.sha256` a `<DB_BACKUP_MIRROR_DIR>/db-backups/` (2º árbol/medio) cuando el env está configurado; la entrada del manifest registra `mirror:{dir,path}`. Espejo best-effort (un fallo no tumba el backup local). `resolveMirrorDir` acepta ruta absoluta o relativa al repo. `db:dr:test` usa dir temporal → no espeja.
- **RPO:** edad del snapshot más reciente. `db-backup:list` muestra RPO + estado espejo.
- **Restore-test periódico con VOLUMEN REAL:** `db-backup-cron-win.mjs` registra ahora DOS tareas Windows: `BolsaV1_DB_Backup` (diario 18:00) y **`BolsaV1_DR_RestoreTest`** (`db:dr:test` local diario 03:30; `--no-dr` cancela). Este scheduler cubre la BD local con datos reales (134 instrumentos, 167k OHLCV), que es la cobertura que el CI no puede tener (nace migrada-vacía).
- **`.github/workflows/release-tag-ci.yml` NO se modifica**: el job `dr-verify` ya ejecuta `node scripts/db-dr-verify.mjs` (TCP, gate por exit code) y este cambio conserva ese contrato (mismo script). Al ser fail-closed del release, no mutarlo sin necesidad es la opción segura.

## 6. Archivos (faena V2.15.5) — diffs sobre `16d84031`

| Fichero                          | Cambio                                                                                                                                  |
| -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| `scripts/db-dr-verify.mjs`       | Snapshot atómico `REPEATABLE READ` (una tx), parser `                                                                                   | `corregido, digest por bloques,`MARKET_ENTITIES` (OHLCV/instruments/data_sync_log), medida RTO. |
| `scripts/db-restore.mjs`         | C2-01: validación `--target-db` ANTES del DDL destructivo.                                                                              |
| `scripts/lib/backup.mjs`         | Espejo 3-2-1 (`mirrorDir`+`resolveMirrorDir`, `mirror` en manifest preservado por reconcile), `readManifest` exportada, `copyFileSync`. |
| `scripts/db-dump.mjs`            | Pasa `mirrorDir`, loguea espejo + RPO/duración.                                                                                         |
| `scripts/db-backup-list.mjs`     | Muestra RPO, estado espejo, retención.                                                                                                  |
| `scripts/db-backup-cron-win.mjs` | Añade tarea programada de restore-test DR diario.                                                                                       |

## 7. Deuda/clarificaciones

1. **3er medio off-site** (fuera de la máquina: Rclone/object-storage) **no se automatiza** (sin credenciales/infra). El espejo provee un 2º medio/árbol; el 3-2-1 completo queda pendiente de un destino remoto (basta apuntar `DB_BACKUP_MIRROR_DIR` a un mount Rclone).
2. **Restore-test en CI** sigue sobre BD vacía-migrada (naturaleza ephemeral del CI). El volumen real lo cubre el scheduler Windows local + runs a mano de `node scripts/db-dr-verify.mjs`.
3. `readManifest` pasa de privada a exportada (uso en `db-backup-list`); sin cambio de comportamiento.

## 8. TRASPASO — arranque del agente V2.16 (o próximo bloque)

- Working tree limpio sobre **V2.15.5**. Núcleo financiero congelado intacto.
- DR ya incluye: snapshot **atómico**, digest **por bloques**, **OHLCV+instruments+data_sync_log** en cobertura, **C2-01** y **3-2-1 con espejo** + **RPO/RTO** medidos.
- Verificación real (abajo). El job `dr-verify` corre el mismo script por TCP.
- **Pendiente natural V2.16:** elevar/taggear (run real) y materializar el **3er medio off-site**.

FIN DEL RELEVO — bloque **V2.15.5 (DR industrial)** implementado y **verificado real** en PG local con volumen real (DR ok + aislamiento 43 verdes + node --check OK + C2-01 rechazado antes de DDL).
