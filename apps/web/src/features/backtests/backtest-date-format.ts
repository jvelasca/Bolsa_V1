/** Display dates as dd/mm/yyyy for movie / result UI. */

export function formatDateDdMmYyyy(
  timestamp: string | null | undefined,
): string {
  if (!timestamp) return "—";
  const day = timestamp.slice(0, 10);
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(day);
  if (match) {
    return `${match[3]}/${match[2]}/${match[1]}`;
  }
  const ms = Date.parse(timestamp);
  if (Number.isNaN(ms)) return timestamp;
  const d = new Date(ms);
  const dd = String(d.getUTCDate()).padStart(2, "0");
  const mm = String(d.getUTCMonth() + 1).padStart(2, "0");
  const yyyy = d.getUTCFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

export function formatDateRangeDdMmYyyy(from: string, to: string): string {
  return `${formatDateDdMmYyyy(from)} → ${formatDateDdMmYyyy(to)}`;
}
