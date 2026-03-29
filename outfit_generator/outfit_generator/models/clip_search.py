"""
CLIP-powered garment analysis with optional FAISS-backed similarity search.

This module must stay import-safe when optional ML extras are missing so that
try-on and catalog routes can still boot.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from loguru import logger
from PIL import Image, ImageOps

try:
    import faiss  # type: ignore

    FAISS_AVAILABLE = True
    FAISS_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - depends on local optional extras
    faiss = None  # type: ignore
    FAISS_AVAILABLE = False
    FAISS_IMPORT_ERROR = str(exc)

try:
    import torch  # type: ignore
    from transformers import CLIPModel, CLIPProcessor  # type: ignore

    CLIP_RUNTIME_AVAILABLE = True
    CLIP_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - depends on local optional extras
    torch = None  # type: ignore
    CLIPModel = None  # type: ignore
    CLIPProcessor = None  # type: ignore
    CLIP_RUNTIME_AVAILABLE = False
    CLIP_IMPORT_ERROR = str(exc)

from config import CLIP_EMBEDDING_DIM, CLIP_MODEL_NAME, FAISS_IDS_PATH, FAISS_INDEX_PATH


GARMENT_CATEGORY_PROMPTS = {
    "top": "a photo of a top garment such as a shirt, blouse, t-shirt, sweater, or hoodie",
    "bottom": "a photo of a bottom garment such as pants, jeans, shorts, or a skirt",
    "dress": "a photo of a dress or one-piece garment",
    "outerwear": "a photo of outerwear such as a jacket, coat, blazer, or cardigan",
    "shoes": "a photo of shoes or footwear",
    "accessories": "a photo of an accessory such as a bag, belt, hat, or jewelry",
    "full_outfit": "a photo of a complete outfit with multiple clothing items",
    "unknown": "a photo of a clothing item",
}

COLOR_ORDER = [
    "black",
    "white",
    "gray",
    "beige",
    "brown",
    "navy",
    "blue",
    "light blue",
    "red",
    "green",
    "pink",
    "purple",
    "yellow",
    "orange",
    "olive",
    "khaki",
    "burgundy",
    "multicolor",
]

COLOR_PROMPTS = {color: f"{color} clothing" for color in COLOR_ORDER}
COLOR_PROMPTS["navy"] = "navy blue clothing"
COLOR_PROMPTS["light blue"] = "light blue clothing"
COLOR_PROMPTS["olive"] = "olive green clothing"
COLOR_PROMPTS["multicolor"] = "multicolor clothing"

PATTERN_PROMPTS = {
    "solid": "solid color clothing without a visible pattern",
    "striped": "striped clothing",
    "plaid": "plaid clothing",
    "checkered": "checkered clothing",
    "floral": "floral pattern clothing",
    "polka_dot": "polka dot pattern clothing",
    "graphic_print": "graphic print clothing",
    "logo_print": "logo print clothing",
    "color_block": "color block clothing",
    "textured": "textured clothing",
    "denim": "denim clothing",
    "unknown": "clothing with no obvious pattern",
}

MATERIAL_PROMPTS = {
    "cotton": "cotton clothing",
    "denim": "denim clothing",
    "knit": "knit clothing",
    "leather": "leather clothing",
    "satin": "satin clothing",
    "silk": "silk clothing",
    "wool": "wool clothing",
    "linen": "linen clothing",
    "polyester": "polyester clothing",
    "fleece": "fleece clothing",
    "jersey": "jersey clothing",
    "unknown": "clothing with an unknown material",
}

FIT_PROMPTS = {
    "slim": "slim fit clothing",
    "regular": "regular fit clothing",
    "relaxed": "relaxed fit clothing",
    "oversized": "oversized clothing",
    "fitted": "fitted clothing",
    "structured": "structured clothing",
    "unknown": "clothing with an unclear fit",
}

SLEEVE_PROMPTS = {
    "sleeveless": "sleeveless clothing",
    "short_sleeve": "short sleeve clothing",
    "three_quarter": "three-quarter sleeve clothing",
    "long_sleeve": "long sleeve clothing",
    "unknown": "clothing with unclear sleeve length",
}

SEASON_PROMPTS = {
    "summer": "summer clothing",
    "spring": "spring clothing",
    "autumn": "autumn clothing",
    "winter": "winter clothing",
    "all-season": "all season clothing",
}

FORMALITY_PROMPTS = {
    "casual": "casual clothing",
    "sport": "sport clothing",
    "semi-formal": "semi formal clothing",
    "formal": "formal clothing",
    "streetwear": "streetwear clothing",
    "athleisure": "athleisure clothing",
    "unknown": "clothing with unclear formality",
}


class ClipFashionSearch:
    """Analyze garments and optionally search similar items."""

    def __init__(self, model_name: str = CLIP_MODEL_NAME, device: str = None):
        self.device = device or ("cuda" if CLIP_RUNTIME_AVAILABLE and torch and torch.cuda.is_available() else "cpu")
        self.processor = None
        self.model = None
        self.model_available = False

        if CLIP_RUNTIME_AVAILABLE and CLIPProcessor and CLIPModel:
            try:
                logger.info(f"Loading CLIP model on {self.device}...")
                self.processor = CLIPProcessor.from_pretrained(model_name)
                self.model = CLIPModel.from_pretrained(model_name).to(self.device)
                self.model.eval()
                self.model_available = True
                logger.info("CLIP model loaded successfully")
            except Exception as exc:
                CLIP_status = f"CLIP runtime failed to initialize: {exc}"
                logger.warning(CLIP_status)
        else:
            logger.warning(f"CLIP runtime unavailable: {CLIP_IMPORT_ERROR}")

        self.faiss_index: Optional[Any] = None
        self.product_embeddings: Optional[np.ndarray] = None
        self.product_ids: List[str] = []
        self._load_saved_index()

    def capability_status(self) -> Dict[str, Any]:
        return {
            "clip_runtime_available": CLIP_RUNTIME_AVAILABLE,
            "clip_import_error": CLIP_IMPORT_ERROR or None,
            "clip_model_loaded": self.model_available,
            "faiss_available": FAISS_AVAILABLE,
            "faiss_import_error": FAISS_IMPORT_ERROR or None,
            "faiss_index_loaded": self.faiss_index is not None,
            "faiss_index_path": str(FAISS_INDEX_PATH),
            "faiss_ids_path": str(FAISS_IDS_PATH),
            "faiss_index_file_exists": FAISS_INDEX_PATH.exists(),
            "faiss_ids_file_exists": FAISS_IDS_PATH.exists(),
        }

    def _load_saved_index(self) -> None:
        if not FAISS_AVAILABLE or faiss is None:
            return
        if not FAISS_INDEX_PATH.exists() or not FAISS_IDS_PATH.exists():
            return

        try:
            self.faiss_index = faiss.read_index(str(FAISS_INDEX_PATH))
            with open(FAISS_IDS_PATH, "r", encoding="utf-8") as file:
                product_ids = json.load(file)
            if not isinstance(product_ids, list):
                raise ValueError("FAISS ids file must contain a JSON list")
            self.product_ids = [str(product_id) for product_id in product_ids]
            logger.info(f"Loaded FAISS index with {len(self.product_ids)} product ids")
        except Exception as exc:
            logger.warning(f"Could not load saved FAISS index: {exc}")
            self.faiss_index = None
            self.product_ids = []

    def save_index(self, index_path: Path = FAISS_INDEX_PATH, ids_path: Path = FAISS_IDS_PATH) -> None:
        if not FAISS_AVAILABLE or faiss is None:
            raise RuntimeError(f"FAISS is not available: {FAISS_IMPORT_ERROR or 'unknown import error'}")
        if self.faiss_index is None:
            raise RuntimeError("FAISS index is not built")

        index_path.parent.mkdir(parents=True, exist_ok=True)
        ids_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.faiss_index, str(index_path))
        with open(ids_path, "w", encoding="utf-8") as file:
            json.dump(self.product_ids, file, ensure_ascii=False, indent=2)
        logger.info(f"Saved FAISS index to {index_path} and ids to {ids_path}")

    def _normalize_image(self, image: Image.Image) -> Image.Image:
        return ImageOps.exif_transpose(image).convert("RGB")

    def _embed_image_tensor(self, image: Image.Image):
        if not self.model_available or not self.processor or not self.model or not torch:
            raise RuntimeError("CLIP model is not available")
        inputs = self.processor(images=self._normalize_image(image), return_tensors="pt").to(self.device)
        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        return image_features[0]

    def _embed_texts(self, texts: List[str]):
        if not self.model_available or not self.processor or not self.model or not torch:
            raise RuntimeError("CLIP model is not available")
        inputs = self.processor(text=texts, return_tensors="pt", padding=True).to(self.device)
        with torch.no_grad():
            text_features = self.model.get_text_features(**inputs)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
        return text_features

    def _rank_labels(self, image_embedding, labels: List[str], prompt_map: Dict[str, str]) -> List[Dict[str, Any]]:
        text_embeddings = self._embed_texts([prompt_map[label] for label in labels])
        logits = torch.matmul(image_embedding.unsqueeze(0), text_embeddings.T)[0]
        if hasattr(self.model, "logit_scale"):
            logits = logits * self.model.logit_scale.exp().detach()
        probs = torch.softmax(logits, dim=0).detach().cpu().numpy().tolist()
        ranked = [{"label": label, "score": float(score), "prompt": prompt_map[label]} for label, score in zip(labels, probs)]
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked

    def _pick_best(self, ranked: List[Dict[str, Any]], threshold: float = 0.18) -> Dict[str, Any]:
        if not ranked:
            return {"label": "unknown", "score": 0.0}
        top = ranked[0]
        if top["score"] < threshold:
            return {"label": "unknown", "score": float(top["score"])}
        return {"label": top["label"], "score": float(top["score"])}

    def _pick_multiple(self, ranked: List[Dict[str, Any]], limit: int = 3, threshold: float = 0.12) -> List[Dict[str, Any]]:
        chosen: List[Dict[str, Any]] = []
        for item in ranked:
            if item["label"] == "unknown" or item["score"] < threshold:
                continue
            chosen.append({"label": item["label"], "score": float(item["score"])})
            if len(chosen) >= limit:
                break
        return chosen

    def _fallback_analysis(self, reason: str) -> Dict[str, Any]:
        return {
            "analysis_type": "clip",
            "summary": "Unclear garment",
            "category": "unknown",
            "dominant_colors": ["unknown"],
            "pattern": "unknown",
            "material": "unknown",
            "fit": "unknown",
            "sleeve_length": "unknown",
            "seasonality": "all-season",
            "formality": "unknown",
            "confidence": {
                "category": 0.0,
                "colors": 0.0,
                "pattern": 0.0,
                "material": 0.0,
                "fit": 0.0,
                "sleeve_length": 0.0,
                "seasonality": 0.0,
                "formality": 0.0,
            },
            "rankings": {},
            "warning": reason,
        }

    def analyze_garment(self, image: Image.Image) -> Dict[str, Any]:
        try:
            image_embedding = self._embed_image_tensor(image)
            category_ranked = self._rank_labels(image_embedding, list(GARMENT_CATEGORY_PROMPTS.keys()), GARMENT_CATEGORY_PROMPTS)
            color_ranked = self._rank_labels(image_embedding, COLOR_ORDER, COLOR_PROMPTS)
            pattern_ranked = self._rank_labels(image_embedding, list(PATTERN_PROMPTS.keys()), PATTERN_PROMPTS)
            material_ranked = self._rank_labels(image_embedding, list(MATERIAL_PROMPTS.keys()), MATERIAL_PROMPTS)
            fit_ranked = self._rank_labels(image_embedding, list(FIT_PROMPTS.keys()), FIT_PROMPTS)
            sleeve_ranked = self._rank_labels(image_embedding, list(SLEEVE_PROMPTS.keys()), SLEEVE_PROMPTS)
            season_ranked = self._rank_labels(image_embedding, list(SEASON_PROMPTS.keys()), SEASON_PROMPTS)
            formality_ranked = self._rank_labels(image_embedding, list(FORMALITY_PROMPTS.keys()), FORMALITY_PROMPTS)

            category = self._pick_best(category_ranked, threshold=0.2)
            colors = self._pick_multiple(color_ranked, limit=3, threshold=0.12)
            pattern = self._pick_best(pattern_ranked, threshold=0.16)
            material = self._pick_best(material_ranked, threshold=0.16)
            fit = self._pick_best(fit_ranked, threshold=0.16)
            sleeve = self._pick_best(sleeve_ranked, threshold=0.16)
            season = self._pick_best(season_ranked, threshold=0.14)
            formality = self._pick_best(formality_ranked, threshold=0.14)

            dominant_colors = [item["label"] for item in colors] or ["unknown"]
            confidence = {
                "category": category["score"],
                "colors": max((item["score"] for item in colors), default=0.0),
                "pattern": pattern["score"],
                "material": material["score"],
                "fit": fit["score"],
                "sleeve_length": sleeve["score"],
                "seasonality": season["score"],
                "formality": formality["score"],
            }

            summary_bits = []
            if category["label"] != "unknown":
                summary_bits.append(category["label"])
            if dominant_colors and dominant_colors[0] != "unknown":
                summary_bits.append(", ".join(dominant_colors[:2]))
            if pattern["label"] != "unknown":
                summary_bits.append(pattern["label"].replace("_", " "))
            if fit["label"] != "unknown":
                summary_bits.append(fit["label"])
            summary = " | ".join(summary_bits) if summary_bits else "Unclear garment"

            return {
                "analysis_type": "clip",
                "summary": summary,
                "category": category["label"],
                "dominant_colors": dominant_colors,
                "pattern": pattern["label"],
                "material": material["label"],
                "fit": fit["label"],
                "sleeve_length": sleeve["label"],
                "seasonality": season["label"],
                "formality": formality["label"],
                "confidence": confidence,
                "rankings": {
                    "category": category_ranked[:5],
                    "colors": color_ranked[:5],
                    "pattern": pattern_ranked[:5],
                    "material": material_ranked[:5],
                    "fit": fit_ranked[:5],
                    "sleeve_length": sleeve_ranked[:5],
                    "seasonality": season_ranked[:5],
                    "formality": formality_ranked[:5],
                },
            }
        except Exception as exc:
            logger.warning(f"Garment analysis fallback: {exc}")
            return self._fallback_analysis(str(exc))

    def extract_embedding(self, image: Image.Image) -> np.ndarray:
        try:
            if not self.model_available or not self.processor or not self.model or not torch:
                raise RuntimeError("CLIP model is not available")
            inputs = self.processor(images=image, return_tensors="pt", padding=True).to(self.device)
            with torch.no_grad():
                image_features = self.model.get_image_features(**inputs)
                image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            return image_features.cpu().numpy()[0]
        except Exception as exc:
            logger.error(f"Error extracting CLIP embedding: {exc}")
            return np.zeros(CLIP_EMBEDDING_DIM, dtype=np.float32)

    def extract_text_embedding(self, text: str) -> np.ndarray:
        try:
            if not self.model_available or not self.processor or not self.model or not torch:
                raise RuntimeError("CLIP model is not available")
            inputs = self.processor(text=[text], return_tensors="pt", padding=True).to(self.device)
            with torch.no_grad():
                text_features = self.model.get_text_features(**inputs)
                text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            return text_features.cpu().numpy()[0]
        except Exception as exc:
            logger.error(f"Error extracting text embedding: {exc}")
            return np.zeros(CLIP_EMBEDDING_DIM, dtype=np.float32)

    def build_index(self, products: List[Dict[str, Any]], image_dir: Optional[str] = None) -> None:
        if not FAISS_AVAILABLE or faiss is None:
            raise RuntimeError(f"FAISS is not available: {FAISS_IMPORT_ERROR or 'unknown import error'}")
        if not self.model_available:
            raise RuntimeError(f"CLIP runtime is not available: {CLIP_IMPORT_ERROR or 'model failed to load'}")

        embeddings = []
        self.product_ids = []
        for product in products:
            try:
                image_path = product.get("image_path") or product.get("image_url")
                if not image_path:
                    continue
                if image_path.startswith("http"):
                    import requests
                    from io import BytesIO

                    response = requests.get(image_path, timeout=5)
                    image = Image.open(BytesIO(response.content)).convert("RGB")
                else:
                    image = Image.open(image_path).convert("RGB")
                embeddings.append(self.extract_embedding(image))
                self.product_ids.append(product["id"])
            except Exception as exc:
                logger.warning(f"Could not process product {product.get('id')}: {exc}")

        if not embeddings:
            logger.warning("No embeddings for index building")
            return

        self.product_embeddings = np.array(embeddings, dtype=np.float32)
        self.faiss_index = faiss.IndexFlatIP(CLIP_EMBEDDING_DIM)
        faiss.normalize_L2(self.product_embeddings)
        self.faiss_index.add(self.product_embeddings)
        logger.info(f"FAISS index built: {len(embeddings)} items")

    def search_similar(
        self,
        query_image: Optional[Image.Image] = None,
        query_text: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        if not FAISS_AVAILABLE or faiss is None:
            logger.warning(f"Search by image unavailable: {FAISS_IMPORT_ERROR}")
            return []
        if self.faiss_index is None:
            logger.warning("FAISS index is not built")
            return []

        if query_image is not None:
            query_embedding = self.extract_embedding(query_image)
        elif query_text:
            query_embedding = self.extract_text_embedding(query_text)
        else:
            logger.error("query_image or query_text is required")
            return []

        query_embedding = query_embedding.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(query_embedding)
        distances, indices = self.faiss_index.search(query_embedding, top_k)

        results = []
        for index, distance in zip(indices[0], distances[0]):
            if index < len(self.product_ids):
                results.append({"product_id": self.product_ids[index], "similarity_score": float(distance)})
        logger.info(f"Found {len(results)} similar products")
        return results

    def find_complementary_items(self, base_product: Dict[str, Any], all_products: List[Dict[str, Any]], outfit_category: str) -> List[Dict[str, Any]]:
        from config import COLOR_GROUPS

        complementary_categories = []
        if outfit_category == "bottom":
            complementary_categories = ["top", "outerwear"]
        elif outfit_category == "top":
            complementary_categories = ["bottom", "outerwear"]
        elif outfit_category == "dress":
            complementary_categories = ["outerwear", "accessories"]

        candidates = [product for product in all_products if product.get("outfit_category") in complementary_categories]
        base_colors = [color.lower() for color in base_product.get("colors", [])]

        def is_color_compatible(product_colors: List[str]) -> bool:
            for color in product_colors:
                lowered = color.lower()
                if lowered in COLOR_GROUPS.get("neutral", []):
                    return True
                for _, group_colors in COLOR_GROUPS.items():
                    if lowered in group_colors:
                        for base_color in base_colors:
                            if base_color in group_colors or base_color in COLOR_GROUPS.get("neutral", []):
                                return True
            return False

        compatible = [product for product in candidates if is_color_compatible(product.get("colors", []))]
        compatible.sort(key=lambda item: item.get("price", 0))
        return compatible[:5]


def get_clip_capability_status() -> Dict[str, Any]:
    return {
        "clip_runtime_available": CLIP_RUNTIME_AVAILABLE,
        "clip_import_error": CLIP_IMPORT_ERROR or None,
        "faiss_available": FAISS_AVAILABLE,
        "faiss_import_error": FAISS_IMPORT_ERROR or None,
    }
