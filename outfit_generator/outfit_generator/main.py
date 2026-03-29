"""
Main API for the AI Stylist service.
"""
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
import hashlib
import json
import os
import time
import io
from urllib.parse import urlparse

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import requests
from pydantic import BaseModel, Field
from PIL import Image
from PIL import ImageOps
from loguru import logger

from catalog.database import ProductDatabase, get_vector_search_capability
from utils.claid_client import (
    ClaidClient,
    ClaidQuotaError,
    ClaidResponseError,
    ClaidTimeoutError,
)
from models.qwen_chatbot import (
    QWEN_IMPORT_ERROR,
    QWEN_RUNTIME_AVAILABLE,
    QwenStylistChatbot,
)
from models.clip_search import (
    CLIP_IMPORT_ERROR,
    CLIP_RUNTIME_AVAILABLE,
    ClipFashionSearch,
    get_clip_capability_status,
)
from models.body_analyzer import (
    BODY_ANALYZER_IMPORT_ERROR,
    BODY_ANALYZER_RUNTIME_AVAILABLE,
    BodyTypeAnalyzer,
    get_body_analyzer_capability_status,
)
from models.tryon_prompt import ClaidTryOnPromptBuilder
from outfit.combiner import OutfitCombiner

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
load_dotenv(BASE_DIR / ".env")
CLAID_SAMPLE_MODEL_URL = "https://images.claid.ai/models/ai-fashion-model/d0ad3dafbd1d4fcfac4012ee810e7463.jpg"
CLAID_SAMPLE_CLOTHING_URLS = [
    "https://images.claid.ai/photoshoot-templates/assets/images/f4945a28e9874eaa89fd43313f373040.png",
    "https://images.claid.ai/photoshoot-templates/assets/images/b63641ea19dd4dac8fdc02a6195873f0.jpeg",
]
CLAID_UPLOAD_CACHE_TTL_SECONDS = 6 * 60 * 60
CLAID_RESULT_CACHE_TTL_SECONDS = 15 * 60
CLAID_POLLS_TIMEOUT_SECONDS = 90
CLAID_POLLS_INTERVAL_SECONDS = 2.0

_claid_client: Optional[ClaidClient] = None
_claid_upload_cache: Dict[str, Dict[str, Any]] = {}
_claid_result_cache: Dict[str, Dict[str, Any]] = {}


class StyleQuery(BaseModel):
    query: str
    budget: Optional[int] = None
    sizes: Optional[List[str]] = None


class OutfitResponse(BaseModel):
    success: bool
    outfits: List[Dict[str, Any]]
    message: str


class BodyAnalysisResponse(BaseModel):
    success: bool
    body_type: str
    recommendations: Dict[str, Any]
    message: str


class SimilarSearchResponse(BaseModel):
    success: bool
    similar_products: List[Dict[str, Any]]
    complementary_items: List[Dict[str, Any]]


class TryOnResponse(BaseModel):
    success: bool
    message: str
    task_id: Optional[int] = None
    result_url: Optional[str] = None
    output_images: List[str] = Field(default_factory=list)
    source: Dict[str, Any] = Field(default_factory=dict)
    clip_analysis: Dict[str, Any] = Field(default_factory=dict)
    claid_prompt: Dict[str, Any] = Field(default_factory=dict)
    fit_analysis: Dict[str, Any] = Field(default_factory=dict)
    fit_warning: Optional[str] = None
    raw_result: Optional[Dict[str, Any]] = None


