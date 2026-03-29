"""Project configuration for the AI Stylist demo backend."""

from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).parent
APPDATA_BASE_DIR = Path(
    os.getenv("AI_STYLIST_DATA_DIR")
    or (Path(os.getenv("LOCALAPPDATA", str(BASE_DIR))) / "AIStylistData")
)
DATA_DIR = APPDATA_BASE_DIR / "data"
MODELS_DIR = APPDATA_BASE_DIR / "models_cache"
CATALOG_FILE = BASE_DIR / "catalog" / "sample_catalog.json"

# Qwen2.5-VL
QWEN_MODEL_NAME = "Qwen/Qwen2.5-VL-3B-Instruct"
QWEN_MAX_TOKENS = 512
QWEN_TEMPERATURE = 0.7

# CLIP
CLIP_MODEL_NAME = "openai/clip-vit-base-patch32"
CLIP_EMBEDDING_DIM = 512

# FAISS
FAISS_INDEX_PATH = DATA_DIR / "faiss_index.index"
FAISS_IDS_PATH = DATA_DIR / "faiss_index_ids.json"

# MediaPipe
MEDIAPIPE_MODEL_COMPLEXITY = 1
MEDIAPIPE_MIN_DETECTION_CONFIDENCE = 0.5

# Avishu catalog source
AVISHU_BASE_URL = "https://avishu.kz"
AVISHU_CATEGORIES = [
    "новинки",
    "верхняя-одежда",
    "база",
    "кардиганы-и-кофты",
    "брюки",
    "юбки",
    "костюмы",
    "платья",
    "футболки",
    "лонгсливы",
]

OUTFIT_CATEGORIES = {
    "top": ["футболки", "лонгсливы", "рубашки", "блузы", "кардиганы", "кофты"],
    "bottom": ["брюки", "юбки", "джогеры", "легинсы"],
    "dress": ["платья", "платье-футболка"],
    "outerwear": ["верхняя одежда", "мантия", "пальто", "куртки"],
    "shoes": ["обувь"],
    "accessories": ["аксессуары", "сумки", "украшения"],
}

COLOR_GROUPS = {
    "neutral": ["черный", "белый", "серый", "бежевый", "тауп", "коричневый"],
    "warm": ["красный", "оранжевый", "желтый", "золотой", "терракотовый"],
    "cool": ["синий", "голубой", "фиолетовый", "серебряный"],
    "natural": ["зеленый", "оливковый", "хаки"],
}

BODY_TYPES = {
    "hourglass": "Песочные часы",
    "pear": "Груша",
    "apple": "Яблоко",
    "rectangle": "Прямоугольник",
    "inverted_triangle": "Треугольник (перевернутый)",
}

BODY_TYPE_RECOMMENDATIONS = {
    "hourglass": {
        "good": ["V-вырез", "приталенный силуэт", "высокая талия", "пояс"],
        "avoid": ["мешковатая одежда", "прямые силуэты"],
        "description": "Ваша фигура сбалансирована. Подчеркивайте талию!",
    },
    "pear": {
        "good": ["яркий верх", "V-вырез", "расклешенные брюки", "A-силуэт"],
        "avoid": ["облегающий низ", "яркие принты на бедрах"],
        "description": "Акцентируйте внимание на верхней части тела!",
    },
    "apple": {
        "good": ["V-вырез", "эмпири линия талии", "прямые брюки", "туники"],
        "avoid": ["облегающая одежда в области талии", "короткие топы"],
        "description": "Создавайте вертикальные линии и открывайте зону декольте!",
    },
    "rectangle": {
        "good": ["пояса", "приталенная одежда", "слои", "текстуры"],
        "avoid": ["прямые мешковатые силуэты"],
        "description": "Создавайте иллюзию талии с помощью аксессуаров!",
    },
    "inverted_triangle": {
        "good": ["A-силуэт", "расклешенные брюки", "темный верх"],
        "avoid": ["объемный верх", "подплечники"],
        "description": "Балансируйте плечи и бедра!",
    },
}

STYLE_CATEGORIES = {
    "casual": ["повседневный", "кэжуал", "прогулка", "отдых"],
    "office": ["офисный", "работа", "деловой", "бизнес"],
    "sport": ["спортивный", "спорт", "тренировка", "активный"],
    "evening": ["вечерний", "мероприятие", "праздник", "свидание"],
    "home": ["домашний", "для дома", "комфорт"],
}

BUDGET_RANGES = {
    "low": (0, 20000),
    "medium": (20000, 40000),
    "high": (40000, 70000),
    "premium": (70000, float("inf")),
}
