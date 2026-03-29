# Chat Runtime Report

## Current mode

- Active demo-safe default: `heuristic_fallback` in reload-backed live runs on this machine
- Proven full mode: yes, in a single no-reload integrated server
- Main blocker in failing live runs: Windows paging-file pressure during Qwen initialization (`os error 1455`)

## What is installed vs missing

- Installed:
  - integrated FastAPI runtime
  - catalog backend
  - fallback combiner logic
  - `torch 2.8.0+cu128`
  - `torchvision 0.23.0+cu128`
  - `transformers 4.52.4`
  - `accelerate`
  - `sentencepiece`
  - `protobuf`
- Not installed:
  - `bitsandbytes`

## Current behavior

- `POST /api/v1/stylist/query` is real and callable.
- In reload-backed runs on this machine, query parsing falls back when Qwen init fails with paging-file pressure.
- In a clean no-reload run, Qwen initializes on `cuda` and `/api/health` reports `mode = full`.
- Outfit assembly still uses deterministic fallback for larger candidate sets to keep latency bounded after Qwen intent analysis.

## Requirements for full mode

1. Keep the current CUDA-enabled torch stack installed.
2. Ensure the machine can download and load `Qwen/Qwen2.5-VL-3B-Instruct`.
3. Avoid extra live Python server workers when validating Qwen on Windows.
4. Prefer starting the integrated app without `--reload` for full-Qwen validation on this machine.
5. Re-run `/api/health` and confirm:
   - `backend.capabilities.chat.runtime_available = true`
   - `route_notes.chat_mode = full`
   - `backend.capabilities.chat.device = cuda`
   - `backend.capabilities.chat.load_error = null`

## How to switch from fallback to full mode

```powershell
uvicorn main:app --app-dir "ai-stylist-platform\ai-stylist-platform" --port 8012
```

Then check:

```powershell
curl http://127.0.0.1:8012/api/health
```

If the health payload still reports `os error 1455`, increase the Windows paging file and restart Windows before retrying.
