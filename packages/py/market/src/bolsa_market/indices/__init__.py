"""Índices de mercado — discovery (Yahoo) + constitutivos (providers).

Capa A: Index Discovery (search quoteType=INDEX + aliases).
Capa B: ConstituentProvider (curated registry primero).
Capa C: materialización en InstrumentList (list_repository / L1+).

@see docs/engineering/lists-universes-design-2026-07-30.md §7
"""

from __future__ import annotations

from bolsa_market.indices.aliases import (
    INDEX_ALIASES,
    canonical_index_code,
    expand_index_query_aliases,
)
from bolsa_market.indices.constituents import (
    ConstituentMember,
    ConstituentProvider,
    ConstituentSet,
    CuratedConstituentProvider,
    default_constituent_provider,
    index_constituents_ready,
)
from bolsa_market.indices.discovery import IndexHit, discover_market_indices
from bolsa_market.indices.registry import (
    KNOWN_INDICES,
    KnownIndex,
    catalog_list_id_for_index,
    get_known_index,
    index_code_from_catalog_list_id,
)

__all__ = [
    "INDEX_ALIASES",
    "KNOWN_INDICES",
    "ConstituentMember",
    "ConstituentProvider",
    "ConstituentSet",
    "CuratedConstituentProvider",
    "IndexHit",
    "KnownIndex",
    "canonical_index_code",
    "catalog_list_id_for_index",
    "default_constituent_provider",
    "discover_market_indices",
    "expand_index_query_aliases",
    "get_known_index",
    "index_code_from_catalog_list_id",
    "index_constituents_ready",
]
