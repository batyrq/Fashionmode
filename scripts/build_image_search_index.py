from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "outfit_generator" / "outfit_generator"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from catalog.database import ProductDatabase
from config import FAISS_IDS_PATH, FAISS_INDEX_PATH
from models.clip_search import ClipFashionSearch


def main() -> int:
    product_db = ProductDatabase()
    clip_search = ClipFashionSearch()
    clip_status = clip_search.capability_status()

    if not clip_status.get("clip_model_loaded"):
        print("CLIP model runtime is not available. Install torch/transformers and verify the model can load first.")
        return 1

    if not clip_status.get("faiss_available"):
        print(f"FAISS is not available: {clip_status.get('faiss_import_error')}")
        return 1

    clip_search.build_index(product_db.products)
    if clip_search.faiss_index is None:
        print("No FAISS index was built. Check that the catalog contains reachable image URLs.")
        return 1

    clip_search.save_index()
    print(f"Saved index: {FAISS_INDEX_PATH}")
    print(f"Saved ids: {FAISS_IDS_PATH}")
    print(f"Indexed products: {len(clip_search.product_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
