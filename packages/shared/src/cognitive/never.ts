/** Exhaustiveness helper for union switches (V1.57). */

export function assertNever(value: never, message?: string): never {
  throw new Error(message ?? `unexpected value: ${String(value)}`);
}
