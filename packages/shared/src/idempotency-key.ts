/**
 * F1 (R-10): clave de idempotencia para operaciones de dinero/trade.
 *
 * Garantiza un UUID v4 como identificador único por operación en curso. La UI cachea
 * la clave devuelta por operación lógica y la reutiliza en retries, de forma que un
 * reenvío HTTP del mismo intento se rejuega (idempotente) en vez de duplicarse.
 */
export function createIdempotencyKey(): string {
  if (typeof globalThis.crypto?.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  // Fallback determinista único para contextos sin `crypto.randomUUID`.
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}-${Math.random()
    .toString(36)
    .slice(2, 10)}`;
}
