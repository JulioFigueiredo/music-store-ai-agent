"""Product tools: search_products and get_product_details."""

from emporio_agent.tools.catalog import Catalog, availability_label
from emporio_agent.tools.common import Record, ToolResult
from emporio_agent.tools.promotions import Promotions

MAX_PRODUCT_RESULTS = 10
MAX_ALTERNATIVES = 3


class ProductTools:
    """Catalog search and product details, with prices and promotions."""

    def __init__(self, catalog: Catalog, promotions: Promotions) -> None:
        self.catalog = catalog
        self.promotions = promotions

    def search_products(
        self,
        query: str = "",
        category: str = "",
        min_price: float | None = None,
        max_price: float | None = None,
        only_available: bool = True,
    ) -> ToolResult:
        """Search the catalog of musical instruments, with optional filters.

        Use it for lists and comparisons ("violões até R$ 1000", "guitarras
        Fender", "ukulele elétrico"). Results are sorted by price, cheapest
        first, with at most 10 products; `total_matches` and `truncated` tell
        whether there are more. Each product comes with its price,
        availability and any active promotion. For one specific product, use
        get_product_details instead.

        Args:
            query: Words to look for in the product name, brand or type, e.g.
                "yamaha nylon". Optional.
            category: Category name, e.g. "violões", "guitarras", "ukuleles",
                "saxofone". Optional.
            min_price: Minimum price in BRL. Optional.
            max_price: Maximum price in BRL. Optional.
            only_available: If true (default), hide products that cannot be
                bought now (out of stock, discontinued or coming soon).
        """
        candidates = self.catalog.products
        if category:
            category_ids, problem = self.catalog.resolve_category(category)
            if problem:
                return problem
            candidates = [p for p in candidates if p["category_id"] in category_ids]
        candidates = [
            p
            for p in candidates
            if self.catalog.matches_filters(p, query, min_price, max_price)
        ]
        hidden_count = 0
        if only_available:
            available = [p for p in candidates if p["is_available"]]
            hidden_count = len(candidates) - len(available)
            candidates = available
        return self._product_list(candidates, hidden_count)

    def get_product_details(self, product_name: str) -> ToolResult:
        """Get everything about one product: exact price, availability, specs,
        description, active promotion and expired promotions.

        Use it when the customer names a product ("quanto custa o Takamine
        GD20?") or asks whether a product is on promotion. If the product
        cannot be bought now, the result includes available alternatives from
        the same category. If the name is not found or is ambiguous, the
        result lists names to confirm with the customer; never guess.

        Args:
            product_name: Product name as the customer wrote it, e.g.
                "Takamine GD20".
        """
        matches = self.catalog.find_by_name(product_name)
        if len(matches) == 1:
            return self._details(matches[0])
        if matches:
            return {
                "found": False,
                "message": "Several products match. Ask which one the customer means.",
                "matching_products": [p["name"] for p in matches],
            }
        return {
            "found": False,
            "message": "No product with this name. Confirm with the customer "
            "(the suggestions may help); do not guess.",
            "suggestions": self.catalog.suggest_names(product_name),
        }

    def _product_list(self, products: list[Record], hidden_count: int) -> ToolResult:
        """Sort by price, cap the list and describe what was left out."""
        products = sorted(products, key=lambda p: p["price_brl"])
        shown = products[:MAX_PRODUCT_RESULTS]
        result: ToolResult = {
            "found": bool(shown),
            "total_matches": len(products),
            "truncated": len(products) > len(shown),
            "products": [self._summary(p) for p in shown],
        }
        if hidden_count:
            result["unavailable_matches_hidden"] = hidden_count
        if not shown:
            result["message"] = "No products match these filters."
        return result

    def _summary(self, product: Record) -> Record:
        """Name, category, price, availability and any active promotion."""
        summary = {
            **self.catalog.label(product),
            "price_brl": product["price_brl"],
            "availability": availability_label(product),
        }
        promotion = self.promotions.active_for(product)
        if promotion:
            summary["active_promotion"] = promotion
        return summary

    def _details(self, product: Record) -> ToolResult:
        """Full details of one product, plus alternatives if unavailable."""
        details: ToolResult = {"found": True, **self._summary(product)}
        if product["is_available"]:
            details["stock_quantity"] = product["stock_quantity"]
        details["specs"] = product["specs"]
        if product["description"]:
            details["description"] = product["description"]
        expired = self.promotions.expired_names(product)
        if expired:
            details["expired_promotions"] = expired
        if not product["is_available"]:
            details["available_alternatives"] = self._alternatives(product)
        return details

    def _alternatives(self, product: Record) -> list[Record]:
        """Available products from the same category, closest in price.

        The manual (section 7.3) asks to suggest alternatives for products
        that are out of stock or discontinued.
        """
        candidates = [
            p
            for p in self.catalog.products
            if p["category_id"] == product["category_id"]
            and p["is_available"]
            and p["product_id"] != product["product_id"]
        ]
        candidates.sort(key=lambda p: abs(p["price_brl"] - product["price_brl"]))
        return [self._summary(p) for p in candidates[:MAX_ALTERNATIVES]]
