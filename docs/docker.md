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

5. Aplica schema (`db:push`) y catálogo IBEX (`db:seed`)



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



## Espacio en disco



El volumen Docker `bolsa_pg_data` puede crecer con cada sincronización Yahoo (miles de barras OHLCV). Ver [DATA_MODEL.md](./DATA_MODEL.md) *(histórico: `DISK_AND_CLEANUP.md` eliminado; pendiente de borrar definitivamente cuando se confirme libre de uso).*