app = FastAPI(
    title="AI Stylist API",
    description="API for outfit generation and Claid-powered virtual try-on support",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

_product_db: Optional[ProductDatabase] = None
_qwen_chatbot: Optional[QwenStylistChatbot] = None
_clip_search: Optional[ClipFashionSearch] = None
_body_analyzer: Optional[BodyTypeAnalyzer] = None
_outfit_combiner: Optional[OutfitCombiner] = None
_tryon_prompt_builder: Optional[ClaidTryOnPromptBuilder] = None
_capability_errors: Dict[str, str] = {}


def get_product_db() -> ProductDatabase:
    global _product_db
    if _product_db is None:
        try:
            logger.info("Initializing product database")
            _product_db = ProductDatabase()
        except Exception as exc:
            _capability_errors["catalog"] = str(exc)
            raise HTTPException(status_code=503, detail=f"Catalog runtime is unavailable: {exc}") from exc
    return _product_db


def get_qwen_chatbot() -> QwenStylistChatbot:
    global _qwen_chatbot
    if _qwen_chatbot is not None:
        qwen_state = _qwen_chatbot.capability_status()
        if (
            QWEN_RUNTIME_AVAILABLE
            and qwen_state.get("mock_mode")
            and not qwen_state.get("model_loaded")
        ):
            logger.warning(
                "Cached Qwen chatbot is in fallback mode even though runtime is available; retrying live initialization"
            )
            try:
                candidate = QwenStylistChatbot()
                candidate_state = candidate.capability_status()
                if candidate_state.get("model_loaded") and not candidate_state.get("mock_mode"):
                    _qwen_chatbot = candidate
                    _capability_errors.pop("chat", None)
                    logger.info(f"Qwen chatbot recovered successfully on {candidate_state.get('device')}")
                else:
                    load_error = candidate_state.get("load_error") or "Qwen reinitialization still fell back"
                    _capability_errors["chat"] = str(load_error)
                    logger.warning(f"Qwen chatbot retry stayed in fallback mode: {load_error}")
            except Exception as exc:
                _capability_errors["chat"] = str(exc)
                logger.warning(f"Qwen chatbot retry failed: {exc}")
    if _qwen_chatbot is None:
        try:
            logger.info("Initializing Qwen stylist chatbot")
            _qwen_chatbot = QwenStylistChatbot()
            qwen_state = _qwen_chatbot.capability_status()
            if qwen_state.get("model_loaded") and not qwen_state.get("mock_mode"):
                _capability_errors.pop("chat", None)
                logger.info(f"Qwen chatbot initialized successfully on {qwen_state.get('device')}")
            elif qwen_state.get("load_error"):
                _capability_errors["chat"] = str(qwen_state.get("load_error"))
        except Exception as exc:
            _capability_errors["chat"] = str(exc)
            raise HTTPException(status_code=503, detail=f"Stylist chat runtime is unavailable: {exc}") from exc
    return _qwen_chatbot


def get_tryon_prompt_builder() -> ClaidTryOnPromptBuilder:
    global _tryon_prompt_builder
    if _tryon_prompt_builder is None:
        try:
            logger.info("Initializing Claid try-on prompt builder")
            _tryon_prompt_builder = ClaidTryOnPromptBuilder()
        except Exception as exc:
            _capability_errors["tryon_prompt"] = str(exc)
            raise HTTPException(status_code=503, detail=f"Try-on prompt builder is unavailable: {exc}") from exc
    return _tryon_prompt_builder


def get_clip_search() -> ClipFashionSearch:
    global _clip_search
    if _clip_search is None:
        try:
            logger.info("Initializing CLIP search")
            _clip_search = ClipFashionSearch()
        except Exception as exc:
            _capability_errors["clip"] = str(exc)
            raise HTTPException(status_code=503, detail=f"CLIP runtime is unavailable: {exc}") from exc
    return _clip_search


def get_body_analyzer() -> BodyTypeAnalyzer:
    global _body_analyzer
    if _body_analyzer is None:
        try:
            logger.info("Initializing body analyzer")
            _body_analyzer = BodyTypeAnalyzer()
        except Exception as exc:
            _capability_errors["body_analysis"] = str(exc)
            raise HTTPException(status_code=503, detail=f"Body analysis runtime is unavailable: {exc}") from exc
    return _body_analyzer


def get_outfit_combiner() -> OutfitCombiner:
    global _outfit_combiner
    if _outfit_combiner is None:
        try:
            logger.info("Initializing outfit combiner")
            _outfit_combiner = OutfitCombiner()
        except Exception as exc:
            _capability_errors["outfit_combiner"] = str(exc)
            raise HTTPException(status_code=503, detail=f"Outfit combiner is unavailable: {exc}") from exc
    return _outfit_combiner


def get_claid_client() -> ClaidClient:
    global _claid_client
    if _claid_client is None:
        api_key = os.getenv("CLAID_API_KEY", "").strip()
        if not api_key:
            raise HTTPException(
                status_code=503,
                detail="CLAID_API_KEY is not configured on the server",
            )
        _claid_client = ClaidClient(api_key=api_key)
    return _claid_client


def get_runtime_capabilities() -> Dict[str, Any]:
    qwen_status: Dict[str, Any] = {
        "runtime_available": QWEN_RUNTIME_AVAILABLE,
        "import_error": QWEN_IMPORT_ERROR or None,
        "initialized": _qwen_chatbot is not None,
        "mode": "heuristic_fallback" if not QWEN_RUNTIME_AVAILABLE else "not_initialized",
        "blocker": None if QWEN_RUNTIME_AVAILABLE else "Install torch and transformers, then allow the Qwen model to download and load.",
    }
    if _qwen_chatbot is not None:
        qwen_state = _qwen_chatbot.capability_status()
        qwen_status.update(
            {
                "mode": "heuristic_fallback" if qwen_state.get("mock_mode") else "full",
                "model_loaded": qwen_state.get("model_loaded"),
                "device": qwen_state.get("device"),
                "load_error": qwen_state.get("load_error"),
                "blocker": None if qwen_state.get("model_loaded") else (qwen_state.get("load_error") or "Qwen runtime is installed but the model failed to initialize."),
            }
        )

    clip_status: Dict[str, Any] = {
        **get_clip_capability_status(),
        "initialized": _clip_search is not None,
        "blocker": None,
    }
    if _clip_search is not None:
        clip_status.update(_clip_search.capability_status())
    if not clip_status.get("clip_runtime_available"):
        clip_status["blocker"] = "Install torch and transformers so the CLIP model can load."
    elif not clip_status.get("faiss_available"):
        clip_status["blocker"] = "Install faiss-cpu so the image-search index can load."
    elif not clip_status.get("faiss_index_loaded"):
        clip_status["blocker"] = "Build and load the CLIP/FAISS product index before calling image search."

    body_status = {
        **get_body_analyzer_capability_status(),
        "initialized": _body_analyzer is not None,
        "route_available": BODY_ANALYZER_RUNTIME_AVAILABLE,
        "blocker": None if BODY_ANALYZER_RUNTIME_AVAILABLE else "Install a MediaPipe build that exposes mediapipe.solutions, or rewrite this flow to use task-based models.",
    }

    vector_status = get_vector_search_capability()
    return {
        "catalog": {
            "available": True,
            "vector_search": vector_status,
        },
        "chat": qwen_status,
        "clip": clip_status,
        "body_analysis": body_status,
        "claid": {
            "configured": bool(os.getenv("CLAID_API_KEY", "").strip()),
        },
        "errors": dict(_capability_errors),
    }


def _cache_is_valid(entry: Dict[str, Any], ttl_seconds: int) -> bool:
    created_at = entry.get("created_at")
    if not isinstance(created_at, (int, float)):
        return False
    return (time.time() - created_at) < ttl_seconds


def _get_cached_upload(key: str) -> Optional[str]:
    entry = _claid_upload_cache.get(key)
    if not entry or not _cache_is_valid(entry, CLAID_UPLOAD_CACHE_TTL_SECONDS):
        _claid_upload_cache.pop(key, None)
        return None
    return entry.get("tmp_url")


def _set_cached_upload(key: str, tmp_url: str) -> None:
    _claid_upload_cache[key] = {"created_at": time.time(), "tmp_url": tmp_url}


def _get_cached_result(key: str) -> Optional[Dict[str, Any]]:
    entry = _claid_result_cache.get(key)
    if not entry or not _cache_is_valid(entry, CLAID_RESULT_CACHE_TTL_SECONDS):
        _claid_result_cache.pop(key, None)
        return None
    return entry.get("result")


def _set_cached_result(key: str, result: Dict[str, Any]) -> None:
    _claid_result_cache[key] = {"created_at": time.time(), "result": result}


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _normalize_aspect_ratio(raw_value: Optional[str]) -> str:
    allowed = {"1:1", "3:4", "4:5", "2:3", "9:16", "16:9"}
    value = (raw_value or "3:4").strip()
    return value if value in allowed else "3:4"


def _normalize_garment_size(raw_value: Optional[str]) -> Optional[str]:
    if raw_value is None:
        return None
    value = str(raw_value).strip().upper()
    allowed = {"XXXS", "XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL", "ONE SIZE"}
    return value if value in allowed else None


def _parse_json_payload(raw_value: Any, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if raw_value is None:
        return default or {}
    if isinstance(raw_value, dict):
        return raw_value
    if isinstance(raw_value, str):
        text = raw_value.strip()
        if not text:
            return default or {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc
        if isinstance(parsed, dict):
            return parsed
        raise HTTPException(status_code=400, detail="JSON payload must be an object")
    raise HTTPException(status_code=400, detail="JSON payload must be an object or JSON string")


def _normalize_claid_text(raw_value: Optional[str], default: str) -> str:
    value = (raw_value or "").strip()
    return value if value else default


def _prepare_fit_adjusted_image(
    image_bytes: bytes,
    scale: float,
    label: str,
) -> Tuple[bytes, int, int, str]:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image)
        original_mode = image.mode
        rgba = image.convert("RGBA")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read {label}: {exc}") from exc

    scale = float(scale)
    if abs(scale - 1.0) < 0.02:
        return image_bytes, rgba.width, rgba.height, original_mode

    new_width = max(1, int(round(rgba.width * scale)))
    new_height = max(1, int(round(rgba.height * scale)))
    resampling = getattr(Image, "Resampling", Image)
    resized = rgba.resize((new_width, new_height), resampling.LANCZOS)

    background = (255, 255, 255, 0) if "A" in rgba.getbands() else (255, 255, 255, 255)
    canvas = Image.new("RGBA", (rgba.width, rgba.height), background)
    offset_x = (rgba.width - new_width) // 2
    offset_y = (rgba.height - new_height) // 2
    canvas.paste(resized, (offset_x, offset_y), resized)

    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue(), canvas.width, canvas.height, "PNG"


async def _prepare_image_source(
    url_value: Optional[str],
    file_value: Optional[UploadFile],
    required: bool,
    label: str,
) -> Dict[str, Any]:
    if file_value is not None:
        image_bytes = await file_value.read()
        if not image_bytes:
            raise HTTPException(status_code=400, detail=f"{file_value.filename or label} is empty")
        try:
            image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not read {file_value.filename or label}: {exc}") from exc
        return {
            "kind": "file",
            "image": image,
            "bytes": image_bytes,
            "filename": file_value.filename or "image.jpg",
            "content_type": file_value.content_type or "application/octet-stream",
            "source_url": None,
            "width": image.width,
            "height": image.height,
        }

    if url_value:
        source_url = url_value.strip()
        if source_url:
            try:
                response = requests.get(source_url, timeout=15)
                response.raise_for_status()
                image_bytes = response.content
                image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Could not fetch {label} from URL: {exc}") from exc
            guessed_name = Path(urlparse(source_url).path).name or "image.jpg"
            return {
                "kind": "url",
                "image": image,
                "bytes": image_bytes,
                "filename": guessed_name,
                "content_type": response.headers.get("content-type", "application/octet-stream"),
                "source_url": source_url,
                "width": image.width,
                "height": image.height,
            }

    if required:
        raise HTTPException(status_code=400, detail=f"{label} is required")

    return {
        "kind": "missing",
        "image": None,
        "bytes": None,
        "filename": None,
        "content_type": None,
        "source_url": None,
        "width": None,
        "height": None,
    }


def _is_claid_hosted_url(url: Optional[str]) -> bool:
    if not url:
        return False
    host = urlparse(url).netloc.lower()
    return host.endswith("claid.ai") or host.endswith("dl.claid.ai")


def _extract_output_urls(result: Dict[str, Any]) -> List[str]:
    output_urls: List[str] = []
    outputs = result.get("result", {}).get("output_objects", [])
    if isinstance(outputs, list):
        for item in outputs:
            if isinstance(item, dict):
                tmp_url = item.get("tmp_url")
                if tmp_url:
                    output_urls.append(str(tmp_url))
    return output_urls


async def _upload_file_to_claid(file: UploadFile) -> str:
    image_data = await file.read()
    if not image_data:
        raise HTTPException(status_code=400, detail=f"{file.filename or 'image'} is empty")

    file_hash = _sha256_bytes(image_data)
    cached_url = _get_cached_upload(file_hash)
    if cached_url:
        return cached_url

    try:
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        width, height = image.size
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read {file.filename or 'image'}: {exc}") from exc

    client = get_claid_client()
    upload_result = client.upload_image(
        image_bytes=image_data,
        filename=file.filename or "image.jpg",
        content_type=file.content_type or "application/octet-stream",
        width=width,
        height=height,
    )
    tmp_url = upload_result["tmp_url"]
    _set_cached_upload(file_hash, tmp_url)
    return tmp_url


async def _upload_prepared_bytes_to_claid(
    image_bytes: bytes,
    filename: str,
    content_type: str,
    width: int,
    height: int,
    cache_suffix: str,
) -> str:
    file_hash = _sha256_bytes(image_bytes + cache_suffix.encode("utf-8"))
    cached_url = _get_cached_upload(file_hash)
    if cached_url:
        return cached_url

    client = get_claid_client()
    upload_result = client.upload_image(
        image_bytes=image_bytes,
        filename=filename,
        content_type=content_type or "image/png",
        width=width,
        height=height,
    )
    tmp_url = upload_result["tmp_url"]
    _set_cached_upload(file_hash, tmp_url)
    return tmp_url


async def _resolve_image_source(
    url_value: Optional[str],
    file_value: Optional[UploadFile],
    required: bool,
    label: str,
) -> Optional[str]:
    if url_value:
        value = url_value.strip()
        if value:
            return value

    if file_value is not None:
        return await _upload_file_to_claid(file_value)

    if required:
        raise HTTPException(status_code=400, detail=f"{label} is required")
    return None


def _normalize_sizes(raw_sizes: Any) -> Optional[List[str]]:
    if raw_sizes is None:
        return None

    if isinstance(raw_sizes, list):
        sizes: List[str] = []
        for size in raw_sizes:
            for part in str(size).split(","):
                value = part.strip().upper()
                if value:
                    sizes.append(value)
        return sizes or None

    if isinstance(raw_sizes, str):
        parts = [part.strip().upper() for part in raw_sizes.split(",") if part.strip()]
        return parts or None

    value = str(raw_sizes).strip().upper()
    return [value] if value else None


async def _parse_style_request(request: Request) -> Tuple[StyleQuery, Optional[Image.Image]]:
    content_type = request.headers.get("content-type", "")
    query: Optional[str] = None
    budget: Optional[int] = None
    sizes: Optional[List[str]] = None
    image: Optional[Image.Image] = None

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        query = form.get("query")
        raw_budget = form.get("budget")
        raw_sizes = form.getlist("sizes") if hasattr(form, "getlist") else form.get("sizes")
        image_file = form.get("image") or form.get("file")

        if raw_budget not in (None, ""):
            try:
                budget = int(raw_budget)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="budget must be an integer")

        sizes = _normalize_sizes(raw_sizes)

        if hasattr(image_file, "read"):
            image_data = await image_file.read()
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
    else:
        payload = await request.json()
        query = payload.get("query")
        raw_budget = payload.get("budget")
        sizes = _normalize_sizes(payload.get("sizes"))

        if raw_budget is not None:
            try:
                budget = int(raw_budget)
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="budget must be an integer")

    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    return StyleQuery(query=query, budget=budget, sizes=sizes), image


