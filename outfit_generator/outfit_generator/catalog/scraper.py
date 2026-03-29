"""
Avishu catalog scraper used to refresh the local sample catalog.

The demo app does not depend on this scraper at runtime, but it is the safest
way to rebuild `sample_catalog.json` when the local sample needs to be refreshed.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger

from config import AVISHU_BASE_URL, AVISHU_CATEGORIES


class AvishuScraper:
    """Small, robust scraper for the Avishu product pages used in this demo."""

    def __init__(self, base_url: str = AVISHU_BASE_URL):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            }
        )

    @staticmethod
    def _text(node) -> str:
        if node is None:
            return ""
        if hasattr(node, "get_text"):
            return node.get_text(" ", strip=True)
        return str(node).strip()

    @staticmethod
    def _extract_price(text: str) -> int:
        digits = "".join(char for char in text if char.isdigit())
        return int(digits) if digits else 0

    @staticmethod
    def _infer_outfit_category(category: str, title: str) -> str:
        lowered = f"{category} {title}".lower()
        if any(token in lowered for token in ["юбк", "брюк", "джин", "легин", "шорт"]):
            return "bottom"
        if "плать" in lowered:
            return "dress"
        if any(token in lowered for token in ["куртк", "пальт", "кардиг", "кофт", "худи", "жакет", "пиджак"]):
            return "outerwear"
        if any(token in lowered for token in ["обув", "кроссов", "ботин", "туфл"]):
            return "shoes"
        if any(token in lowered for token in ["сум", "рем", "аксесс", "украш"]):
            return "accessories"
        return "top"

    def parse_product_page(self, url: str) -> Optional[Dict]:
        try:
            response = self.session.get(url, timeout=60)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            title_elem = soup.find("h1", class_="product_title") or soup.find("h1")
            title = self._text(title_elem) or "Без названия"

            price_elem = soup.find(class_="price")
            price = self._extract_price(self._text(price_elem))

            image_url = ""
            img_elem = soup.find("img", class_="wp-post-image") or soup.find("img")
            if img_elem is not None:
                image_url = img_elem.get("src", "") or img_elem.get("data-src", "")
            if not image_url:
                og_image = soup.find("meta", attrs={"property": "og:image"})
                image_url = og_image.get("content", "") if og_image else ""

            description = ""
            desc_elem = soup.find(class_="woocommerce-product-details__short-description") or soup.find(class_="description")
            description = self._text(desc_elem)
            if not description:
                paragraph = soup.find("p")
                description = self._text(paragraph)

            category = "другое"
            lowered_url = url.lower()
            for known_category in AVISHU_CATEGORIES:
                if known_category in lowered_url:
                    category = known_category
                    break

            product = {
                "id": url.rstrip("/").split("/")[-1],
                "name": title,
                "price": price,
                "currency": "KZT",
                "url": url,
                "image_url": image_url,
                "category": category,
                "outfit_category": self._infer_outfit_category(category, title),
                "colors": ["черный"] if price else [],
                "sizes": ["S", "M", "L", "XL"],
                "description": description,
                "material": "",
                "style_tags": ["casual"],
                "in_stock": True,
            }
            logger.info(f"Parsed product: {title[:40]} ({price} KZT)")
            return product
        except Exception as exc:
            logger.error(f"Could not parse product {url}: {exc}")
            return None

    def parse_category_page(self, category_url: str, max_items: int = 20) -> List[Dict]:
        products: List[Dict] = []
        try:
            response = self.session.get(category_url, timeout=60)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            product_links: List[str] = []
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "/product/" in href and href not in product_links:
                    product_links.append(href)

            logger.info(f"Found {len(product_links)} products in category page {category_url}")
            for href in product_links[:max_items]:
                product = self.parse_product_page(href)
                if product:
                    products.append(product)
                time.sleep(0.4)
        except Exception as exc:
            logger.error(f"Could not parse category {category_url}: {exc}")

        return products

    def scrape_full_catalog(self, save_path: Optional[Path] = None, per_category_limit: int = 12) -> List[Dict]:
        all_products: List[Dict] = []
        for category in AVISHU_CATEGORIES:
            category_url = f"{self.base_url}/product-category/каталог/женщинам/{category}/"
            logger.info(f"Scraping category: {category}")
            all_products.extend(self.parse_category_page(category_url, max_items=per_category_limit))
            time.sleep(1)

        deduped: List[Dict] = []
        seen_ids = set()
        for product in all_products:
            product_id = product.get("id")
            if not product_id or product_id in seen_ids:
                continue
            seen_ids.add(product_id)
            deduped.append(product)

        if save_path:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as file:
                json.dump(deduped, file, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(deduped)} products to {save_path}")

        return deduped

    @staticmethod
    def load_catalog_from_json(json_path: Path) -> List[Dict]:
        with open(json_path, "r", encoding="utf-8") as file:
            return json.load(file)


if __name__ == "__main__":
    scraper = AvishuScraper()
    products = scraper.scrape_full_catalog(
        save_path=Path(__file__).resolve().parent / "sample_catalog.json",
    )
    print(f"Loaded {len(products)} products")
