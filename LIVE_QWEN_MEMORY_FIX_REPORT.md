# Live Qwen Memory Fix Report

Date: 2026-03-29

## Exact root cause

The live integrated app was not failing because CUDA was broken. The blocker was Windows virtual-memory pressure during Qwen initialization inside the integrated server process.

Exact failing error:

- `The paging file is too small for this operation to complete. (os error 1455)`

In one no-reload test before clearing old workers, the same root cause also surfaced one level earlier while importing the CUDA stack:

- `Error loading "...torch\\lib\\cublas64_12.dll" or one of its dependencies`

Both symptoms point to the same practical problem on this machine:

- too much live process duplication and not enough effective paging-file headroom during Qwen startup

## Did `--reload` contribute?

Yes.

Evidence:

- fresh reload-backed servers repeatedly fell back with `os error 1455`
- after killing leftover Python server workers and starting one single integrated server without `--reload`, Qwen initialized successfully and `/api/health` reported `mode = full`

Why it contributes:

- `uvicorn --reload` runs a watcher/reloader plus a worker process
- on Windows, extra live processes increase host-memory and virtual-memory pressure
- repeated reload experiments left additional Python workers alive, which made the problem worse

## Is pagefile size the real blocker?

Yes, on this machine.

The code now exposes the real load error through `/api/health`, and fresh reload-backed runs consistently reported the Windows paging-file error rather than missing-package errors.

## Code changes made

### 1. Better Qwen load diagnostics

File:

- `outfit_generator\outfit_generator\models\qwen_chatbot.py`

Changes:

- added `load_error`
- added `device` to capability status
- kept graceful fallback intact

### 2. Stale fallback recovery

File:

- `outfit_generator\outfit_generator\main.py`

Changes:

- if a cached fallback chatbot exists while runtime is available, the backend retries live initialization once
- `/api/health` now reflects the real Qwen load error instead of a generic blocker

### 3. Smaller live outfit-synthesis path

File:

- `outfit_generator\outfit_generator\models\qwen_chatbot.py`

Changes:

- reduced candidate list passed into direct Qwen outfit synthesis
- reduced generation budget
- for larger candidate sets, uses deterministic assembly after Qwen intent analysis to reduce latency

## Validation result

### Reload-backed live runs

- status: `partial / still risky`
- result: fallback remained active
- health after chat init:
  - `mode = heuristic_fallback`
  - `load_error = os error 1455`

### Single-process no-reload live run

- status: `working`
- server command:

```powershell
uvicorn main:app --app-dir "ai-stylist-platform\ai-stylist-platform" --port 8012
```

- result:
  - `/api/health` before chat init -> `mode = not_initialized`
  - `POST /api/v1/stylist/query` -> `200`
  - `/api/health` after chat init -> `mode = full`
  - `device = cuda`
  - `model_loaded = true`
  - `load_error = null`

## Recommended operator path

For full-Qwen validation or demo on this machine:

1. close leftover Python/uvicorn workers
2. use a single-process server without `--reload`
3. verify `/api/health`
4. then run chat

Recommended command:

```powershell
uvicorn main:app --app-dir "ai-stylist-platform\ai-stylist-platform" --port 8012
```

## Windows paging-file steps

If full Qwen still fails in the target machine/session, increase the Windows paging file.

Suggested operator steps:

1. Open `System Properties`
2. Go to `Advanced` -> `Performance` -> `Settings`
3. Open the `Advanced` tab
4. Under `Virtual memory`, click `Change`
5. Disable automatic management only if you need manual control
6. Set a larger paging file on the system drive

Practical recommendation for this model/runtime on a laptop-class 8 GB GPU machine:

- initial size: at least `16384 MB`
- maximum size: `32768 MB` or higher if disk space allows

7. Apply the change
8. Restart Windows
9. Launch only one integrated app server and retest Qwen

## Final result

- Repo/code result: `partial but materially improved`
- Operational result: `working in single-process no-reload mode`
- Remaining caveat: reload-backed live runs can still hit Windows paging-file pressure on this machine
