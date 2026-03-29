# Body Analysis Runtime Report

## Status

- Enabled: no
- Route: `POST /api/v1/stylist/analyze-body`
- Current response: explicit `503`

## Packages required

- `mediapipe`
- `opencv-python`
- `numpy`

## What was tested

- `mediapipe` installed successfully.
- `opencv-python` installed successfully.
- Backend capability check still reports body analysis unavailable.

## Exact blocker

The currently installed `mediapipe` wheel on this machine exposes `mediapipe.tasks` but not `mediapipe.solutions`. The current body analyzer depends on the legacy `mediapipe.solutions.pose` API, so the route remains intentionally unavailable.

Health now reports:

- `backend.capabilities.body_analysis.runtime_available = false`
- `backend.capabilities.body_analysis.import_error = Installed mediapipe package does not expose mediapipe.solutions...`

## Input/output contract summary

- Input:
  - multipart file field: `file`
- Intended output:
  - `success`
  - `body_type`
  - `recommendations`
  - `message`
  - integrated wrapper also adds `fit_ready` and measurement endpoint metadata when available

## What would enable it

- Either install a MediaPipe distribution that exposes `mediapipe.solutions`
- Or rewrite the analyzer to use task-based MediaPipe models plus explicit local model assets

## Demo guidance

Keep the route disabled for the demo and rely on:

- explicit `503` messaging
- the measurement button guidance on the analysis page
- `/api/health` blocker visibility
