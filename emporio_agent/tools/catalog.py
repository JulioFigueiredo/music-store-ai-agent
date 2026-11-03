"""The product catalog: products and categories indexed once, plus the
matching and lookups shared by the product and promotion tools.

This module has no tools of its own; it is the read model the tools use.
"""

from emporio_agent.data.store_data import StoreData
from emporio_agent.text_utils import (
    compact,
    matches_all_words,
    rank_by_similarity,
    word_similarity,
)
from emporio_agent.tools.common import Record, ToolResult, to_records

# Minimum difflib ratio for a query word to match a product word.
WORD_MATCH_RATIO = 0.8
# Minimum score for a category to match ("violao" -> "Violões").
CATEGORY_MATCH_SCORE = 0.8
# Minimum score for a product name to be offered as a "did you mean?".
SUGGESTION_MIN_SCORE = 0.5
MAX_SUGGESTIONS = 3


class Catalog:
    """Products and categories, with name, category and filter matching."""

    def __init__(self, data: StoreData) -> None:
        self.products = to_records(data.products)
        self.products_by_id = {p["product_id"]: p for p in self.products}
        self.categories = {c["category_id"]: c for c in to_records(data.categories)}

    def label(self, product: Record) -> Record:
        """Name and category: the minimum to identify a product."""
        return {
            "name": product["name"],
            "category": self.categories[product["category_id"]]["name"],
        }

    def resolve_category(self, text: str) -> tuple[set[int], ToolResult | None]:
        """Find the categories matching a text, or explain why there are none.

        Returns (category ids, None) on success, or (ids, problem) where
        `problem` is a ready-made tool result for the model. Compares with
        each category's name and description, so "saxofone" finds
        "Instrumentos de Sopro (Madeiras)". Ties are all kept ("sopro" matches
        both wind categories).
        """
        scored = [(category_score(text, c), c) for c in self.categories.values()]
        best_score = max(score for score, _ in scored)
        if best_score < CATEGORY_MATCH_SCORE:
            return set(), {
                "found": False,
                "message": f"No category matches '{text}'.",
                "available_categories": [c["name"] for c in self.categories.values()],
            }
        matched = [c for score, c in scored if score == best_score]
        ids = {c["category_id"] for c in matched}
        if not any(p["category_id"] in ids for p in self.products):
            return ids, {
                "found": False,
                "message": "The store does not carry products in this category "
                "at the moment. This is not a stock issue: do not say "
                "'out of stock', and do not invent products.",
                "categories": [c["name"] for c in matched],
            }
        return ids, None

    def matches_filters(
        self,
        product: Record,
        query: str,
        min_price: float | None,
        max_price: float | None,
    ) -> bool:
        """Check the price range and the text query for one product.

        The query is matched against the product name and its category name,
        so "violão nylon" finds nylon guitars in "Violões".
        """
        if min_price is not None and product["price_brl"] < min_price:
            return False
        if max_price is not None and product["price_brl"] > max_price:
            return False
        if not query:
            return True
        label = self.label(product)
        searchable = f"{label['name']} {label['category']}"
        return matches_all_words(query, searchable, WORD_MATCH_RATIO)

    def find_by_name(self, name: str) -> list[Record]:
        """Exact name first, then names containing the query.

        compact() ignores case, accents, spaces and hyphens, so "Takamine
        GD-20" finds "Takamine GD20 Dreadnought Natural".
        """
        key = compact(name)
        if not key:
            return []
        exact = [p for p in self.products if compact(p["name"]) == key]
        if exact:
            return exact
        return [p for p in self.products if key in compact(p["name"])]

    def suggest_names(self, name: str) -> list[str]:
        """Closest product names, for a "did you mean?" when nothing matched."""
        all_names = [p["name"] for p in self.products]
        return rank_by_similarity(
            name, all_names, MAX_SUGGESTIONS, SUGGESTION_MIN_SCORE
        )


def category_score(text: str, category: Record) -> float:
    """How well a text matches a category's name or description."""
    return max(
        word_similarity(text, category["name"]),
        word_similarity(text, category["description"]),
    )


def availability_label(product: Record) -> str:
    """Customer-facing availability, following the manual (section 7.3)."""
    if product["status"] == "discontinued":
        return "descontinuado (não faz mais parte do catálogo)"
    if product["status"] == "coming_soon":
        return "em breve"
    if product["stock_quantity"] <= 0:
        return "temporariamente indisponível (sem estoque)"
    return "disponível"
