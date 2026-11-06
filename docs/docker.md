# Docker en Bolsa V1

## ¿Qué hace Docker en este proyecto?

**Docker no ejecuta la aplicación** (ni React ni la API FastAPI). Esos servicios corren con Node.js y Python en tu máquina.

Docker solo levanta **PostgreSQL**, la base de datos local del proyecto.

```

┌─────────────┐     HTTP      ┌──────────────────┐     SQLAlchemy   ┌──────────────────┐

│  React Web  │ ────────────► │  API Python      │ ───────────────► │  PostgreSQL      │

│  :5173      │   :8000       │  FastAPI         │                  │  (Docker) :5432  │

└─────────────┘               └──────────────────┘                  └──────────────────┘

                                      ▲

                                      │ Prisma push + seed (bootstrap)

                                      │ packages/database

```

### Qué se guarda en PostgreSQL

| Dato | Descripción |

|------|-------------|

| **Instrumentos** | Catálogo IBEX 35 + importados desde Yahoo |

| **OHLCV** | Históricos diarios sincronizados desde Yahoo Finance |

| **Sync logs** | Registro de cada sincronización (éxito/error) |

| **Listas, cartera, alertas, backtests** | Persistidos por la API Python |

### Contenedor y archivos

| Elemento | Valor |

|----------|-------|

| Archivo de config | `docker-compose.yml` |

| Contenedor | `bolsa-postgres` |

| Imagen | `postgres:16-alpine` |

| Puerto | `localhost:5432` |

| Usuario / BD | `bolsa` / `bolsa_v1` |

| Contraseña | `bolsa_dev` |

| Volumen persistente | `bolsa_pg_data` (los datos sobreviven a reinicios) |

La API se conecta mediante `DATABASE_URL` en `.env`:

```

postgresql://bolsa:bolsa_dev@localhost:5432/bolsa_v1

```

## Arranque automático

Al ejecutar `pnpm dev`, `pnpm dev:log` o **F5** en Cursor, el proyecto:

1. Comprueba si **Docker Desktop** está en marcha

2. Si no lo está, **lo abre automáticamente** (Windows/macOS)

3. Espera a que el daemon responda

4. Levanta el contenedor `bolsa-postgres` si hace falta

5. Aplica schema (Alembic `ensure_migrated`) y catálogo IBEX (`db:seed`)

Comando manual equivalente:

```bash

pnpm db:ensure

```

## Comandos útiles

| Comando | Descripción |

|---------|-------------|

| `pnpm db:ensure` | Docker + PostgreSQL + schema + seed |

| `pnpm db:check` | Diagnóstico; repara si falta la BD |

| `pnpm db:start` | Solo levanta Docker y el contenedor |

| `pnpm db:studio` | Prisma Studio (UI para ver la BD) |

## Requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado

- Windows: `winget install Docker.DockerDesktop`

Si Docker no está instalado, los scripts mostrarán instrucciones de instalación.

## Parar PostgreSQL

```bash

docker compose down

```

Los datos se conservan en el volumen `bolsa_pg_data`. Para borrar todo:

```bash

docker compose down -v

```

## Copias de seguridad y restauración

El contenedor **no** guarda copias propias: los volcados se escriben fuera, en `db-backups/`
(gitignored), y se restauran con los scripts del repo.

```bash
pnpm db:dump                 # pg_dump -> db-backups/bolsa_v1-<sello>.sql[.gz] + prune
pnpm db:backup:list          # lista copias y retención vigente
pnpm db:restore --file <backup> --yes   # DESTRUCTIVO: recrea la BD y sube a Alembic head
```

- Retención: `DB_BACKUP_KEEP` (default 14). Directorio: `DB_BACKUP_DIR` (default `db-backups`).
- Estado en vivo (edad, checksum `.sha256`, revisión y espejo): **Configuración → BD → «Copias de
  seguridad»** o `GET /api/database/maintenance`.
- **Crear copia desde la UI**: `POST /api/database/backup` (botón «Crear copia ahora», escribir
  `COPIAR`): ejecuta el mismo `scripts/db-dump.mjs --dir <DB_BACKUP_DIR>` dentro de la máquina de la
  API, así que necesita `node` y `pg_dump`/Docker disponibles ahí (si faltan, responde 503 con un
  código; no simula éxito). El contenedor de la API **no** restaura ni hace VACUUM: eso sigue en CLI.
- Detalle completo, incluida la tarea programada de Windows: [DEV_STARTUP.md](./DEV_STARTUP.md#copias-de-seguridad-y-recuperación-bolsa_v1-local).

## Espacio en disco

El volumen Docker `bolsa_pg_data` puede crecer con cada sincronización Yahoo (miles de barras OHLCV). Ver [DATA_MODEL.md](./DATA_MODEL.md).
