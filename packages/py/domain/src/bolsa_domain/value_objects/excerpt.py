"""Helpers de texto puros para resúmenes de documentos (filings)."""

from __future__ import annotations


def prefer_summary_excerpt(text: str, *, max_chars: int = 12_000) -> str:
    """Prioriza bloques de riesgos / MD&A si aparecen; si no, cabeza del doc."""
    if not text:
        return ""
    lower = text.lower()
    anchors = (
        "item 1a",
        "item 1a.",
        "risk factors",
        "item 7",
        "management's discussion",
        "management’s discussion",
    )
    start = 0
    for anchor in anchors:
        idx = lower.find(anchor)
        if idx >= 0:
            start = idx
            break
    return text[start : start + max_chars].strip()


__all__ = ["prefer_summary_excerpt"]
