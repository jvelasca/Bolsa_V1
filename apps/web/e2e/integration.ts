/**
 * V1.64 / V1.67 — helpers Playwright: mock vs integración FastAPI+PostgreSQL.
 * V1.79 — split: implementations live in `e2e/helpers/*`; this file is the barrel.
 */
export * from "./helpers/ids";
export * from "./helpers/mercado";
export * from "./helpers/database";
export * from "./helpers/paper-day";
export * from "./helpers/stale-unknown";
export * from "./helpers/golden-session";
export * from "./helpers/lifecycle-snapshot";
export * from "./helpers/lifecycle-events";
export * from "./helpers/assertions";
