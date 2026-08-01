# ADR 001: PostgreSQL + Prisma

## Estado

Aceptado — Sprint 0

## Contexto

Necesitamos persistencia relacional para OHLCV, cartera futura y auditoría de sync.

## Decisión

- **PostgreSQL 16** en Docker para desarrollo local.
- **Prisma** como ORM con migraciones versionadas y tipos TypeScript.

## Consecuencias

- Excelente soporte para constraints únicos en series temporales.
- Fácil evolución a TimescaleDB o particionado si crece el volumen intradía.
- Dependencia de `DATABASE_URL` en `.env`.
