# AI Runtime Enablement Report

Date: 2026-03-29

## Summary

This pass enabled the machine-level CUDA stack, the CLIP runtime, FAISS index persistence, and live image-search in the integrated app. Qwen now loads successfully on GPU in standalone backend initialization, and the live app now reports the exact Qwen load failure instead of hiding it behind a generic fallback. Body analysis and measurement remain blocked for concrete runtime/asset reasons.

## CUDA / PyTorch diagnostics

### Root cause before changes

- The machine has a compatible NVIDIA GPU.
- `nvidia-smi` was healthy.
- The active Python runtime had a CPU-only PyTorch build installed earlier (`torch 2.8.0+cpu`), so `torch.cuda.is_available()` was `False`.

### Current machine state

- GPU: `NVIDIA GeForce RTX 5060 Laptop GPU`
- Driver: `595.79`
- `nvidia-smi` CUDA version: `13.2`
- Active Python: `C:\Users\batyr\AppData\Local\Programs\Python\Python39\python.exe`
- Current PyTorch build: `2.8.0+cu128`
- `torch.cuda.is_available()`: `True`
- `torch.cuda.device_count()`: `1`

## Packages installed in this pass

- `torch==2.8.0+cu128`
- `torchvision==0.23.0+cu128`
- `transformers==4.52.4`
- `accelerate`
- `sentencepiece`
- `protobuf`
- `beautifulsoup4`

Already present and used:

- `faiss-cpu`
- `mediapipe`
- `opencv-python`

## Capability status by feature

| Capability | Status | Evidence |
|---|---|---|
| Qwen runtime import | working | backend imports `torch` and `transformers` successfully |
| Qwen standalone model load | working | `QwenStylistChatbot()` loads on `device='cuda'` with `model_loaded=true` |
| Integrated chat route | degraded | `/api/v1/stylist/query` still returns `Generated ... using heuristic fallback mode` |
| CLIP runtime | working | live search route and standalone index builder both load CLIP |
| FAISS runtime | working | `faiss-cpu` installed and index loads from disk |
| Search-by-image | working | `/api/v1/stylist/search-by-image` returned `200` with `similar_products` |
| Body analysis | blocked | installed `mediapipe` wheel does not expose `mediapipe.solutions` |
| Measurement inference | blocked | required pose/segmentation asset files are still missing |

## Qwen status

### What now works

Standalone backend initialization:

- imports `torch` and `transformers`
- selects `cuda`
- loads `Qwen/Qwen2.5-VL-3B-Instruct`
- falls back from bitsandbytes quantization to fp16 CUDA loading when `bitsandbytes` is not installed

### What still does not work

Fresh live reload servers still fall back on this machine during real route initialization.

The live app reports:

- `route_notes.chat_mode = heuristic_fallback`
- backend chat capability `model_loaded = false`
- backend chat capability `device = "cuda"`
- backend chat capability `load_error = "The paging file is too small for this operation to complete. (os error 1455)"`

and the live route response still says:

- `Generated 3 outfits using heuristic fallback mode`

### Exact blocker that remains

The blocker is now explicit and reproducible:

- Windows virtual memory / paging-file exhaustion during Qwen model initialization in the live integrated runtime
- exact error: `The paging file is too small for this operation to complete. (os error 1455)`

This is no longer a CUDA or import problem. It is a machine-level memory/virtual-memory constraint affecting the live server process.

### Live-runtime hardening added

- the backend now records `load_error` and `device` in Qwen capability status
- if a cached fallback chatbot exists while the runtime is available, the backend now retries live initialization once instead of staying stuck forever on a stale mock instance
- `/api/health` now exposes the real Qwen load error instead of the previous generic message

### What no-reload testing proved

A single integrated server without `--reload` succeeded:

- `/api/health` before chat init -> `mode = not_initialized`
- `POST /api/v1/stylist/query` -> `200`
- `/api/health` after chat init -> `mode = full`
- `device = cuda`
- `model_loaded = true`
- `load_error = null`

This makes `--reload` a real contributor on this machine because it increases live-process duplication and memory pressure.

## CLIP / FAISS image search

### What changed

- CLIP runtime dependencies are installed
- FAISS index persistence/loading was added
- the default FAISS/index storage path was moved to an ASCII-safe local appdata directory to avoid Windows path issues with non-ASCII workspace paths

Current index paths:

- `C:\Users\batyr\AppData\Local\AIStylistData\data\faiss_index.index`
- `C:\Users\batyr\AppData\Local\AIStylistData\data\faiss_index_ids.json`

### Build workflow

```powershell
python scripts\build_image_search_index.py
```

### Live status

- `/api/v1/stylist/search-by-image` returned `200`
- `/api/health` reports image search as available

## Body analysis

### Current blocker

The installed `mediapipe` package on this machine does not expose `mediapipe.solutions`, while the current body-analysis code depends on the legacy solutions API.

### Result

- `/api/v1/stylist/analyze-body` returns `503`
- blocker is explicit and stable

## Measurement inference

### What changed

- downloaded the local MediaPipe task assets expected by `measure_from_image.py`
- enabled asset auto-discovery for:
  - `assets\measurement\pose_landmarker_lite.task`
  - `assets\measurement\selfie_multiclass_256x256.tflite`
- switched measurement execution to an ASCII-safe subprocess runtime under:
  - `C:\Users\batyr\AppData\Local\AIStylistData\measurement_runtime`

This subprocess wrapper was needed because calling MediaPipe Tasks directly from the main process under the repo's non-ASCII workspace path caused a hard crash on this Windows machine.

### Result

- `/api/v1/body/measurements` now returns `200`
- `/api/health` reports:
  - `measurement_callable: true`
  - `execution_mode: subprocess_ascii_runtime`
- returned fields include:
  - `measurements`
  - `fit_profile`
  - `fit_ready: true`

### Remaining limitation

- coarse body-type analysis is still blocked because `body_analyzer.py` depends on `mediapipe.solutions`
- measurement now works independently of that blocked legacy body-analysis path

## Operator guidance

### To verify CUDA quickly

```powershell
nvidia-smi
python -c "import torch; print(torch.__version__); print(torch.cuda.is_available()); print(torch.version.cuda); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'no cuda')"
```

### To rebuild image search

```powershell
python scripts\build_image_search_index.py
```

### To verify live integrated health

```powershell
curl http://127.0.0.1:8012/api/health
```

## Truthful current position

- CUDA: enabled
- PyTorch GPU runtime: enabled
- CLIP + FAISS image search: enabled in the integrated app
- Qwen full mode: proven in standalone load and in a clean single-process integrated server without `--reload`
- Qwen reload-backed live mode: still vulnerable to Windows paging-file exhaustion on this machine
- Body analysis: blocked
- Measurement inference: blocked
