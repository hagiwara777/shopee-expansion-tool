"""Market-neutral Brand selection helpers; confirmation remains market-specific."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def search_brand_options(
    brands: Iterable[Mapping[str, Any]], query: str, *, include_no_brand: bool = True,
) -> list[Mapping[str, Any]]:
    """Search API display names/IDs without inferring or confirming a Brand."""
    return [
        brand for brand in brands
        if (include_no_brand or not bool(brand["is_no_brand"]))
        and (
            not query.strip()
            or query.casefold() in str(brand["brand_name"]).casefold()
            or query.strip() in str(brand["brand_id"])
        )
    ]


def brand_option_label(brand: Mapping[str, Any]) -> str:
    return f"{brand['brand_id']} | {brand['brand_name']}"
