"""
Catalog access helpers for filtering and optional vector search.

The catalog should remain usable even when FAISS is not installed, so vector
search support is treated as an optional capability.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

try:
    import faiss  # type: ignore

    FAISS_AVAILABLE = True
    FAISS_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - depends on local optional extras
    faiss = None  # type: ignore
    FAISS_AVAILABLE = False
    FAISS_IMPORT_ERROR = str(exc)

from config import CATALOG_FILE, FAISS_INDEX_PATH, OUTFIT_CATEGORIES, STYLE_CATEGORIES


class ProductDatabase:
    """Simple catalog wrapper with optional vector-search support."""

    def __init__(self, catalog_path: Path = CATALOG_FILE):
        self.catalog_path = catalog_path
        self.products: List[Dict[str, Any]] = []
        self.product_embeddings: Optional[np.ndarray] = None
        self.faiss_index: Optional[Any] = None
        self.clip_model = None
        self._load_catalog()

    def _load_catalog(self) -> None:
        try:
            with open(self.catalog_path, "r", encoding="utf-8") as file:
                self.products = json.load(file)
            logger.info(f"Loaded {len(self.products)} products from catalog")
        except FileNotFoundError:
            logger.warning(f"Catalog not found: {self.catalog_path}")
            self.products = []

    def _write_catalog(self) -> None:
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.catalog_path, "w", encoding="utf-8") as file:
            json.dump(self.products, file, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(self.products)} products to catalog")

    def _generate_product_id(self, name: str) -> str:
        slug = re.sub(r"[^\w]+", "-", name.lower(), flags=re.UNICODE).strip("-")
        slug = slug or "catalog-item"
        return f"{slug}-{int(time.time())}"

    def search_by_attributes(
        self,
        style: Optional[str] = None,
        colors: Optional[List[str]] = None,
        budget: Optional[Tuple[int, int]] = None,
        sizes: Optional[List[str]] = None,
        category: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        candidates = self.products.copy()

        if style:
            normalized_style = style.lower()
            style_keywords = [normalized_style] + STYLE_CATEGORIES.get(normalized_style, [style])
            candidates = [
                product
                for product in candidates
                if any(keyword in product.get("style_tags", []) for keyword in style_keywords)
                or any(keyword in product.get("description", "").lower() for keyword in style_keywords)
            ]

        if colors:
            candidates = [
                product
                for product in candidates
                if any(color.lower() in [product_color.lower() for product_color in product.get("colors", [])] for color in colors)
            ]

        if budget:
            min_price, max_price = budget
            candidates = [
                product
                for product in candidates
                if min_price <= product.get("price", 0) <= max_price
            ]

        if sizes:
            candidates = [
                product
                for product in candidates
                if any(size in product.get("sizes", []) for size in sizes)
            ]

        if category and category != "full_outfit":
            outfit_categories = OUTFIT_CATEGORIES.get(category, [category])
            candidates = [
                product
                for product in candidates
                if product.get("outfit_category") in outfit_categories
                or product.get("category") in outfit_categories
            ]

        candidates = candidates[:limit]
        logger.info(f"Found {len(candidates)} products by attribute filters")
        return candidates

    def get_products_by_outfit_category(self, outfit_category: str) -> List[Dict[str, Any]]:
        categories = OUTFIT_CATEGORIES.get(outfit_category, [outfit_category])
        return [
            product
            for product in self.products
            if product.get("outfit_category") in categories
            or product.get("category") in categories
        ]

    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        for product in self.products:
            if product.get("id") == product_id:
                return product
        return None

    def get_all_colors(self) -> List[str]:
        colors = set()
        for product in self.products:
            colors.update(color.lower() for color in product.get("colors", []))
        return list(colors)

    def get_price_range(self) -> Tuple[int, int]:
        if not self.products:
            return (0, 0)
        prices = [product.get("price", 0) for product in self.products]
        return (min(prices), max(prices))

    def export_for_faiss(self, embeddings: np.ndarray) -> None:
        if not FAISS_AVAILABLE or faiss is None:
            raise RuntimeError(f"FAISS is not available: {FAISS_IMPORT_ERROR or 'unknown import error'}")

        self.product_embeddings = embeddings
        self.faiss_index = faiss.IndexFlatIP(embeddings.shape[1])
        faiss.normalize_L2(embeddings)
        self.faiss_index.add(embeddings)
        logger.info(f"FAISS index built with {len(embeddings)} vectors")

    def add_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        name = str(product_data.get("name") or "").strip()
        if not name:
            raise ValueError("Product name is required")

        product_id = str(product_data.get("id") or "").strip() or self._generate_product_id(name)
        if self.get_product_by_id(product_id):
            raise ValueError(f"Catalog item with id '{product_id}' already exists")

        category = str(product_data.get("category") or "").strip()
        outfit_category = str(product_data.get("outfit_category") or "").strip()
        if not category:
            raise ValueError("Product category is required")
        if not outfit_category:
            raise ValueError("Product outfit_category is required")

        product = {
            "id": product_id,
            "name": name,
            "price": float(product_data.get("price") or 0),
            "currency": str(product_data.get("currency") or "KZT").strip() or "KZT",
            "url": str(product_data.get("url") or "").strip() or None,
            "image_url": str(product_data.get("image_url") or "").strip(),
            "category": category,
            "outfit_category": outfit_category,
            "colors": [str(color).strip() for color in product_data.get("colors", []) if str(color).strip()],
            "sizes": [str(size).strip().upper() for size in product_data.get("sizes", []) if str(size).strip()],
            "description": str(product_data.get("description") or "").strip(),
            "material": str(product_data.get("material") or "").strip() or None,
            "style_tags": [str(tag).strip().lower() for tag in product_data.get("style_tags", []) if str(tag).strip()],
            "in_stock": bool(product_data.get("in_stock", True)),
        }

        self.products.append(product)
        self._write_catalog()
        return product

    def delete_product(self, product_id: str) -> bool:
        original_count = len(self.products)
        self.products = [product for product in self.products if str(product.get("id")) != str(product_id)]
        deleted = len(self.products) != original_count
        if deleted:
            self._write_catalog()
        return deleted

    def similarity_search(self, query_embedding: np.ndarray, top_k: int = 10) -> List[Dict[str, Any]]:
        if not FAISS_AVAILABLE or faiss is None:
            logger.warning(f"FAISS similarity search unavailable: {FAISS_IMPORT_ERROR}")
            return []

        if self.faiss_index is None or self.product_embeddings is None:
            logger.warning("FAISS index is not initialized")
            return []

        query_embedding = query_embedding.reshape(1, -1)
        faiss.normalize_L2(query_embedding)
        distances, indices = self.faiss_index.search(query_embedding, top_k)

        results = []
        for index, distance in zip(indices[0], distances[0]):
            if index < len(self.products):
                product = self.products[index].copy()
                product["similarity_score"] = float(distance)
                results.append(product)
        return results


def get_vector_search_capability() -> Dict[str, Any]:
    return {
        "available": FAISS_AVAILABLE,
        "import_error": FAISS_IMPORT_ERROR or None,
        "index_path": str(FAISS_INDEX_PATH),
        "index_file_exists": FAISS_INDEX_PATH.exists(),
    }