async def _parse_tryon_request(request: Request) -> Dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    model_url: Optional[str] = None
    clothing_url: Optional[str] = None
    pose: Optional[str] = None
    background: Optional[str] = None
    aspect_ratio: Optional[str] = None
    garment_size: Optional[str] = None
    body_measurements: Dict[str, Any] = {}
    model_file: Optional[UploadFile] = None
    clothing_file: Optional[UploadFile] = None

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        model_url = form.get("model_url")
        clothing_url = form.get("clothing_url")
        pose = form.get("pose")
        background = form.get("background")
        aspect_ratio = form.get("aspect_ratio")
        garment_size = form.get("garment_size")
        body_measurements = _parse_json_payload(form.get("body_measurements"), {})
        model_file = form.get("model_file")
        clothing_file = form.get("clothing_file")
    else:
        payload = await request.json()
        model_url = payload.get("model_url")
        clothing_url = payload.get("clothing_url")
        pose = payload.get("pose")
        background = payload.get("background")
        aspect_ratio = payload.get("aspect_ratio")
        garment_size = payload.get("garment_size")
        body_measurements = _parse_json_payload(payload.get("body_measurements"), {})

    return {
        "model_url": model_url,
        "clothing_url": clothing_url,
        "model_file": model_file,
        "clothing_file": clothing_file,
        "pose": _normalize_claid_text(pose, "full body, front view, neutral stance, arms relaxed"),
        "background": _normalize_claid_text(background, "minimalistic studio background"),
        "aspect_ratio": _normalize_aspect_ratio(aspect_ratio),
        "garment_size": _normalize_garment_size(garment_size),
        "body_measurements": body_measurements,
    }


