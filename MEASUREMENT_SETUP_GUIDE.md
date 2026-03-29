# Measurement Setup Guide

## Current endpoint

- Route: `POST /api/v1/body/measurements`
- Status: wired and callable
- Current blocker: local model assets are missing

## Supported env vars

- Pose model:
  - `POSE_MODEL_PATH`
  - `MEDIAPIPE_POSE_MODEL_PATH`
- Segmentation model:
  - `SEG_MODEL_PATH`
  - `MEDIAPIPE_SEG_MODEL_PATH`

## Supported default local asset locations

If env vars are not set, the app now checks these paths automatically:

- Pose model:
  - `assets\measurement\pose_landmarker.task`
  - `models\measurement\pose_landmarker.task`
- Segmentation model:
  - `assets\measurement\image_segmenter.tflite`
  - `assets\measurement\selfie_multiclass_256x256.tflite`
  - `models\measurement\image_segmenter.tflite`
  - `models\measurement\selfie_multiclass_256x256.tflite`

## Recommended local setup

1. Create:
   - `assets\measurement\`
2. Place:
   - `pose_landmarker.task`
   - one compatible segmentation model such as `image_segmenter.tflite` or `selfie_multiclass_256x256.tflite`
3. Optionally set env vars explicitly if assets live elsewhere.

## What `/api/health` should show when ready

Under `config.measurement`:

- `module_file_present = true`
- `pose_model_path_exists = true`
- `seg_model_path_exists = true`
- `ready = true`
- `blocker = null`

Under `features`:

- `measurement_callable = true`

## Smoke-test example

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/v1/body/measurements" `
  -F "file=@C:\path\to\full-body-photo.png" `
  -F "height_cm=170"
```

Expected success shape:

- `success = true`
- `measurements`
- `fit_profile`
- `fit_ready = true`

## Current failure mode

If assets are missing, the endpoint now returns a `503` with the exact resolved pose and segmentation paths so the operator can see what the server actually checked.
