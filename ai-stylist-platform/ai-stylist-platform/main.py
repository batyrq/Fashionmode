from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
REPO_ROOT = BASE_DIR.parent.parent
BACKEND_DIR = REPO_ROOT / "outfit_generator" / "outfit_generator"
MEASUREMENT_MODULE_PATH = REPO_ROOT / "measure_from_image.py"
MEASUREMENT_ASSETS_DIR = REPO_ROOT / "assets" / "measurement"
MEASUREMENT_ALT_ASSETS_DIR = REPO_ROOT / "models" / "measurement"
LOCAL_RUNTIME_DIR = Path(os.getenv("LOCALAPPDATA", tempfile.gettempdir())) / "AIStylistData"
MEASUREMENT_RUNTIME_DIR = LOCAL_RUNTIME_DIR / "measurement_runtime"

load_dotenv(BASE_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env", override=False)


def _load_backend_module():
    backend_path = BACKEND_DIR / "main.py"
    if not backend_path.exists():
        raise RuntimeError(f"Backend entrypoint not found: {backend_path}")

    backend_sys_path = str(BACKEND_DIR)
    if backend_sys_path not in sys.path:
        sys.path.insert(0, backend_sys_path)

    spec = importlib.util.spec_from_file_location("integrated_outfit_backend", backend_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load backend module from {backend_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_measurement_module():
    if not MEASUREMENT_MODULE_PATH.exists():
        raise RuntimeError(f"Measurement module not found: {MEASUREMENT_MODULE_PATH}")

    spec = importlib.util.spec_from_file_location("integrated_measurement_module", MEASUREMENT_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load measurement module from {MEASUREMENT_MODULE_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


backend = None
measurement_module = None
backend_import_error = None
measurement_import_error = None
catalog_source_state = "unknown"

app = FastAPI(
    title="AI Stylist Integrated App",
    description="User-facing AI Stylist app wired to the outfit_generator backend and Supabase auth.",
    version="2.0.0",
)

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


class AdminCatalogCreateRequest(BaseModel):
    name: str
    category: str
    outfit_category: str
    price: float = Field(default=0, ge=0)
    currency: str = "KZT"
    image_url: str
    url: Optional[str] = None
    description: Optional[str] = None
    material: Optional[str] = None
    colors: List[str] = Field(default_factory=list)
    sizes: List[str] = Field(default_factory=list)
    style_tags: List[str] = Field(default_factory=list)
    in_stock: bool = True


def _slugify_filename(value: str) -> str:
    slug = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "catalog-item"


def _save_admin_catalog_image(image_file: UploadFile) -> str:
    content_type = str(image_file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Catalog image upload must be an image file")

    suffix = Path(image_file.filename or "upload").suffix.lower()
    allowed_suffixes = {".jpg", ".jpeg", ".png", ".webp"}
    if suffix not in allowed_suffixes:
        raise HTTPException(status_code=400, detail="Supported image formats are .jpg, .jpeg, .png, and .webp")

    upload_dir = STATIC_DIR / "uploads" / "catalog"
    upload_dir.mkdir(parents=True, exist_ok=True)

    stem = _slugify_filename(Path(image_file.filename or "catalog-item").stem)
    filename = f"{stem}-{next(tempfile._get_candidate_names())}{suffix}"
    destination = upload_dir / filename

    with destination.open("wb") as output_file:
        image_file.file.seek(0)
        output_file.write(image_file.file.read())

    return f"/static/uploads/catalog/{filename}"


def _copy_if_needed(source: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists() or source.stat().st_mtime > destination.stat().st_mtime:
        shutil.copy2(source, destination)
    return destination


def _ensure_measurement_runtime_paths(
    source_image: Path,
    pose_model: Path,
    seg_model: Path,
) -> Dict[str, Path]:
    runtime_script = _copy_if_needed(
        MEASUREMENT_MODULE_PATH,
        MEASUREMENT_RUNTIME_DIR / "measure_from_image_runtime.py",
    )
    runtime_pose = _copy_if_needed(pose_model, MEASUREMENT_RUNTIME_DIR / pose_model.name)
    runtime_seg = _copy_if_needed(seg_model, MEASUREMENT_RUNTIME_DIR / seg_model.name)
    runtime_image = _copy_if_needed(source_image, MEASUREMENT_RUNTIME_DIR / source_image.name)
    runtime_overlay = MEASUREMENT_RUNTIME_DIR / f"{source_image.stem}-overlay.jpg"
    return {
        "script": runtime_script,
        "pose_model": runtime_pose,
        "seg_model": runtime_seg,
        "image": runtime_image,
        "overlay": runtime_overlay,
    }


def get_supabase_config() -> Dict[str, str]:
    return {
        "url": os.getenv("SUPABASE_URL", "https://uwvgnalhhkqrxlimaseg.supabase.co"),
        "anonKey": os.getenv(
            "SUPABASE_ANON_KEY",
            os.getenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_ET8sz43OsKvJBjPrv-REtw_uqOf322A"),
        ),
    }


def extract_bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Authorization header must use Bearer token")
    return token.strip()


async def fetch_supabase_user_context(authorization: Optional[str]) -> Dict[str, Any]:
    token = extract_bearer_token(authorization)
    config = get_supabase_config()
    if not config["url"] or not config["anonKey"]:
        raise HTTPException(status_code=503, detail="Supabase auth is not configured on the server")

    headers = {
        "apikey": config["anonKey"],
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        user_response = await client.get(f"{config['url']}/auth/v1/user", headers=headers)
        if user_response.status_code in {401, 403}:
            raise HTTPException(status_code=401, detail="Authenticated Supabase session is required")
        if user_response.status_code >= 400:
            raise HTTPException(status_code=503, detail="Could not verify Supabase session on the server")

        user_payload = user_response.json()
        user_id = user_payload.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Supabase session did not include a user id")

        profile_response = await client.get(
            f"{config['url']}/rest/v1/profiles",
            headers=headers,
            params={
                "select": "id,email,role",
                "id": f"eq.{user_id}",
                "limit": "1",
            },
        )
        if profile_response.status_code in {401, 403}:
            raise HTTPException(status_code=403, detail="Authenticated profile access is required")
        if profile_response.status_code >= 400:
            raise HTTPException(status_code=503, detail="Could not load Supabase profile data on the server")

        profile_rows = profile_response.json()
        profile = profile_rows[0] if isinstance(profile_rows, list) and profile_rows else None
        if not profile:
            raise HTTPException(status_code=403, detail="Authenticated user does not have a profile row yet")

        return {
            "user": user_payload,
            "profile": profile,
            "role": str(profile.get("role") or "user"),
            "is_admin": str(profile.get("role") or "user") == "admin",
        }


async def require_admin_context(authorization: Optional[str]) -> Dict[str, Any]:
    context = await fetch_supabase_user_context(authorization)
    if not context["is_admin"]:
        raise HTTPException(status_code=403, detail="Admin access is required for catalog management")
    return context


def get_catalog_admin_database():
    try:
        backend_module = get_backend()
        if hasattr(backend_module, "get_product_db"):
            return backend_module.get_product_db()
    except HTTPException as exc:
        if exc.status_code != 503:
            raise

    database_path = BACKEND_DIR / "catalog" / "database.py"
    backend_sys_path = str(BACKEND_DIR)
    if backend_sys_path not in sys.path:
        sys.path.insert(0, backend_sys_path)
    spec = importlib.util.spec_from_file_location("integrated_catalog_database", database_path)
    if spec is None or spec.loader is None:
        raise HTTPException(status_code=503, detail="Catalog database module is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.ProductDatabase()


def get_backend():
    global backend, backend_import_error
    if backend is None:
        try:
            backend = _load_backend_module()
        except Exception as exc:
            backend_import_error = str(exc)
            raise HTTPException(
                status_code=503,
                detail=f"AI backend is unavailable in this environment: {exc}",
            ) from exc
    return backend


def get_measurement_module():
    global measurement_module, measurement_import_error
    if measurement_module is None:
        try:
            measurement_module = _load_measurement_module()
        except Exception as exc:
            measurement_import_error = str(exc)
            raise HTTPException(
                status_code=503,
                detail=f"Measurement module is unavailable in this environment: {exc}",
            ) from exc
    return measurement_module


def get_measurement_runtime_status() -> Dict[str, Any]:
    pose_status = resolve_measurement_asset(
        env_keys=("POSE_MODEL_PATH", "MEDIAPIPE_POSE_MODEL_PATH"),
        default_candidates=(
            MEASUREMENT_ASSETS_DIR / "pose_landmarker_lite.task",
            MEASUREMENT_ASSETS_DIR / "pose_landmarker.task",
            MEASUREMENT_ALT_ASSETS_DIR / "pose_landmarker_lite.task",
            MEASUREMENT_ALT_ASSETS_DIR / "pose_landmarker.task",
        ),
    )
    seg_status = resolve_measurement_asset(
        env_keys=("SEG_MODEL_PATH", "MEDIAPIPE_SEG_MODEL_PATH"),
        default_candidates=(
            MEASUREMENT_ASSETS_DIR / "image_segmenter.tflite",
            MEASUREMENT_ASSETS_DIR / "selfie_multiclass_256x256.tflite",
            MEASUREMENT_ALT_ASSETS_DIR / "image_segmenter.tflite",
            MEASUREMENT_ALT_ASSETS_DIR / "selfie_multiclass_256x256.tflite",
        ),
    )
    ready = pose_status["exists"] and seg_status["exists"]
    blocker = None
    if not pose_status["selected_path"]:
        blocker = "Missing pose model configuration. Set POSE_MODEL_PATH or MEDIAPIPE_POSE_MODEL_PATH, or place pose_landmarker_lite.task or pose_landmarker.task under assets/measurement."
    elif not pose_status["exists"]:
        blocker = f"Pose model path does not exist: {pose_status['selected_path']}"
    elif not seg_status["selected_path"]:
        blocker = "Missing segmentation model configuration. Set SEG_MODEL_PATH or MEDIAPIPE_SEG_MODEL_PATH, or place a segmenter model under assets/measurement."
    elif not seg_status["exists"]:
        blocker = f"Segmentation model path does not exist: {seg_status['selected_path']}"
    return {
        "module_file_present": MEASUREMENT_MODULE_PATH.exists(),
        "pose_model_env_present": pose_status["source"] == "env",
        "seg_model_env_present": seg_status["source"] == "env",
        "pose_model_path_exists": pose_status["exists"],
        "seg_model_path_exists": seg_status["exists"],
        "pose_model_path": pose_status["selected_path"],
        "seg_model_path": seg_status["selected_path"],
        "pose_model_source": pose_status["source"],
        "seg_model_source": seg_status["source"],
        "pose_model_checked_paths": pose_status["checked_paths"],
        "seg_model_checked_paths": seg_status["checked_paths"],
        "ready": ready,
        "blocker": blocker,
        "import_error": measurement_import_error,
        "execution_mode": "subprocess_ascii_runtime",
    }


def resolve_measurement_asset(env_keys: tuple[str, ...], default_candidates: tuple[Path, ...]) -> Dict[str, Any]:
    checked_paths = []
    for env_key in env_keys:
        value = os.getenv(env_key)
        if not value:
            continue
        checked_paths.append(value)
        return {
            "source": "env",
            "selected_path": value,
            "exists": Path(value).exists(),
            "checked_paths": checked_paths,
            "env_keys": list(env_keys),
        }

    for candidate in default_candidates:
        candidate_str = str(candidate)
        checked_paths.append(candidate_str)
        if candidate.exists():
            return {
                "source": "default_local_asset",
                "selected_path": candidate_str,
                "exists": True,
                "checked_paths": checked_paths,
                "env_keys": list(env_keys),
            }

    return {
        "source": "missing",
        "selected_path": checked_paths[0] if checked_paths else None,
        "exists": False,
        "checked_paths": checked_paths,
        "env_keys": list(env_keys),
    }


def get_backend_status() -> Dict[str, Any]:
    status: Dict[str, Any] = {
        "entrypoint_exists": (BACKEND_DIR / "main.py").exists(),
        "importable": False,
        "import_error": backend_import_error,
        "capabilities": None,
    }
    try:
        backend_module = get_backend()
        status["importable"] = True
        status["import_error"] = None
        if hasattr(backend_module, "get_runtime_capabilities"):
            status["capabilities"] = backend_module.get_runtime_capabilities()
    except HTTPException as exc:
        status["import_error"] = exc.detail
    except Exception as exc:
        status["import_error"] = str(exc)
    return status


def load_catalog_fallback() -> list[dict[str, Any]]:
    catalog_path = BACKEND_DIR / "catalog" / "sample_catalog.json"
    if not catalog_path.exists():
        return []
    with catalog_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def apply_catalog_contract(product: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(product)
    display_id = normalized.get("id")
    favorite_key = normalized.get("favorite_key") or normalized.get("external_id") or normalized.get("slug") or display_id
    normalized.setdefault("catalog_display_id", display_id)
    normalized.setdefault("favorite_key", favorite_key)
    normalized.setdefault("favorite_product_uuid", normalized.get("product_uuid"))
    return normalized


def apply_catalog_contract_to_list(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [apply_catalog_contract(product) for product in products]


def filter_catalog_fallback(
    products: list[dict[str, Any]],
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    colors: Optional[str] = None,
    sizes: Optional[str] = None,
) -> list[dict[str, Any]]:
    color_filters = [item.strip().lower() for item in (colors or "").split(",") if item.strip()]
    size_filters = [item.strip().upper() for item in (sizes or "").split(",") if item.strip()]
    filtered = []
    for product in products:
        if category and product.get("category") != category and product.get("outfit_category") != category:
            continue
        if max_price is not None and float(product.get("price", 0)) > max_price:
            continue
        if color_filters:
            product_colors = [value.lower() for value in product.get("colors", [])]
            if not any(color in product_colors for color in color_filters):
                continue
        if size_filters:
            product_sizes = [value.upper() for value in product.get("sizes", [])]
            if not any(size in product_sizes for size in size_filters):
                continue
        filtered.append(product)
    return filtered


def render(request: Request, template_name: str, context: Optional[Dict[str, Any]] = None) -> HTMLResponse:
    payload = {"request": request, "supabase_config": get_supabase_config()}
    if context:
        payload.update(context)
    return templates.TemplateResponse(template_name, payload)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return render(request, "index.html")


@app.get("/chat", response_class=HTMLResponse)
async def chat_page(request: Request):
    return render(request, "chat.html")


@app.get("/tryon", response_class=HTMLResponse)
async def tryon_page(request: Request):
    return render(request, "tryon.html")


@app.get("/analysis", response_class=HTMLResponse)
async def analysis_page(request: Request):
    return render(request, "analysis.html")


@app.get("/catalog", response_class=HTMLResponse)
async def catalog_page(request: Request):
    return render(request, "catalog.html")


@app.get("/outfits", response_class=HTMLResponse)
async def outfits_page(request: Request):
    return render(request, "outfits.html")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return render(request, "login.html")


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return render(request, "register.html")


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    return render(request, "profile.html")


@app.get("/api/health")
async def health():
    backend_status = get_backend_status()
    measurement_status = get_measurement_runtime_status()
    supabase_config = get_supabase_config()
    effective_catalog_source = catalog_source_state
    if effective_catalog_source == "unknown":
        effective_catalog_source = "backend" if backend_status.get("importable") else "catalog_json_fallback"
    backend_capabilities = backend_status.get("capabilities") or {}
    clip_capabilities = backend_capabilities.get("clip") or {}
    vector_capabilities = (backend_capabilities.get("catalog") or {}).get("vector_search") or {}
    chat_capabilities = backend_capabilities.get("chat") or {}
    body_capabilities = backend_capabilities.get("body_analysis") or {}
    if not clip_capabilities.get("faiss_available"):
        search_status = "missing_faiss"
    elif not clip_capabilities.get("clip_runtime_available"):
        search_status = "missing_clip_runtime"
    elif not vector_capabilities.get("index_file_exists"):
        search_status = "index_not_built"
    else:
        search_status = "available"

    return {
        "success": True,
        "app": {
            "name": "ai-stylist-platform",
            "bootable": True,
            "primary_entrypoint": str(BASE_DIR / "main.py"),
        },
        "backend": backend_status,
        "config": {
            "supabase": {
                "url_present": bool(supabase_config["url"]),
                "anon_key_present": bool(supabase_config["anonKey"]),
            },
            "claid": {
                "api_key_present": bool(os.getenv("CLAID_API_KEY")),
            },
            "measurement": measurement_status,
        },
        "catalog": {
            "source": effective_catalog_source,
            "fallback_available": (BACKEND_DIR / "catalog" / "sample_catalog.json").exists(),
        },
        "features": {
            "catalog": True,
            "supabase_auth": bool(supabase_config["url"] and supabase_config["anonKey"]),
            "saved_outfits": bool(supabase_config["url"] and supabase_config["anonKey"]),
            "admin_catalog_management": bool(supabase_config["url"] and supabase_config["anonKey"]),
            "chat_route_callable": bool(backend_status["importable"]),
            "tryon_route_callable": bool(backend_status["importable"] and os.getenv("CLAID_API_KEY")),
            "body_analysis_callable": bool(body_capabilities.get("route_available", backend_status["importable"])),
            "measurement_callable": bool(measurement_status["module_file_present"] and measurement_status["ready"]),
            "search_by_image_callable": bool(
                backend_status["importable"]
                and clip_capabilities.get("faiss_available")
                and clip_capabilities.get("clip_runtime_available")
                and vector_capabilities.get("available")
                and vector_capabilities.get("index_file_exists")
            ),
            "favorites_enabled": bool(supabase_config["url"] and supabase_config["anonKey"]),
        },
        "route_notes": {
            "canonical_tryon_route": "/api/v1/claid/try-on",
            "compatibility_tryon_route": "/api/v1/vton/try-on",
            "chat_mode": chat_capabilities.get("mode"),
            "search_by_image_status": search_status,
        },
        "blockers": {
            "chat": chat_capabilities.get("blocker"),
            "body_analysis": body_capabilities.get("blocker"),
            "measurement": measurement_status.get("blocker"),
            "search_by_image": clip_capabilities.get("blocker"),
            "favorites": None,
        },
    }


@app.post("/api/v1/stylist/query")
async def stylist_query(request: Request):
    return await get_backend().stylist_query(request)


@app.post("/api/v1/stylist/analyze-body")
async def stylist_analyze_body(request: Request):
    response = await get_backend().analyze_body(request)
    if isinstance(response, dict):
        response.setdefault("fit_ready", False)
        response.setdefault(
            "measurement_endpoint",
            {
                "path": "/api/v1/body/measurements",
                "requires": ["file", "height_cm"],
            },
        )
    return response


@app.get("/api/v1/catalog/products")
async def catalog_products(
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    colors: Optional[str] = None,
    sizes: Optional[str] = None,
):
    global catalog_source_state
    try:
        result = await get_backend().get_products(
            category=category,
            max_price=max_price,
            colors=colors,
            sizes=sizes,
        )
        result["products"] = apply_catalog_contract_to_list(result.get("products", []))
        catalog_source_state = "backend"
        return result
    except HTTPException as exc:
        if exc.status_code != 503:
            raise
        fallback_products = filter_catalog_fallback(
            load_catalog_fallback(),
            category=category,
            max_price=max_price,
            colors=colors,
            sizes=sizes,
        )
        catalog_source_state = "catalog_json_fallback"
        return {
            "success": True,
            "products": apply_catalog_contract_to_list(fallback_products),
            "source": "catalog_json_fallback",
            "warning": exc.detail,
        }


@app.get("/api/v1/admin/catalog/me")
async def admin_catalog_me(authorization: Optional[str] = Header(default=None)):
    context = await fetch_supabase_user_context(authorization)
    profile = context["profile"]
    return {
        "success": True,
        "is_admin": context["is_admin"],
        "role": context["role"],
        "email": profile.get("email"),
    }


@app.post("/api/v1/admin/catalog/products")
async def admin_create_catalog_product(
    name: str = Form(...),
    category: str = Form(...),
    outfit_category: str = Form(...),
    price: float = Form(...),
    currency: str = Form("KZT"),
    image_file: UploadFile = File(...),
    url: Optional[str] = Form(default=None),
    description: Optional[str] = Form(default=None),
    material: Optional[str] = Form(default=None),
    colors: Optional[str] = Form(default=None),
    sizes: Optional[str] = Form(default=None),
    style_tags: Optional[str] = Form(default=None),
    in_stock: bool = Form(True),
    authorization: Optional[str] = Header(default=None),
):
    await require_admin_context(authorization)
    product_db = get_catalog_admin_database()
    try:
        image_url = _save_admin_catalog_image(image_file)
        created = product_db.add_product(
            {
                "name": name,
                "category": category,
                "outfit_category": outfit_category,
                "price": price,
                "currency": currency,
                "image_url": image_url,
                "url": url,
                "description": description,
                "material": material,
                "colors": [item.strip() for item in str(colors or "").split(",") if item.strip()],
                "sizes": [item.strip().upper() for item in str(sizes or "").split(",") if item.strip()],
                "style_tags": [item.strip().lower() for item in str(style_tags or "").split(",") if item.strip()],
                "in_stock": in_stock,
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "success": True,
        "product": apply_catalog_contract(created),
    }


@app.delete("/api/v1/admin/catalog/products/{product_id}")
async def admin_delete_catalog_product(
    product_id: str,
    authorization: Optional[str] = Header(default=None),
):
    await require_admin_context(authorization)
    product_db = get_catalog_admin_database()
    deleted = product_db.delete_product(product_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Catalog item not found")
    return {
        "success": True,
        "deleted_product_id": product_id,
    }


@app.post("/api/v1/claid/try-on")
async def claid_try_on(request: Request, content_type: Optional[str] = Header(default=None)):
    if not content_type:
        raise HTTPException(
            status_code=400,
            detail="Try-on request must be sent as JSON or multipart/form-data.",
        )
    return await get_backend().claid_try_on(request)


@app.post("/api/v1/vton/try-on")
async def compatibility_try_on(
    user_photo: UploadFile = File(...),
    clothing_photo: Optional[UploadFile] = File(default=None),
    clothing_url: Optional[str] = Form(default=None),
    garment_size: Optional[str] = Form(default=None),
    pose: Optional[str] = Form(default=None),
    background: Optional[str] = Form(default=None),
    aspect_ratio: Optional[str] = Form(default=None),
    body_measurements: Optional[str] = Form(default=None),
):
    model_file = user_photo
    clothing_file = clothing_photo

    if clothing_file is None and not clothing_url:
        raise HTTPException(status_code=400, detail="Either clothing_photo or clothing_url is required")

    form = {
        "model_file": model_file,
        "clothing_file": clothing_file,
        "clothing_url": clothing_url,
        "garment_size": garment_size,
        "pose": pose,
        "background": background,
        "aspect_ratio": aspect_ratio,
        "body_measurements": body_measurements,
    }

    # The real backend request parser reads the incoming Request object, so route legacy clients to the
    # modern endpoint with normalized field names via an in-process subrequest.
    from starlette.datastructures import FormData, Headers, UploadFile as StarletteUploadFile
    from starlette.requests import Request as StarletteRequest

    normalized_items = []
    for key, value in form.items():
        if value is None:
            continue
        if isinstance(value, UploadFile):
            normalized_items.append((key, StarletteUploadFile(value.file, filename=value.filename, headers=value.headers)))
        else:
            normalized_items.append((key, value))

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/claid/try-on",
        "headers": Headers({"content-type": "multipart/form-data"}).raw,
        "query_string": b"",
        "client": ("127.0.0.1", 0),
        "server": ("127.0.0.1", 80),
        "scheme": "http",
        "root_path": "",
        "app": app,
    }

    request = StarletteRequest(scope, receive)
    request._form = FormData(normalized_items)
    return await get_backend().claid_try_on(request)


@app.post("/api/v1/body/measurements")
async def body_measurements(
    file: UploadFile = File(...),
    height_cm: float = Form(...),
):
    measurement_status = get_measurement_runtime_status()
    pose_model_path = measurement_status.get("pose_model_path")
    seg_model_path = measurement_status.get("seg_model_path")

    if not pose_model_path or not seg_model_path:
        raise HTTPException(
            status_code=503,
            detail=(
                "Measurement models are not configured. Set POSE_MODEL_PATH or MEDIAPIPE_POSE_MODEL_PATH, "
                "and SEG_MODEL_PATH or MEDIAPIPE_SEG_MODEL_PATH, or place the assets under assets/measurement."
            ),
        )

    pose_model = Path(pose_model_path)
    seg_model = Path(seg_model_path)
    if not pose_model.exists() or not seg_model.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Measurement model files are missing on disk. Pose path: {pose_model}. "
                f"Segmentation path: {seg_model}. "
                "Check POSE_MODEL_PATH or MEDIAPIPE_POSE_MODEL_PATH, and SEG_MODEL_PATH or MEDIAPIPE_SEG_MODEL_PATH."
            ),
        )

    suffix = Path(file.filename or "upload.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
        tmp_file.write(await file.read())
        tmp_path = Path(tmp_file.name)

    try:
        runtime_paths = _ensure_measurement_runtime_paths(
            source_image=tmp_path,
            pose_model=pose_model,
            seg_model=seg_model,
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(runtime_paths["script"]),
                "--image",
                str(runtime_paths["image"]),
                "--height_cm",
                str(height_cm),
                "--pose_model",
                str(runtime_paths["pose_model"]),
                "--seg_model",
                str(runtime_paths["seg_model"]),
                "--overlay_out",
                str(runtime_paths["overlay"]),
            ],
            cwd=str(MEASUREMENT_RUNTIME_DIR),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if completed.returncode != 0:
            stderr = (completed.stderr or completed.stdout or "").strip()
            raise HTTPException(
                status_code=400,
                detail=f"Measurement failed: {stderr or 'measurement subprocess exited with a non-zero status'}",
            )

        results = json.loads((completed.stdout or "").strip())
    except HTTPException:
        raise
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Measurement timed out while loading local vision models") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Measurement failed: {exc}") from exc
    finally:
        tmp_path.unlink(missing_ok=True)

    fit_profile = {
        "recommended_size": results.get("size_recommendation", {}).get("recommended_size"),
        "confidence": results.get("size_recommendation", {}).get("confidence"),
        "body_measurements": {
            "shoulder_width_cm": results.get("shoulder_width_cm"),
            "chest_width_cm": results.get("chest_front_width_cm"),
            "waist_width_cm": results.get("waist_front_width_cm"),
            "hip_width_cm": results.get("hip_front_width_cm"),
            "torso_length_cm": results.get("torso_length_cm"),
            "sleeve_length_cm": results.get("sleeve_length_cm"),
            "leg_length_cm": results.get("leg_length_cm"),
            "height_cm": results.get("height_input_cm"),
        },
    }

    return {
        "success": True,
        "message": "Measurements calculated successfully.",
        "measurements": results,
        "fit_profile": fit_profile,
        "fit_ready": True,
    }


@app.post("/api/v1/stylist/search-by-image")
async def stylist_search_by_image(file: UploadFile = File(...)):
    try:
        return await get_backend().search_by_image(file=file)
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "detail": exc.detail,
                "status": "unavailable" if exc.status_code == 503 else "error",
            },
        )