@app.get("/")
async def root():
    index_path = STATIC_DIR / "tryon.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "AI Stylist API ready", "version": "1.0.0"}


@app.get("/try-on", include_in_schema=False)
async def try_on_page():
    index_path = STATIC_DIR / "tryon.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="tryon.html not found")
    return FileResponse(index_path)


@app.post("/api/v1/claid/try-on", response_model=TryOnResponse)
async def claid_try_on(request: Request):
    """
    Proxy a Claid AI Fashion Models request while keeping the API key server-side.
    Accepts either uploaded files or already-hosted image URLs.
    """
    try:
        tryon_request = await _parse_tryon_request(request)
        client = get_claid_client()

        clothing_source = await _prepare_image_source(
            tryon_request.get("clothing_url"),
            tryon_request.get("clothing_file"),
            required=True,
            label="clothing image",
        )
        model_source = await _prepare_image_source(
            tryon_request.get("model_url"),
            tryon_request.get("model_file"),
            required=False,
            label="model image",
        )

        clip_search = get_clip_search()
        tryon_prompt_builder = get_tryon_prompt_builder()

        clip_analysis = clip_search.analyze_garment(clothing_source["image"])
        claid_prompt = tryon_prompt_builder.build_prompt(
            clip_analysis,
            model_context={
                "has_model": model_source["kind"] != "missing",
                "aspect_ratio": tryon_request["aspect_ratio"],
            },
            fit_context={
                "garment_size": tryon_request["garment_size"],
                "body_measurements": tryon_request["body_measurements"],
            },
        )
        fit_analysis = claid_prompt.get("fit_analysis", {})
        fit_scale = float(claid_prompt.get("fit_scale") or 1.0)
        fit_warning = str(claid_prompt.get("fit_warning") or "").strip() or None

        clothing_cache_token = clothing_source["source_url"] or f"upload:{_sha256_bytes(clothing_source['bytes'])}"
        model_cache_token = None
        if model_source["kind"] != "missing":
            model_cache_token = model_source["source_url"] or f"upload:{_sha256_bytes(model_source['bytes'])}"

        body_measurements_hash = None
        if tryon_request["body_measurements"]:
            body_measurements_hash = _sha256_bytes(
                json.dumps(tryon_request["body_measurements"], sort_keys=True, ensure_ascii=False).encode("utf-8")
            )

        cache_key = json.dumps(
            {
                "model_url": model_cache_token,
                "clothing_url": clothing_cache_token,
                "pose": claid_prompt["pose"],
                "background": claid_prompt["background"],
                "aspect_ratio": claid_prompt["aspect_ratio"],
                "garment_size": tryon_request["garment_size"],
                "body_measurements_hash": body_measurements_hash,
                "clip_analysis": clip_analysis,
            },
            sort_keys=True,
            ensure_ascii=False,
        )

        cached_result = _get_cached_result(cache_key)
        if cached_result:
            return TryOnResponse(**cached_result)

        clothing_bytes = clothing_source["bytes"]
        clothing_width = clothing_source["width"]
        clothing_height = clothing_source["height"]
        clothing_filename = clothing_source["filename"]
        clothing_content_type = clothing_source["content_type"]
        if abs(fit_scale - 1.0) >= 0.02:
            adjusted_bytes, adjusted_width, adjusted_height, adjusted_format = _prepare_fit_adjusted_image(
                clothing_bytes,
                fit_scale,
                clothing_filename,
            )
            clothing_bytes = adjusted_bytes
            clothing_width = adjusted_width
            clothing_height = adjusted_height
            clothing_filename = Path(clothing_filename).stem + "_fit_adjusted." + adjusted_format.lower()
            clothing_content_type = "image/png"

        if clothing_source["source_url"] and _is_claid_hosted_url(clothing_source["source_url"]) and abs(fit_scale - 1.0) < 0.02:
            clothing_urls = [clothing_source["source_url"]]
        else:
            clothing_urls = [
                await _upload_prepared_bytes_to_claid(
                    clothing_bytes,
                    clothing_filename,
                    clothing_content_type,
                    clothing_width,
                    clothing_height,
                    cache_suffix=f"{fit_scale:.3f}",
                )
            ]

        model_url = None
        if model_source["kind"] != "missing":
            if model_source["source_url"]:
                if _is_claid_hosted_url(model_source["source_url"]):
                    model_url = model_source["source_url"]
                else:
                    upload_result = client.upload_image(
                        image_bytes=model_source["bytes"],
                        filename=model_source["filename"],
                        content_type=model_source["content_type"],
                        width=model_source["width"],
                        height=model_source["height"],
                    )
                    model_url = upload_result["tmp_url"]
            else:
                upload_result = client.upload_image(
                    image_bytes=model_source["bytes"],
                    filename=model_source["filename"],
                    content_type=model_source["content_type"],
                    width=model_source["width"],
                    height=model_source["height"],
                )
                model_url = upload_result["tmp_url"]

        task = client.create_ai_fashion_model(
            clothing_urls=clothing_urls,
            model_url=model_url,
            pose=claid_prompt["pose"],
            background=claid_prompt["background"],
            aspect_ratio=claid_prompt["aspect_ratio"],
            number_of_images=1,
        )

        result = client.poll_result(
            task["result_url"],
            timeout_seconds=CLAID_POLLS_TIMEOUT_SECONDS,
            interval_seconds=CLAID_POLLS_INTERVAL_SECONDS,
        )

        output_urls = _extract_output_urls(result)
        error_messages: List[str] = []
        raw_errors = result.get("errors", [])
        if isinstance(raw_errors, list):
            for item in raw_errors:
                if isinstance(item, dict):
                    error_text = item.get("error")
                    if error_text:
                        error_messages.append(str(error_text))

        status = result.get("status")
        message = "Claid try-on completed" if status == "DONE" and output_urls else "Claid try-on finished without output images"
        if status == "ERROR" and error_messages:
            message = error_messages[0]

        response_payload = TryOnResponse(
            success=status == "DONE" and bool(output_urls),
            message=message,
            task_id=task["task_id"],
            result_url=task["result_url"],
            output_images=output_urls,
            source={
                "model_url": model_url,
                "clothing_urls": clothing_urls,
                "aspect_ratio": claid_prompt["aspect_ratio"],
                "garment_size": tryon_request["garment_size"],
                "body_measurements_provided": bool(tryon_request["body_measurements"]),
                "fit_scale": fit_scale,
                "clothing_source_kind": clothing_source["kind"],
                "model_source_kind": model_source["kind"],
            },
            clip_analysis=clip_analysis,
            claid_prompt=claid_prompt,
            fit_analysis=fit_analysis,
            fit_warning=fit_warning,
            raw_result=result,
        )
        _set_cached_result(cache_key, response_payload.model_dump())
        return response_payload

    except HTTPException:
        raise
    except (ClaidQuotaError, ClaidTimeoutError, ClaidResponseError) as exc:
        logger.warning(f"claid_try_on failed: {exc}")
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        logger.error(f"claid_try_on unexpected error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/stylist/query", response_model=OutfitResponse)
async def stylist_query(request: Request):
    """
    Analyze a user request and return outfit recommendations.
    Supports JSON requests and multipart requests with an optional image.
    """
    try:
        parsed_request, user_image = await _parse_style_request(request)

        product_db = get_product_db()
        qwen_chatbot = get_qwen_chatbot()
        outfit_combiner = get_outfit_combiner()

        style_intent = qwen_chatbot.analyze_query(
            parsed_request.query,
            user_image=user_image,
            budget=parsed_request.budget,
            sizes=parsed_request.sizes,
        )

        budget_limit = parsed_request.budget if parsed_request.budget is not None else style_intent.get("budget")
        budget_range = (0, budget_limit) if budget_limit is not None else None
        sizes = parsed_request.sizes or style_intent.get("sizes")

        candidates = product_db.search_by_attributes(
            style=style_intent.get("style"),
            colors=style_intent.get("colors"),
            budget=budget_range,
            sizes=sizes,
            category=style_intent.get("category"),
        )

        if not candidates:
            return OutfitResponse(
                success=False,
                outfits=[],
                message="No products matched the requested criteria",
            )

        outfits = qwen_chatbot.generate_outfit_recommendations(style_intent, candidates)

        if not outfits:
            outfits = outfit_combiner.create_outfits(
                candidates,
                style=style_intent.get("style", "casual"),
                max_budget=budget_range[1] if budget_range else None,
                num_outfits=3,
            )

        mode_note = " using heuristic fallback mode" if getattr(qwen_chatbot, "mock_mode", False) else ""
        return OutfitResponse(
            success=True,
            outfits=outfits,
            message=f"Generated {len(outfits)} outfits{mode_note}",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"stylist_query error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/stylist/search-by-image", response_model=SimilarSearchResponse)
