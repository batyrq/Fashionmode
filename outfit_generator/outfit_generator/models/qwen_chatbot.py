"""
Qwen2.5-VL integration for the stylist chatbot.
"""
import json
import importlib.util
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from PIL import Image
from loguru import logger
try:
    import torch  # type: ignore
    from transformers import AutoModelForVision2Seq, AutoProcessor  # type: ignore
    try:
        from transformers import BitsAndBytesConfig  # type: ignore
    except Exception:  # pragma: no cover - optional dependency
        BitsAndBytesConfig = None
    QWEN_RUNTIME_AVAILABLE = True
    QWEN_IMPORT_ERROR = ""
except Exception as exc:  # pragma: no cover - depends on optional local extras
    torch = None  # type: ignore
    AutoModelForVision2Seq = None  # type: ignore
    AutoProcessor = None  # type: ignore
    BitsAndBytesConfig = None
    QWEN_RUNTIME_AVAILABLE = False
    QWEN_IMPORT_ERROR = str(exc)

from config import QWEN_MAX_TOKENS, QWEN_MODEL_NAME, QWEN_TEMPERATURE
from outfit.combiner import OutfitCombiner


STYLE_ALIASES = {
    "casual": ["casual", "everyday", "relaxed", "повседнев", "прогулк", "отдых"],
    "office": ["office", "work", "business", "formal", "офис", "работ", "делов"],
    "sport": ["sport", "athletic", "training", "active", "спорт", "тренир", "актив"],
    "evening": ["evening", "party", "date", "event", "вечер", "праздник", "свидан"],
    "home": ["home", "lounge", "comfort", "дом", "домаш", "комфорт"],
}

QWEN_OUTFIT_GENERATION_PRODUCT_LIMIT = 12
QWEN_OUTFIT_GENERATION_MAX_TOKENS = 384
QWEN_OUTFIT_GENERATION_DIRECT_LIMIT = 6

COLOR_ALIASES = {
    "черный": ["black", "черн"],
    "белый": ["white", "бел"],
    "серый": ["gray", "grey", "сер"],
    "бежевый": ["beige", "beig", "беж"],
    "синий": ["blue", "navy", "син"],
    "голубой": ["light blue", "sky", "голуб"],
    "красный": ["red", "крас"],
    "зеленый": ["green", "зел"],
    "оливковый": ["olive", "олив"],
    "хаки": ["khaki", "хаки"],
    "коричневый": ["brown", "корич"],
    "тауп": ["taupe", "тауп"],
    "фиолетовый": ["purple", "violet", "фиолет"],
    "розовый": ["pink", "розов"],
    "желтый": ["yellow", "желт"],
    "оранжевый": ["orange", "оранж"],
    "золотой": ["gold", "golden", "золот"],
    "серебряный": ["silver", "серебр"],
}

CATEGORY_ALIASES = {
    "top": ["top", "shirt", "blouse", "tshirt", "tee", "верх", "футбол", "рубаш", "лонг", "свит"],
    "bottom": ["bottom", "pants", "trousers", "jeans", "skirt", "низ", "брюк", "джог", "юбк"],
    "dress": ["dress", "плать"],
    "shoes": ["shoes", "sneakers", "boots", "обув"],
    "accessories": ["accessories", "bag", "jewelry", "аксесс"],
    "full_outfit": ["full outfit", "full look", "look", "outfit", "образ", "лук", "комплект"],
}

OCCASION_ALIASES = {
    "work": ["work", "office", "работ", "офис", "делов"],
    "walk": ["walk", "stroll", "прогул", "отдых"],
    "event": ["event", "party", "date", "meeting", "праздник", "свидан", "мероп"],
    "everyday": ["everyday", "daily", "повседнев", "casual", "обыч"],
}

SIZE_PATTERN = re.compile(r"\b(xxxl|xxl|xl|l|m|s|xs)\b", re.IGNORECASE)


