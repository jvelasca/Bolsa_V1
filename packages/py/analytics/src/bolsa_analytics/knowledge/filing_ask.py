"""FIE F2b++ — Q&A narrativo sobre chunks recuperados (sin recalcular ratios)."""

from __future__ import annotations

from typing import Any


def build_filing_ask_variables(
    *,
    ticker: str,
    sector: str | None,
    filing: dict[str, Any],
    question: str,
    context: str,
) -> dict[str, str]:
    """Variables para ``prompt_filing_ask_v1``."""
    return {
        "ticker": ticker or "—",
        "sector": sector or "—",
        "kind": str(filing.get("kind") or "other"),
        "originalName": str(filing.get("originalName") or "—"),
        "question": (question or "").strip() or "—",
        "context": context or "—",
    }


def heuristic_filing_answer(
    *,
    ticker: str,
    question: str,
    hits: list[dict[str, Any]],
) -> dict[str, Any]:
    """Fallback sin Ollama: cita los top chunks recuperados."""
    q = (question or "").strip()
    if not hits:
        answer = (
            f"No hay pasajes relevantes en el filing de {ticker} para: «{q or '—'}». "
            "Sube/Trae un 10-K con extracto textual e inténtalo de nuevo."
        )
        return {
            "answer": answer,
            "disclaimer": (
                "Respuesta heurística sin LLM. No es consejo de inversión "
                "ni sustituye la lectura del filing."
            ),
        }

    bullets: list[str] = []
    for hit in hits[:3]:
        label = hit.get("label") or hit.get("id") or "pasaje"
        snippet = str(hit.get("text") or "").replace("\n", " ").strip()
        if len(snippet) > 280:
            snippet = snippet[:277] + "…"
        bullets.append(f"• ({label}) {snippet}")

    answer = (
        f"{ticker} — respuesta heurística (TF-IDF, sin LLM) a «{q}»:\n"
        + "\n".join(bullets)
        + "\nContrasta con el snapshot FA Yahoo; este Q&A no calcula ratios ni Score_FUND."
    )
    return {
        "answer": answer,
        "disclaimer": (
            "Respuesta automática desde pasajes del documento. "
            "No es consejo de inversión ni sustituye la lectura del filing."
        ),
    }