async def search_by_image(file: UploadFile = File(...)):
    """
    Search for similar products based on a user photo of a garment.
    """
    try:
        product_db = get_product_db()
        clip_search = get_clip_search()
        clip_status = clip_search.capability_status()

        if not clip_status.get("faiss_available"):
            raise HTTPException(
                status_code=503,
                detail=f"Image search is unavailable because FAISS is not installed: {clip_status.get('faiss_import_error')}",
            )
        if not clip_status.get("clip_model_loaded"):
            raise HTTPException(
                status_code=503,
                detail="Image search is unavailable because the CLIP model runtime could not be loaded",
            )
        if clip_search.faiss_index is None:
            raise HTTPException(
                status_code=503,
                detail="Image search is unavailable because the CLIP/FAISS product index has not been built",
            )

        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data)).convert("RGB")

        similar = clip_search.search_similar(query_image=image, top_k=10)

        if not similar:
            return SimilarSearchResponse(
                success=False,
                similar_products=[],
                complementary_items=[],
            )

        similar_products = []
        for item in similar:
            product = product_db.get_product_by_id(item["product_id"])
            if product:
                product = dict(product)
                product["similarity_score"] = item["similarity_score"]
                similar_products.append(product)

        complementary = []
        if similar_products:
            base_product = similar_products[0]
            complementary = clip_search.find_complementary_items(
                base_product,
                product_db.products,
                base_product.get("outfit_category", "top"),
            )

        return SimilarSearchResponse(
            success=True,
            similar_products=similar_products,
            complementary_items=complementary,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"search_by_image error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/stylist/analyze-body", response_model=BodyAnalysisResponse)
