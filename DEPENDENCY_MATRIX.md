# Dependency Matrix

## Runtime groups

- `ai-stylist-platform\ai-stylist-platform\requirements.txt`
  - minimal web runtime for the integrated app shell
- `outfit_generator\outfit_generator\requirements.txt`
  - backend and ML/runtime extras
- Additional practical packages discovered during stabilization:
  - `httpx` for local smoke tests with FastAPI `TestClient`
  - `opencv-python` for body analysis and `measure_from_image.py`
  - `beautifulsoup4` for rebuilding the sample catalog used by the live demo
  - CUDA-enabled `torch` / `torchvision` wheels from the PyTorch CU128 index on NVIDIA machines

## Matrix

| Package | Why it is needed | Required for boot | Required for try-on | Required for chat | Required for measurement | Required for search-by-image |
|---|---|---:|---:|---:|---:|---:|
| `fastapi` | app and backend routing | yes | yes | yes | yes | yes |
| `uvicorn` | local ASGI server | yes | yes | yes | yes | yes |
| `jinja2` | template rendering | yes | no | no | no | no |
| `python-multipart` | form/file uploads | yes | yes | yes | yes | yes |
| `python-dotenv` | `.env` loading | no | yes | yes | yes | yes |
| `requests` | Claid client, remote image fetches | no | yes | no | no | no |
| `pillow` | image parsing and conversion | yes | yes | yes | yes | yes |
| `pydantic` | API response models | yes | yes | yes | yes | yes |
| `loguru` | diagnostics/logging | no | yes | yes | yes | yes |
| `numpy<2.0` | shared math dependency for catalog/CLIP/body analysis/measurement | yes for backend import | yes | partially | yes | yes |
| `torch` | CLIP/Qwen model runtime | no | no, try-on can degrade without it | no, chat can fall back heuristically | no | yes |
| `torchvision` | Qwen/vision processor dependency and image model ops | no | no | optional for full Qwen mode | no | optional |
| `transformers>=4.52.4` | Qwen2.5-VL and CLIP model wrappers | no | no, try-on can degrade without it | no, chat can fall back heuristically | no | yes |
| `accelerate` | efficient model loading for Qwen | no | no | optional for full Qwen model mode | no | no |
| `sentencepiece` | tokenizer/runtime support for some transformer models | no | no | optional for full Qwen model mode | no | no |
| `protobuf>=3.20.0` | transformer / MediaPipe compatibility | no | no | optional | yes | optional |
| `openai-clip` | legacy CLIP helper dependency declared by backend | no | no | no | no | optional |
| `mediapipe` | body analysis and measurement models | no | no | no | yes for body analysis / measurement | no |
| `opencv-python` | body analyzer and `measure_from_image.py` image ops | no | no | no | yes | no |
| `faiss-cpu` | vector index for image similarity search | no | no | no | no | yes |
| `scikit-learn` | declared backend data dependency, not on current critical path | no | no | no | no | no |
| `pandas` | declared backend data dependency, not on current critical path | no | no | no | no | no |
| `beautifulsoup4` | scraper support for restoring/rebuilding the demo catalog JSON | no | no | no | no | no |
| `aiohttp` | scraper/network helper, not runtime-critical for integrated app | no | no | no | no | no |
| `httpx` | local smoke tests via `TestClient` | no | no | no | no | no |

## Recommended installation policy

- Required for a stable local boot:
  - `fastapi`
  - `uvicorn`
  - `jinja2`
  - `python-multipart`
  - `python-dotenv`
  - `pillow`
  - `pydantic`
  - `loguru`
  - `requests`
  - `numpy<2.0`
- Recommended for the currently intended maximum real functionality:
  - plus `torch`, `torchvision`, `transformers`, `accelerate`, `sentencepiece`, `protobuf`, `mediapipe`, `opencv-python`
- Optional and isolated:
  - `faiss-cpu`
    - only needed for search-by-image
    - not required for app boot, catalog, auth, try-on route boot, or heuristic chat

## Verified machine state on 2026-03-29

- `nvidia-smi` reports an NVIDIA GPU (`NVIDIA GeForce RTX 5060 Laptop GPU`)
- Active Python runtime now sees CUDA through `torch 2.8.0+cu128`
- CLIP + FAISS image search is working in the integrated app after building the index
- Standalone Qwen loads on GPU successfully
- Integrated chat route still reports `heuristic_fallback`, so full Qwen mode is not yet counted as enabled in the live app

## Safest decision on `faiss`

- `faiss-cpu` is treated as optional.
- The codebase is now isolated so missing `faiss` disables only image-search capability.
- Do not block local boot or core routes on `faiss-cpu`.
