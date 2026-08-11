"""FIE F2b — resumen narrativo de filing (heurística; LLM vía prompt aparte).

Reglas: no inventa ratios; no escribe Score_FUND / fundamentals Yahoo.
"""

from __future__ import annotations

from typing import Any

from bolsa_domain.value_objects.excerpt import prefer_summary_excerpt


def build_filing_summary_variables(
    *,
    ticker: str,
    sector: str | None,
    filing: dict[str, Any],
    excerpt: str,
) -> dict[str, str]:
    """Variables para ``prompt_filing_summary_v1``."""
    return {
        "ticker": ticker or "—",
        "sector": sector or "—",
        "kind": str(filing.get("kind") or "other"),
        "originalName": str(filing.get("originalName") or "—"),
        "charCount": str(filing.get("charCount") or 0),
        "extractStatus": str(filing.get("extractStatus") or "—"),
        "excerpt": excerpt[:12_000] if excerpt else "—",
    }


def heuristic_filing_summary(
    *,
    ticker: str,
    filing: dict[str, Any],
    text: str | None,
) -> dict[str, Any]:
    """Fallback sin Ollama: 3 párrafos desde extract truncado."""
    kind = str(filing.get("kind") or "documento")
    name = str(filing.get("originalName") or "archivo")
    status = str(filing.get("extractStatus") or "—")
    excerpt = prefer_summary_excerpt(text or "", max_chars=900)

    if not excerpt:
        p1 = (
            f"Se adjuntó {kind} «{name}» para {ticker}, pero no hay texto extraíble "
            f"(estado: {status}). Sube un .txt o instala pypdf para PDF."
        )
        p2 = "Sin extracto no se pueden señalar riesgos o temas del filing."
        p3 = "Reintenta con un extracto textual del 10-K (Item 1A / Item 7) si el PDF falla."
    else:
        snippet = excerpt.replace("\n", " ").strip()
        if len(snippet) > 420:
            snippet = snippet[:417] + "…"
        p1 = f"{ticker}: resumen heurístico del {kind} «{name}» (sin LLM). Extracto: {snippet}"
        p2 = (
            "Revisa especialmente factores de riesgo, liquidez, deuda y cambios en resultados "
            "en el documento original; este resumen no calcula ratios."
        )
        p3 = (
            "El copiloto FA (Score_FUND) sigue usando solo el snapshot Yahoo; este filing "
            "es contexto narrativo y no altera el score."
        )

    return {
        "paragraphs": [p1, p2, p3],
        "disclaimer": (
            "Resumen automático de un documento subido por el usuario. "
            "No es consejo de inversión ni sustituye la lectura del filing."
        ),
    }
