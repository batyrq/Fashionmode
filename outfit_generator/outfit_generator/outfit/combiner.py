"""
Combine catalog products into outfits.
"""
from typing import List, Dict, Optional, Tuple
from loguru import logger
import random

from config import OUTFIT_CATEGORIES
from outfit.color_rules import ColorHarmonyEngine


class OutfitCombiner:
    """Deterministic outfit builder with simple color and budget rules."""

    def __init__(self):
        self.color_engine = ColorHarmonyEngine()

    def create_outfits(
        self,
        products: List[Dict],
        style: str = "casual",
        max_budget: Optional[int] = None,
        num_outfits: int = 3,
    ) -> List[Dict]:
        """Build up to ``num_outfits`` complete outfits from the catalog."""
        grouped = self._group_products(products)
        candidates: List[Dict] = []
        seen: set[Tuple[str, ...]] = set()

        def add_candidate(outfit: Optional[Dict]) -> None:
            if not outfit:
                return
            key = tuple(sorted(item["id"] for item in outfit.get("items", [])))
            if key in seen:
                return
            seen.add(key)
            candidates.append(outfit)

        if grouped["top"] and grouped["bottom"]:
            for top in grouped["top"][:5]:
                for bottom in grouped["bottom"][:5]:
                    outfit = self._build_outfit(
                        base_products=[top, bottom],
                        outfit_type="top_bottom",
                        style=style,
                        max_budget=max_budget,
                        grouped=grouped,
                    )
                    add_candidate(outfit)
                    if len(candidates) >= num_outfits:
                        break
                if len(candidates) >= num_outfits:
                    break

        if len(candidates) < num_outfits and grouped["dress"]:
            for dress in grouped["dress"][:5]:
                outfit = self._build_outfit(
                    base_products=[dress],
                    outfit_type="dress",
                    style=style,
                    max_budget=max_budget,
                    grouped=grouped,
                )
                add_candidate(outfit)
                if len(candidates) >= num_outfits:
                    break

        if len(candidates) < num_outfits and grouped["top"] and grouped["bottom"] and grouped["outerwear"]:
            for top in grouped["top"][:5]:
                for bottom in grouped["bottom"][:5]:
                    for outerwear in grouped["outerwear"][:3]:
                        outfit = self._build_outfit(
                            base_products=[top, bottom, outerwear],
                            outfit_type="full",
                            style=style,
                            max_budget=max_budget,
                            grouped=grouped,
                        )
                        add_candidate(outfit)
                        if len(candidates) >= num_outfits:
                            break
                    if len(candidates) >= num_outfits:
                        break
                if len(candidates) >= num_outfits:
                    break

        for i, outfit in enumerate(candidates[:num_outfits], 1):
            outfit["outfit_number"] = i
            outfit["description"] = self._generate_description(outfit, style)

        logger.info(f"Created {len(candidates[:num_outfits])} outfits")
        return candidates[:num_outfits]

    def _group_products(self, products: List[Dict]) -> Dict[str, List[Dict]]:
        grouped = {cat: [] for cat in ["top", "bottom", "dress", "outerwear", "shoes", "accessories"]}

        for product in products:
            outfit_cat = product.get("outfit_category", "")
            if outfit_cat in grouped:
                grouped[outfit_cat].append(product)
                continue

            for cat, keywords in OUTFIT_CATEGORIES.items():
                if product.get("category") in keywords:
                    grouped[cat].append(product)
                    break

        return grouped

    def _build_outfit(
        self,
        base_products: List[Dict],
        outfit_type: str,
        style: str,
        max_budget: Optional[int],
        grouped: Dict[str, List[Dict]],
    ) -> Optional[Dict]:
        selected = []
        total_price = 0
        for product in base_products:
            selected.append(product)
            total_price += product.get("price", 0)

        selected, total_price = self._add_complements(
            selected=selected,
            total_price=total_price,
            grouped=grouped,
            max_budget=max_budget,
        )

        if max_budget is not None and total_price > max_budget:
            return None

        return {
            "name": self._build_name(selected, outfit_type),
            "style": style,
            "items": [self._project_item(item) for item in selected],
            "total_price": total_price,
            "type": outfit_type,
        }

    def _add_complements(
        self,
        selected: List[Dict],
        total_price: int,
        grouped: Dict[str, List[Dict]],
        max_budget: Optional[int],
    ) -> Tuple[List[Dict], int]:
        """Add outerwear, shoes, and accessories when they fit the outfit."""
        complement_order = ["outerwear", "shoes", "accessories"]
        result = list(selected)

        for category in complement_order:
            if any(item.get("outfit_category") == category for item in result):
                continue

            candidates = grouped.get(category, [])
            if not candidates:
                continue

            candidates = sorted(candidates, key=lambda item: item.get("price", 0))
            for candidate in candidates:
                candidate_price = candidate.get("price", 0)
                if max_budget is not None and total_price + candidate_price > max_budget:
                    continue
                if self._is_compatible_with_outfit(candidate, result):
                    result.append(candidate)
                    total_price += candidate_price
                    break

        return result, total_price

    def _is_compatible_with_outfit(self, candidate: Dict, outfit_items: List[Dict]) -> bool:
        candidate_colors = candidate.get("colors", [])
        if not candidate_colors:
            return True

        for item in outfit_items:
            if self.color_engine.are_colors_compatible(candidate_colors, item.get("colors", [])):
                return True

        return False

    def _project_item(self, product: Dict) -> Dict:
        return {
            "id": product.get("id"),
            "name": product.get("name"),
            "price": product.get("price", 0),
            "currency": product.get("currency"),
            "url": product.get("url"),
            "image_url": product.get("image_url"),
            "category": product.get("outfit_category", product.get("category")),
            "outfit_category": product.get("outfit_category"),
            "colors": product.get("colors", []),
            "sizes": product.get("sizes", []),
        }

    def _build_name(self, items: List[Dict], outfit_type: str) -> str:
        if outfit_type == "dress":
            base = next((item for item in items if item.get("outfit_category") == "dress"), None)
            if base:
                return f"Outfit with dress: {base.get('name')}"
        if outfit_type == "full":
            return "Full look"
        if len(items) >= 2:
            return f"Outfit: {items[0].get('name')} + {items[1].get('name')}"
        return "Outfit"

    def _generate_description(self, outfit: Dict, style: str) -> str:
        style_names = {
            "casual": "casual",
            "office": "office",
            "sport": "sport",
            "evening": "evening",
            "home": "home",
        }

        style_name = style_names.get(style, style)
        item_count = len(outfit.get("items", []))
        descriptors = [
            f"Balanced {style_name} outfit with {item_count} pieces",
            f"Complete look for the {style_name} style",
            f"Ready-to-wear {style_name} outfit",
            f"Color-matched items for a polished look",
        ]
        return random.choice(descriptors)
