$ErrorActionPreference = "Stop"

Write-Host "Installing the stable integrated web runtime..." -ForegroundColor Cyan
python -m pip install -r "ai-stylist-platform\ai-stylist-platform\requirements.txt"
python -m pip install "requests>=2.31.0" "pydantic>=2.5.0" "loguru>=0.7.0" "numpy>=1.26,<2.0" "httpx"

Write-Host "Installing FAISS for optional image-search diagnostics..." -ForegroundColor Cyan
try {
    python -m pip install "faiss-cpu>=1.13.0"
    Write-Host "faiss-cpu installed successfully." -ForegroundColor Green
} catch {
    Write-Warning "faiss-cpu could not be installed. Image search will remain disabled."
}

Write-Host ""
Write-Host "Bootstrap complete for demo-safe local boot." -ForegroundColor Green
Write-Host ""
Write-Host "Optional heavy extras, install only if you need them:" -ForegroundColor Yellow
Write-Host "  CUDA-enabled Qwen / CLIP runtime (recommended on NVIDIA GPU machines):" -ForegroundColor Yellow
Write-Host '    python -m pip install --upgrade --force-reinstall --no-deps --index-url https://download.pytorch.org/whl/cu128 torch torchvision' -ForegroundColor Yellow
Write-Host '    python -m pip install "transformers>=4.52.4,<5.0.0" "accelerate>=0.25.0" "sentencepiece>=0.1.99" "protobuf>=3.20.0"' -ForegroundColor Yellow
Write-Host "  CPU-only fallback Qwen / CLIP runtime:" -ForegroundColor Yellow
Write-Host '    python -m pip install "torch>=2.8.0" "torchvision>=0.23.0" "transformers>=4.52.4,<5.0.0" "accelerate>=0.25.0" "sentencepiece>=0.1.99" "protobuf>=3.20.0"' -ForegroundColor Yellow
Write-Host "  Body-analysis experiment:" -ForegroundColor Yellow
Write-Host '    python -m pip install "mediapipe>=0.10.0" "opencv-python>=4.8.0"' -ForegroundColor Yellow
Write-Host "  Build the CLIP/FAISS image-search index after ML extras are installed:" -ForegroundColor Yellow
Write-Host '    python scripts\build_image_search_index.py' -ForegroundColor Yellow
Write-Host ""
Write-Host "If you need measurement support, set or provide:" -ForegroundColor Yellow
Write-Host "  POSE_MODEL_PATH or MEDIAPIPE_POSE_MODEL_PATH" -ForegroundColor Yellow
Write-Host "  SEG_MODEL_PATH or MEDIAPIPE_SEG_MODEL_PATH" -ForegroundColor Yellow
Write-Host "  or place the assets under assets\\measurement" -ForegroundColor Yellow