class QwenStylistChatbot:
    """Stylist chatbot powered by Qwen2.5-VL."""

    def __init__(
        self,
        model_name: str = QWEN_MODEL_NAME,
        device: str = None,
        quantization: Optional[str] = None,
    ):
        cuda_available = bool(QWEN_RUNTIME_AVAILABLE and torch is not None and torch.cuda.is_available())
        self.device = device or ("cuda" if cuda_available else "cpu")
        self.quantization = (quantization or os.getenv("QWEN_QUANTIZATION", "auto")).lower()
        self.mock_mode = False
        self.load_error: Optional[str] = None
        self.outfit_combiner = OutfitCombiner()

        logger.info(f"Loading Qwen2.5-VL on {self.device} with quantization={self.quantization}...")

        if not QWEN_RUNTIME_AVAILABLE or torch is None or AutoProcessor is None:
            self.load_error = QWEN_IMPORT_ERROR or "Qwen runtime dependencies are unavailable"
            logger.warning(f"Qwen runtime is unavailable: {self.load_error}. Falling back to heuristic mode.")
            self.mock_mode = True
            self.processor = None
            self.model = None
            return

        try:
            self.processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
            self.model = self._load_model(model_name)
            self.model.eval()
            self.load_error = None
            logger.info("Qwen2.5-VL loaded successfully")
        except Exception as exc:
            self.load_error = str(exc)
            logger.warning(f"Could not load Qwen model: {exc}. Falling back to mock mode.")
            self.mock_mode = True
            self.processor = None
            self.model = None

    def _load_model(self, model_name: str):
        if torch is None or AutoModelForVision2Seq is None:
            raise RuntimeError(f"Qwen runtime is unavailable: {QWEN_IMPORT_ERROR}")
        load_kwargs: Dict[str, Any] = {"trust_remote_code": True}
        bitsandbytes_available = importlib.util.find_spec("bitsandbytes") is not None

        if self.device == "cuda" and torch.cuda.is_available():
            prefer_4bit = self.quantization in {"auto", "4bit", "int4", "bnb4bit"}
            prefer_8bit = self.quantization in {"8bit", "int8"}

            if prefer_4bit and BitsAndBytesConfig is not None and bitsandbytes_available:
                load_kwargs.update(
                    {
                        "quantization_config": BitsAndBytesConfig(
                            load_in_4bit=True,
                            bnb_4bit_quant_type="nf4",
                            bnb_4bit_use_double_quant=True,
                            bnb_4bit_compute_dtype=torch.float16,
                        ),
                        "device_map": "auto",
                        "low_cpu_mem_usage": True,
                    }
                )
                logger.info("Using 4-bit quantized Qwen loading")
            elif prefer_8bit and BitsAndBytesConfig is not None and bitsandbytes_available:
                load_kwargs.update(
                    {
                        "quantization_config": BitsAndBytesConfig(load_in_8bit=True),
                        "device_map": "auto",
                        "low_cpu_mem_usage": True,
                    }
                )
                logger.info("Using 8-bit quantized Qwen loading")
            elif prefer_4bit and (BitsAndBytesConfig is None or not bitsandbytes_available):
                logger.warning("bitsandbytes is not installed; falling back to fp16 CUDA loading")
                load_kwargs.update(
                    {
                        "torch_dtype": torch.float16,
                        "device_map": "auto",
                        "low_cpu_mem_usage": True,
                    }
                )
            else:
                if BitsAndBytesConfig is None or not bitsandbytes_available:
                    logger.warning("bitsandbytes is not installed; falling back to fp16 CUDA loading")
                load_kwargs.update(
                    {
                        "torch_dtype": torch.float16,
                        "device_map": "auto",
                        "low_cpu_mem_usage": True,
                    }
                )
                logger.info("Using fp16 Qwen loading on CUDA")
        else:
            load_kwargs["torch_dtype"] = torch.float32
            logger.info("Using CPU Qwen loading")

        return AutoModelForVision2Seq.from_pretrained(model_name, **load_kwargs)

    def capability_status(self) -> Dict[str, Any]:
        return {
            "qwen_runtime_available": QWEN_RUNTIME_AVAILABLE,
            "qwen_import_error": QWEN_IMPORT_ERROR or None,
            "mock_mode": self.mock_mode,
            "model_loaded": self.model is not None,
            "device": self.device,
            "load_error": self.load_error,
        }

    @staticmethod
    def _extract_json_block(text: str, opening: str) -> Optional[str]:
        """Return the first balanced JSON object or array from free-form text."""
        closing = "}" if opening == "{" else "]"
        start = text.find(opening)
        if start == -1:
            return None

        depth = 0
        in_string = False
        escaped = False

        for idx in range(start, len(text)):
            char = text[idx]

            if escaped:
                escaped = False
                continue

            if char == "\\" and in_string:
                escaped = True
                continue

            if char == '"':
                in_string = not in_string
                continue

            if in_string:
                continue

            if char == opening:
                depth += 1
            elif char == closing:
                depth -= 1
                if depth == 0:
                    return text[start : idx + 1]

        return None

    @classmethod
    def _parse_json_response(cls, text: str, expected_type: type) -> Optional[Any]:
        """Parse model output that may contain prose or fenced JSON."""
        candidates: List[str] = []

        fenced_blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
        candidates.extend(block.strip() for block in fenced_blocks if block.strip())

        opening = "{" if expected_type is dict else "["
        balanced = cls._extract_json_block(text, opening)
        if balanced:
            candidates.append(balanced)

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue

            if isinstance(parsed, expected_type):
                return parsed

        return None

    def _run_generation(
        self,
        messages: List[Dict[str, Any]],
        user_image: Optional[Image.Image] = None,
        max_new_tokens: int = QWEN_MAX_TOKENS,
        temperature: float = QWEN_TEMPERATURE,
    ) -> str:
        if self.mock_mode or self.processor is None or self.model is None:
            raise RuntimeError("Qwen model is not available")

        text = self.processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        processor_kwargs: Dict[str, Any] = {"text": [text], "return_tensors": "pt"}
        if user_image is not None:
            processor_kwargs["images"] = [user_image]

        inputs = self.processor(**processor_kwargs)
        if self.device == "cuda" and torch.cuda.is_available():
            inputs = inputs.to(self.device)

        with torch.no_grad():
            generated_ids = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                do_sample=temperature > 0,
            )

        return self.processor.batch_decode(
            generated_ids[:, inputs["input_ids"].shape[1] :],
            skip_special_tokens=True,
        )[0]

    def analyze_query(
        self,
        user_query: str,
        user_image: Optional[Image.Image] = None,
        budget: Optional[int] = None,
        sizes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze the user's request.
        Returns style, colors, budget, category, occasion, and optional sizes.
        """
        if self.mock_mode:
            return self._mock_analyze_query(user_query, budget=budget, sizes=sizes)

        try:
            prompt = f"""
You are a fashion stylist for a marketplace.
Analyze the user request and return ONLY valid JSON.

Allowed styles: casual, office, sport, evening, home.
Allowed categories: top, bottom, dress, shoes, accessories, full_outfit, null.

Rules:
- Use the provided explicit budget if present.
- Use the provided sizes if present, but do not put sizes into the JSON unless you also detect them from the query.
- Prefer catalog-friendly values.
- If a field is unclear, use null.

User query: {user_query}
Explicit budget: {budget if budget is not None else "null"}
Explicit sizes: {sizes if sizes else "null"}

Return JSON in this shape:
{{
  "style": "casual",
  "colors": ["black", "white"],
  "budget": 5000,
  "category": "full_outfit",
  "occasion": "work"
}}
"""

            messages = [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}],
                }
            ]

            if user_image:
                messages[0]["content"].insert(0, {"type": "image", "image": user_image})

            generated_text = self._run_generation(messages, user_image=user_image)
            result = self._parse_json_response(generated_text, dict)
            if result is not None:
                normalized = self._normalize_intent(
                    result,
                    user_query=user_query,
                    budget_hint=budget,
                    sizes=sizes,
                )
                logger.info(f"Query analysis: {normalized}")
                return normalized

            logger.warning("Could not parse JSON response for query analysis")
            return self._mock_analyze_query(user_query, budget=budget, sizes=sizes)

        except Exception as exc:
            logger.error(f"Query analysis error: {exc}")
            return self._mock_analyze_query(user_query, budget=budget, sizes=sizes)

    def _normalize_intent(
        self,
        raw_intent: Dict[str, Any],
        user_query: str,
        budget_hint: Optional[int] = None,
        sizes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        query_lower = user_query.lower()
        style = self._normalize_style(raw_intent.get("style"), query_lower)
        colors = self._normalize_colors(raw_intent.get("colors"))
        if not colors:
            colors = self._detect_colors_from_query(query_lower)

        budget = self._coerce_budget(raw_intent.get("budget"))
        if budget_hint is not None:
            budget = budget_hint
        if budget is None:
            budget = self._detect_budget_from_query(query_lower)

        category = self._normalize_category(raw_intent.get("category"), query_lower)
        occasion = self._normalize_occasion(raw_intent.get("occasion"), query_lower, style)
        detected_sizes = self._detect_sizes_from_query(query_lower)
        if sizes:
            detected_sizes = self._merge_unique(detected_sizes, [str(size).upper() for size in sizes if size])

        normalized = {
            "style": style,
            "colors": colors or None,
            "budget": budget,
            "category": category,
            "occasion": occasion,
        }
        if detected_sizes:
            normalized["sizes"] = detected_sizes

        return normalized

    def _normalize_style(self, style: Any, query_lower: str = "") -> str:
        style_value = str(style).strip().lower() if style else ""
        if style_value in STYLE_ALIASES:
            return style_value

        for canonical, aliases in STYLE_ALIASES.items():
            if any(alias in query_lower for alias in aliases):
                return canonical

        return "casual"

    def _normalize_colors(self, colors: Any) -> List[str]:
        if not colors:
            return []

        if isinstance(colors, str):
            colors = [colors]

        normalized: List[str] = []
        for color in colors:
            text = str(color).strip().lower()
            if not text:
                continue
            normalized.append(self._normalize_color_token(text))

        return self._merge_unique(normalized)

    def _normalize_color_token(self, token: str) -> str:
        for canonical, aliases in COLOR_ALIASES.items():
            if token == canonical or any(alias in token for alias in aliases):
                return canonical
        return token

    def _detect_colors_from_query(self, query_lower: str) -> List[str]:
        detected: List[str] = []
        for canonical, aliases in COLOR_ALIASES.items():
            if any(alias in query_lower for alias in aliases):
                detected.append(canonical)
        return self._merge_unique(detected)

    def _coerce_budget(self, budget: Any) -> Optional[int]:
        if budget is None:
            return None
        if isinstance(budget, bool):
            return None
        if isinstance(budget, (int, float)):
            value = int(budget)
            return value if value > 0 else None
        if isinstance(budget, str):
            digits = re.sub(r"[^\d]", "", budget)
            if digits:
                value = int(digits)
                return value if value > 0 else None
        return None

    def _detect_budget_from_query(self, query_lower: str) -> Optional[int]:
        match = re.search(r"(\d[\d\s.,]*)", query_lower)
        if not match:
            return None

        digits = re.sub(r"[^\d]", "", match.group(1))
        if not digits:
            return None

        value = int(digits)
        upper_bound_markers = ["up to", "under", "below", "??", "?? ??????", "????", "maximum", "max"]
        if "k" in query_lower or any(marker in query_lower for marker in upper_bound_markers):
            if len(digits) <= 2:
                value *= 1000
        elif len(digits) <= 2 and any(marker in query_lower for marker in ["???", "????", "??????????", "??????", "???"]):
            value *= 1000

        return value if value > 0 else None

    def _normalize_category(self, category: Any, query_lower: str = "") -> Optional[str]:
        category_value = str(category).strip().lower() if category else ""
        if category_value in CATEGORY_ALIASES:
            return category_value

        for canonical, aliases in CATEGORY_ALIASES.items():
            if any(alias in query_lower for alias in aliases):
                return canonical

        return None

    def _normalize_occasion(self, occasion: Any, query_lower: str, style: str) -> str:
        occasion_value = str(occasion).strip().lower() if occasion else ""
        if occasion_value:
            for canonical, aliases in OCCASION_ALIASES.items():
                if occasion_value == canonical or any(alias in occasion_value for alias in aliases):
                    return canonical

        for canonical, aliases in OCCASION_ALIASES.items():
            if any(alias in query_lower for alias in aliases):
                return canonical

        return "everyday" if style == "casual" else style

    def _detect_sizes_from_query(self, query_lower: str) -> List[str]:
        matches = [match.group(1).upper() for match in SIZE_PATTERN.finditer(query_lower)]
        return self._merge_unique(matches)

    def _merge_unique(self, values: Sequence[str], extra: Optional[Sequence[str]] = None) -> List[str]:
        ordered: List[str] = []
        seen = set()
        for value in list(values) + list(extra or []):
            if value is None:
                continue
            normalized = str(value).strip()
            if not normalized:
                continue
            if normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered

    def generate_outfit_recommendations(
        self,
        style_intent: Dict[str, Any],
        available_products: List[Dict],
    ) -> List[Dict]:
        """
        Generate outfit recommendations based on query analysis and the catalog.
        """
        if not available_products:
            return []

        intent = self._normalize_intent(style_intent, user_query="", budget_hint=None, sizes=style_intent.get("sizes"))

        if self.mock_mode:
            return self._mock_generate_outfits(intent, available_products)

        if len(available_products) > QWEN_OUTFIT_GENERATION_DIRECT_LIMIT:
            logger.info(
                f"Skipping direct Qwen outfit synthesis for {len(available_products)} products; using deterministic assembly after Qwen intent analysis"
            )
            return self._project_fallback_outfits(intent, available_products)

        try:
            candidate_products = available_products[:QWEN_OUTFIT_GENERATION_PRODUCT_LIMIT]
            products_text = "\n".join(
                [
                    f"- id={p.get('id')} | name={p.get('name')} | price={p.get('price')} | currency={p.get('currency', 'KZT')} | "
                    f"category={p.get('category')} | outfit_category={p.get('outfit_category')} | colors={', '.join(p.get('colors', []))} | url={p.get('url', '')}"
                    for p in candidate_products
                ]
            )

            prompt = f"""
You are a stylist assistant for a fashion marketplace.
Build exactly 3 outfit options from the provided catalog items.

Requirements:
- Use only the listed product IDs.
- Prefer complete looks with top + bottom + shoes + accessories when possible.
- Keep the outfits aligned with style={intent.get('style', 'casual')}.
- Respect budget={intent.get('budget', 'null')} when possible.
- Return ONLY JSON and nothing else.

Available catalog items:
{products_text}

Return a JSON array shaped like:
[
  {{
    "name": "Office look #1",
    "items": [
      {{"id": "product_id", "name": "Item name", "price": 0}}
    ],
    "total_price": 0,
    "description": "Short explanation"
  }}
]
"""

            messages = [
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}],
                }
            ]

            logger.info(
                f"Generating outfits with Qwen from {len(candidate_products)} candidate products on {self.device}"
            )
            generated_text = self._run_generation(
                messages,
                max_new_tokens=QWEN_OUTFIT_GENERATION_MAX_TOKENS,
                temperature=0.3,
            )
            parsed_outfits = self._parse_json_response(generated_text, list) or []
            normalized_outfits = self._normalize_outfits(parsed_outfits, candidate_products, intent)
            fallback_outfits = self._project_fallback_outfits(intent, candidate_products)
            merged = self._rank_and_merge_outfits(normalized_outfits, fallback_outfits, intent)
            logger.info(
                f"Generated outfits: model={len(normalized_outfits)}, fallback={len(fallback_outfits)}, final={len(merged)}"
            )
            return merged[:3]

        except Exception as exc:
            logger.error(f"Outfit generation error: {exc}")
            return self._mock_generate_outfits(intent, available_products)

    def _normalize_outfits(
        self,
        outfits: List[Dict[str, Any]],
        available_products: List[Dict],
        style_intent: Dict[str, Any],
    ) -> List[Dict]:
        product_map = {product.get("id"): product for product in available_products if product.get("id")}
        normalized: List[Dict] = []
        for index, outfit in enumerate(outfits, 1):
            if not isinstance(outfit, dict):
                continue

            resolved_items = self._resolve_outfit_items(outfit, product_map)
            if not resolved_items:
                continue

            resolved_items, total_price = self._complete_outfit_items(
                resolved_items,
                available_products,
                style_intent.get("budget"),
            )

            normalized.append(
                {
                    "name": outfit.get("name") or f"Outfit #{index}",
                    "style": style_intent.get("style", "casual"),
                    "items": resolved_items,
                    "total_price": total_price,
                    "description": outfit.get("description") or self._fallback_description(style_intent, len(resolved_items)),
                    "source": "qwen",
                }
            )

        return normalized

    def _resolve_outfit_items(
        self,
        outfit: Dict[str, Any],
        product_map: Dict[str, Dict],
    ) -> List[Dict]:
        resolved: List[Dict] = []
        for item in outfit.get("items", []):
            product_id = None
            if isinstance(item, dict):
                product_id = item.get("id")
            elif isinstance(item, str):
                product_id = item

            product = product_map.get(product_id)
            if not product:
                continue

            resolved.append(self._project_product(product))

        return resolved

    def _project_product(self, product: Dict, category: Optional[str] = None) -> Dict:
        return {
            "id": product.get("id"),
            "name": product.get("name"),
            "price": product.get("price", 0),
            "currency": product.get("currency"),
            "url": product.get("url"),
            "image_url": product.get("image_url"),
            "category": category or product.get("outfit_category", product.get("category")),
            "outfit_category": product.get("outfit_category"),
            "colors": product.get("colors", []),
            "sizes": product.get("sizes", []),
        }

    def _complete_outfit_items(
        self,
        items: List[Dict],
        available_products: List[Dict],
        max_budget: Optional[int],
    ) -> Tuple[List[Dict], int]:
        selected = [dict(item) for item in items]
        total_price = sum(item.get("price", 0) for item in selected)
        grouped = self._group_products(available_products)

        for category in ["outerwear", "shoes", "accessories"]:
            if any(item.get("outfit_category") == category or item.get("category") == category for item in selected):
                continue

            for candidate in sorted(grouped.get(category, []), key=lambda product: product.get("price", 0)):
                candidate_price = candidate.get("price", 0)
                if max_budget is not None and total_price + candidate_price > max_budget:
                    continue
                if self._is_compatible_candidate(candidate, selected):
                    selected.append(self._project_product(candidate))
                    total_price += candidate_price
                    break

        return selected, total_price

    def _group_products(self, products: List[Dict]) -> Dict[str, List[Dict]]:
        grouped = {cat: [] for cat in ["top", "bottom", "dress", "outerwear", "shoes", "accessories"]}
        for product in products:
            outfit_category = product.get("outfit_category")
            if outfit_category in grouped:
                grouped[outfit_category].append(product)
        return grouped

    def _is_compatible_candidate(self, candidate: Dict, outfit_items: List[Dict]) -> bool:
        candidate_colors = candidate.get("colors", [])
        if not candidate_colors:
            return True

        for item in outfit_items:
            if self.outfit_combiner.color_engine.are_colors_compatible(candidate_colors, item.get("colors", [])):
                return True

        return False

    def _project_fallback_outfits(self, intent: Dict[str, Any], available_products: List[Dict]) -> List[Dict]:
        fallback = self.outfit_combiner.create_outfits(
            available_products,
            style=intent.get("style", "casual"),
            max_budget=intent.get("budget"),
            num_outfits=3,
        )
        for outfit in fallback:
            outfit["source"] = "combiner"
        return fallback

    def _rank_and_merge_outfits(
        self,
        model_outfits: List[Dict],
        fallback_outfits: List[Dict],
        intent: Dict[str, Any],
    ) -> List[Dict]:
        combined = []
        seen = set()

        for outfit in model_outfits + fallback_outfits:
            key = tuple(sorted(item.get("id") for item in outfit.get("items", []) if item.get("id")))
            if not key or key in seen:
                continue
            seen.add(key)
            combined.append(outfit)

        combined.sort(key=lambda outfit: self._score_outfit(outfit, intent), reverse=True)
        return combined

    def _score_outfit(self, outfit: Dict, intent: Dict[str, Any]) -> float:
        categories = {
            item.get("outfit_category") or item.get("category")
            for item in outfit.get("items", [])
            if item.get("outfit_category") or item.get("category")
        }

        score = float(len(outfit.get("items", [])))
        if "dress" in categories:
            score += 3.0
        if "top" in categories and "bottom" in categories:
            score += 3.0
        if "outerwear" in categories:
            score += 1.5
        if "shoes" in categories:
            score += 2.0
        if "accessories" in categories:
            score += 1.0
        if outfit.get("style") == intent.get("style"):
            score += 1.0

        budget = intent.get("budget")
        total_price = outfit.get("total_price")
        if budget and total_price:
            if total_price <= budget:
                score += 2.0
            else:
                score += max(0.0, 1.0 - ((total_price - budget) / max(budget, 1)))

        if outfit.get("source") == "qwen":
            score += 0.25

        return score

    def _fallback_description(self, intent: Dict[str, Any], item_count: int) -> str:
        style = intent.get("style", "casual")
        return f"{style.capitalize()} outfit with {item_count} items"

    def _mock_analyze_query(
        self,
        user_query: str,
        budget: Optional[int] = None,
        sizes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Fallback rule-based parser."""
        query_lower = user_query.lower()

        style = self._normalize_style(None, query_lower)
        colors = self._detect_colors_from_query(query_lower)
        detected_budget = budget if budget is not None else self._detect_budget_from_query(query_lower)
        category = self._normalize_category(None, query_lower)
        occasion = self._normalize_occasion(None, query_lower, style)
        detected_sizes = self._detect_sizes_from_query(query_lower)
        if sizes:
            detected_sizes = self._merge_unique(detected_sizes, [str(size).upper() for size in sizes if size])

        result = {
            "style": style,
            "colors": colors if colors else None,
            "budget": detected_budget,
            "category": category,
            "occasion": occasion,
        }
        if detected_sizes:
            result["sizes"] = detected_sizes

        logger.info(f"Mock query analysis: {result}")
        return result

    def _mock_generate_outfits(
        self,
        style_intent: Dict[str, Any],
        available_products: List[Dict],
    ) -> List[Dict]:
        """Fallback outfit generator."""
        outfits = self._project_fallback_outfits(style_intent, available_products)
        if outfits:
            return outfits[:3]

        products_by_category = self._group_products(available_products)
        fallback_outfits: List[Dict] = []

        if products_by_category["top"] and products_by_category["bottom"]:
            top = products_by_category["top"][0]
            bottom = products_by_category["bottom"][0]
            fallback_outfits.append(
                {
                    "name": "Everyday look #1",
                    "style": style_intent.get("style", "casual"),
                    "items": [self._project_product(top), self._project_product(bottom)],
                    "total_price": top.get("price", 0) + bottom.get("price", 0),
                    "description": self._fallback_description(style_intent, 2),
                    "source": "mock",
                }
            )

        if products_by_category["dress"]:
            dress = products_by_category["dress"][0]
            fallback_outfits.append(
                {
                    "name": "Dress look #2",
                    "style": style_intent.get("style", "casual"),
                    "items": [self._project_product(dress)],
                    "total_price": dress.get("price", 0),
                    "description": self._fallback_description(style_intent, 1),
                    "source": "mock",
                }
            )

        if products_by_category["top"] and products_by_category["bottom"] and products_by_category["outerwear"]:
            top = products_by_category["top"][0]
            bottom = products_by_category["bottom"][0]
            outer = products_by_category["outerwear"][0]
            fallback_outfits.append(
                {
                    "name": "Layered look #3",
                    "style": style_intent.get("style", "casual"),
                    "items": [self._project_product(top), self._project_product(bottom), self._project_product(outer)],
                    "total_price": top.get("price", 0) + bottom.get("price", 0) + outer.get("price", 0),
                    "description": self._fallback_description(style_intent, 3),
                    "source": "mock",
                }
            )

        if style_intent.get("budget"):
            budget = style_intent["budget"]
            fallback_outfits = [outfit for outfit in fallback_outfits if outfit["total_price"] <= budget * 1.2]

        logger.info(f"Mock generation: {len(fallback_outfits)} outfits")
        return fallback_outfits[:3]