async def analyze_body(file: UploadFile = File(...)):
    """
    Analyze a full-body photo and estimate body type.
    """
    try:
        body_analyzer = get_body_analyzer()

        image_data = await file.read()
        image = Image.open(io.BytesIO(image_data)).convert("RGB")
        result = body_analyzer.analyze_full(image)

        if not result.get("success"):
            return BodyAnalysisResponse(
                success=False,
                body_type=result.get("recommendations", {}).get("body_type", "Unknown"),
                recommendations=result.get("recommendations", {}),
                message=result.get("error", "Could not analyze the image"),
            )

        return BodyAnalysisResponse(
            success=True,
            body_type=result["body_type"],
            recommendations=result,
            message=f"Body type: {result['body_type']}",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"analyze_body error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/v1/catalog/products")
async def get_products(
    category: Optional[str] = None,
    style: Optional[str] = None,
    max_price: Optional[int] = None,
    colors: Optional[str] = None,
    sizes: Optional[str] = None,
    limit: int = 50,
):
    """Return catalog products with optional filters."""
    try:
        product_db = get_product_db()
        color_filters = [item.strip() for item in colors.split(",")] if colors else None
        size_filters = [item.strip().upper() for item in sizes.split(",")] if sizes else None
        products = product_db.search_by_attributes(
            style=style,
            colors=color_filters,
            budget=(0, max_price) if max_price is not None else None,
            sizes=size_filters,
            category=category,
            limit=limit,
        )
        return {"success": True, "products": products, "count": len(products)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"get_products error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
