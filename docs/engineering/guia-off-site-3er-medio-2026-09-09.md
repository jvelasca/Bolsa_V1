# GUÍA MVP — 3er medio off-site del backup 3-2-1 de `bolsa_v1` — 2026-09-09

> **Propietario:** bloque **V2.16-beta** (relevo `traspaso-relevo-v2-15-5-dr-industrial-2026-09-09.md`, deuda §7.1). El backup 3-2-1 quedó en V2.15.5 con **2 medios locales**: (1) `db-backups/` local y (2) espejo a `<DB_BACKUP_MIRROR_DIR>/db-backups/`. Este doc materializa **únicamente la guía** para añadir el **3er medio fuera de la máquina**; NO incluye credenciales/remote de ningún proveedor (`.env` local del owner).

## 1. Cómo encaja con la implementación (V2.15.5)

Ya está todo el gancho en `scripts/lib/backup.mjs` y `scripts/db-dump.mjs`: no se toca código para incorporar el 3er medio — solo se apunta el env **`DB_BACKUP_MIRROR_DIR`** a un namespace local que esté **sincronizado off-site**. Resumen del flujo real:

- `pgDumpToFile(opts)` escribe el dump y su `<file>.sha256` en `db-backups/` (1er medio) y, si `opts.mirrorDir` viene explícito, copia ambos a `<mirrorDir>/db-backups/` (2º medio) — **best-effort**: un fallo de copia no tumba el backup local ya escrito.
- `db-dump.mjs` (script `pnpm db:dump`) pasa `mirrorDir` resuelto por **`resolveMirrorDir()`**, que lee `process.env.DB_BACKUP_MIRROR_DIR` (acepta ruta absoluta `X:\…`/`\\…`/`/…` o relativa al repo). El manifest de cada backup registra `mirror:{dir,path}`.
- El 3er medio es **ortogonal** a esa variable de 2 doble copia: si apuntas `DB_BACKUP_MIRROR_DIR` a un montaje/remoto sincronizado, el "espejo" **ya viaja fuera de la máquina** — con lo que usas las 2 patas implementadas para alcanzar el medio off-site sin duplicar lógica.

## 2. Topología objetivo (3-2-1 honesto)

| Medio | Ubicación                                       | Fuente                    | Implementado    |
| ----- | ----------------------------------------------- | ------------------------- | --------------- |
| 1     | `db-backups/` (local repo)                      | generado por `db-dump`    | ✅ V2.15        |
| 2     | `<DB_BACKUP_MIRROR_DIR>/db-backups/`            | espejo de `pgDumpToFile`  | ✅ V2.15.5      |
| 3     | **fuera de la máquina** (remote/object-storage) | sync del medio 2 (Rclone) | ⏳ **este doc** |

Nota de honestidad del §7.1 del relevo: la implementación ya denomina "2º medio" al espejo configurable. Para **no** cambiar el significado de `mirror` (que el manifest ya persiste), el 3er medio fuera de la máquina se logra **sincronizando el árbol completo donde viva `DB_BACKUP_MIRROR_DIR`** hacia el remoto. De esta manera `mirror:{dir,path}` del manifest sigue siendo veraz y el medio 3 es el nombre del remoto Rclone.

## 3. Set-up MVP con Rclone (sin credenciales — preparado para apuntar)

Solo preparación declarativa; nada que requiera secretos.

### 3.1 Verifica que el espejo (2º medio) está activo y sano

Antes de remoto, asegúrate de que el hoyo ya vacía a un árbol propio y que el manifest refleja `mirror`:

```bash
# 1 vez: apuntar a un árbol local que sea TU namespace a sincronizar (o deja el
#      default relativo). Ejemplo (powershell):  $env:DB_BACKUP_MIRROR_DIR=".../bolsa-off-site"
# Añádelo a tu `.env` (NO versionado) si quieres que persista:
#   DB_BACKUP_MIRROR_DIR=bolsa-off-site
pnpm db:dump            # genera backup + espejo
pnpm db:backup:list     # muestra RPO + estado espejo (campo mirror)
```

### 3.2 Instala y configura Rclone (una vez, por el owner)

```bash
rclone config          # crea un remote de tu proveedor (ej. nombre 'odrive')
                      # NO deje credenciales en este repo; viven en ~/.config/rclone
```

### 3.3 Crear el intervalo de sync programado (Windows, schtasks)

Dos ventanas sencillas, a partir del mismo patrón que `db-backup-cron-win.mjs`:

```bash
# Después del backup diario (`BolsaV1_DB_Backup`, 18:00) y MUY separado del
# resto-test para no competir por I/O:
schtasks /Create /TN "BolsaV1_DB_MirrorOffsite" /SC DAILY /ST 18:45 ^
  /TR "rclone sync <RUTA_MIRROR_DIR_DB_BACKUPS> odrive:bolsa_v1/backups --progress" /F
```

> Sustituye `<RUTA_MIRROR_DIR_DB_BACKUPS>` por el árbol de backups que cuelga de `DB_BACKUP_MIRROR_DIR` (ej. `C:\...\bolsa-off-site\db-backups`) y `odrive:` por el nombre de tu remote Rclone.

### 3.4 Verificación periódica (restore-test con volumen real sigue igual)

El restore-test DR diario (`BolsaV1_DR_RestoreTest`, `pnpm db:dr:test`) cubre la integridad local; el recuperable off-site se comprueba con:

```bash
rclone check <RUTA_MIRROR_DIR_DB_BACKUPS> odrive:bolsa_v1/backups
```

## 4. Qué NO está cubierto / pendiente para cerrar del todo

1. **Solo sync; retención off-site sin estado**: el manifest/poda (`retentionPrune`) gestiona la retención solo en el árbol local del espejo. Si algún día se desea poda remota (conservar N en `odrive:`), habría que añadir una estrategia (`rclone delete --min-age` o un script dedicado); hoy el 3er medio crece con el espejo local.
2. **Credenciales/infra**: no se versionan credenciales; el owner debe `rclone config` y decidir el proveedor montado (local disk `/` y remoto). El resto del flujo no exige cambios de código.
3. **Automática de los scheduled tasks**: el schtasks anterior es a mano/modelo; el script `db-backup-cron-win.mjs` no se toca (su contrato no incluye medio 3). Puede extenderse en un futuro bloque si el owner lo desea.

FIN DE LA GUÍA — el 3er medio queda **preparado**: basta apuntar `DB_BACKUP_MIRROR_DIR` a un archivo montado/sincronizado y añadir el `rclone sync` diario.
