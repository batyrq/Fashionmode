# Environment Check Report

## Required env vars

| Variable | Required for | If missing |
|---|---|---|
| `CLAID_API_KEY` | real Claid try-on execution | `/api/v1/claid/try-on` and `/api/v1/vton/try-on` return actionable configuration errors |
| `SUPABASE_URL` | frontend auth/session and saved outfits | auth UI and Supabase-backed saves are not correctly configured |
| `SUPABASE_ANON_KEY` or `SUPABASE_PUBLISHABLE_KEY` | frontend auth/session and saved outfits | auth UI and Supabase-backed saves are not correctly configured |

## Optional env vars

| Variable | Used for | If missing |
|---|---|---|
| `HF_TOKEN` | optional Hugging Face access for model downloads | some model downloads may be rate-limited or unavailable |
| `QWEN_QUANTIZATION` | Qwen load mode | Qwen uses default `auto` behavior |
| `POSE_MODEL_PATH` | measurement pose model path | measurement endpoint stays unavailable unless alias is present |
| `MEDIAPIPE_POSE_MODEL_PATH` | alias for measurement pose model path | same as above |
| `SEG_MODEL_PATH` | measurement segmentation model path | measurement endpoint stays unavailable unless alias is present |
| `MEDIAPIPE_SEG_MODEL_PATH` | alias for measurement segmentation model path | same as above |

## Model asset paths

| Path/env | Used by | Missing behavior |
|---|---|---|
| `POSE_MODEL_PATH` or `MEDIAPIPE_POSE_MODEL_PATH` | `measure_from_image.py` adapter | `/api/v1/body/measurements` returns `503` with alias-aware guidance |
| `SEG_MODEL_PATH` or `MEDIAPIPE_SEG_MODEL_PATH` | `measure_from_image.py` adapter | `/api/v1/body/measurements` returns `503` with alias-aware guidance |

## Runtime capability behavior

| Missing thing | Result |
|---|---|
| `faiss-cpu` | search-by-image remains unavailable; app boot, catalog, try-on route boot, and heuristic chat still work |
| `torch` / `transformers` | chat falls back to heuristic catalog-based mode; try-on can still boot and attempt Claid flow with degraded garment analysis |
| `mediapipe` / `opencv-python` | body analysis route returns explicit `503`; app boot is unaffected |
| measurement model files | measurement route returns explicit `503`; app boot is unaffected |

## Health endpoint coverage

`GET /api/health` now reports:

- web app boot status
- backend import status
- backend capability summary
- Supabase config presence
- Claid key presence
- measurement env/path presence
- catalog source in use
- feature-level callability flags
- canonical vs compatibility try-on route notes
