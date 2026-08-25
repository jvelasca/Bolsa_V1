#!/usr/bin/env node
/**
 * Public Prisma schema commands (db:push / db:migrate / db:migrate:deploy)
 * fail closed. Alembic is the only schema authority (Ciclo C2).
 */
const MSG = 'Prisma schema is not authoritative. Use Alembic.';
console.error(MSG);
process.exit(1);
