from __future__ import annotations

import csv
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
CSV_WITH_SOURCE = ROOT / "products_with_source.csv"
CSV_FORM_READY = ROOT / "products_form_ready.csv"
CATALOG_JSON = ROOT / "outfit_generator" / "outfit_generator" / "catalog" / "sample_catalog.json"
STATIC_CATALOG_DIR = ROOT / "ai-stylist-platform" / "ai-stylist-platform" / "static" / "uploads" / "catalog"
REPORT_PATH = ROOT / "CATALOG_BULK_IMPORT_REPORT.md"
SUMMARY_PATH = ROOT / "catalog_bulk_import_summary.json"


CATEGORY_MAP = {
    "outerwear": "outerwear",
    "shoes": "shoes",
    "tops": "tops",
}

OUTFIT_CATEGORY_MAP = {
    "blazer": "outerwear",
    "coat": "outerwear",
    "hoodie": "outerwear",
    "jacket": "outerwear",
    "vest": "outerwear",
    "blouse": "top",
    "t-shirt": "top",
    "tank top": "top",
    "boots": "shoes",
    "heels": "shoes",
}


@dataclass
class MatchResult:
    row: Dict[str, str]
    final_row: Dict[str, str]
    image_path: Path
    strategy: str


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def find_image_dir() -> Path:
    candidates = [p for p in ROOT.iterdir() if p.is_dir() and p.name.startswith("imgi_")]
    if not candidates:
        raise FileNotFoundError("Could not find extracted image folder starting with 'imgi_' in project root")
    if len(candidates) > 1:
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def normalize_text(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value)
    return value.strip("-")


def parse_list(value: str, upper: bool = False) -> List[str]:
    items = []
    for raw in (value or "").split(","):
        token = raw.strip()
        if not token:
            continue
        items.append(token.upper() if upper else token.lower())
    return items


def load_existing_catalog() -> List[Dict]:
    if not CATALOG_JSON.exists():
        return []
    text = CATALOG_JSON.read_text(encoding="utf-8")
    return json.loads(text) if text.strip() else []


def build_image_indexes(image_dir: Path) -> Tuple[Dict[str, Path], Dict[str, List[Path]], Dict[str, Path]]:
    files = [p for p in image_dir.rglob("*") if p.is_file()]
    by_name = {p.name.lower(): p for p in files}
    by_group: Dict[str, List[Path]] = {}
    by_stem = {p.stem.lower(): p for p in files}
    for path in files:
        match = re.search(r"_([0-9a-f]{32})$", path.stem, re.IGNORECASE)
        if match:
            by_group.setdefault(match.group(1).lower(), []).append(path)
    return by_name, by_group, by_stem


def match_rows(
    with_source_rows: List[Dict[str, str]],
    form_ready_rows: List[Dict[str, str]],
    image_dir: Path,
) -> Tuple[List[MatchResult], List[Dict], List[Dict]]:
    by_name, by_group, by_stem = build_image_indexes(image_dir)
    form_by_name = {row["product_name"].strip(): row for row in form_ready_rows}
    matches: List[MatchResult] = []
    unmatched: List[Dict] = []
    ambiguous: List[Dict] = []

    for row in with_source_rows:
        source_image = (row.get("source_image") or "").strip().lower()
        group_id = (row.get("group_id") or "").strip().lower()
        product_name = row.get("product_name") or ""
        final_row = form_by_name.get(product_name.strip(), row)

        image_path: Optional[Path] = None
        strategy = ""

        if source_image and source_image in by_name:
            image_path = by_name[source_image]
            strategy = "exact_source_image"
        elif group_id and len(by_group.get(group_id, [])) == 1:
            image_path = by_group[group_id][0]
            strategy = "group_id"
        elif source_image:
            source_stem = Path(source_image).stem.lower()
            if source_stem in by_stem:
                image_path = by_stem[source_stem]
                strategy = "normalized_basename"

        if image_path is not None:
            matches.append(MatchResult(row=row, final_row=final_row, image_path=image_path, strategy=strategy))
            continue

        group_matches = by_group.get(group_id, [])
        if len(group_matches) > 1:
            ambiguous.append(
                {
                    "product_name": product_name,
                    "group_id": group_id,
                    "source_image": row.get("source_image"),
                    "candidate_images": [p.name for p in group_matches],
                }
            )
        else:
            unmatched.append(
                {
                    "product_name": product_name,
                    "group_id": group_id,
                    "source_image": row.get("source_image"),
                }
            )

    return matches, unmatched, ambiguous


def build_product(match: MatchResult, local_image_url: str) -> Dict:
    source_row = match.row
    final_row = match.final_row
    group_id = (source_row.get("group_id") or "").strip().lower()
    product_name = (final_row.get("product_name") or source_row.get("product_name") or "").strip()
    raw_category = (final_row.get("category") or source_row.get("category") or "").strip()
    raw_outfit_category = (final_row.get("outfit_category") or source_row.get("outfit_category") or "").strip()
    category = CATEGORY_MAP.get(raw_category.lower(), normalize_text(raw_category) or "tops")
    outfit_category = OUTFIT_CATEGORY_MAP.get(raw_outfit_category.lower(), "top")
    product_id = f"bulk-{group_id}" if group_id else f"bulk-{normalize_text(product_name)}"

    style_tags = parse_list(final_row.get("style_tags") or source_row.get("style_tags") or "")
    style_tags.extend(
        [
            f"source-group:{group_id}" if group_id else "",
            f"source-image:{Path(source_row.get('source_image') or '').name.lower()}" if source_row.get("source_image") else "",
            "bulk-import",
        ]
    )
    style_tags = [tag for tag in style_tags if tag]

    return {
        "id": product_id,
        "name": product_name,
        "price": float((final_row.get("price") or source_row.get("price") or "0").strip() or 0),
        "currency": (final_row.get("currency") or source_row.get("currency") or "KZT").strip() or "KZT",
        "url": None,
        "image_url": local_image_url,
        "category": category,
        "outfit_category": outfit_category,
        "colors": parse_list(final_row.get("colors") or source_row.get("colors") or ""),
        "sizes": parse_list(final_row.get("sizes") or source_row.get("sizes") or "", upper=True),
        "description": (final_row.get("short_description") or source_row.get("short_description") or "").strip(),
        "material": None,
        "style_tags": style_tags,
        "in_stock": (final_row.get("in_stock") or source_row.get("in_stock") or "").strip().lower() == "true",
    }


def import_matches(matches: List[MatchResult], existing_catalog: List[Dict]) -> Tuple[List[Dict], int]:
    STATIC_CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    existing_ids = {str(item.get("id")) for item in existing_catalog}
    imported: List[Dict] = []
    duplicates = 0

    for match in matches:
        product_name = (match.final_row.get("product_name") or match.row.get("product_name") or "").strip()
        group_id = (match.row.get("group_id") or "").strip().lower()
        product_id = f"bulk-{group_id}" if group_id else f"bulk-{normalize_text(product_name)}"
        if product_id in existing_ids:
            duplicates += 1
            continue

        destination_name = f"{product_id}{match.image_path.suffix.lower()}"
        destination = STATIC_CATALOG_DIR / destination_name
        shutil.copy2(match.image_path, destination)
        local_image_url = f"/static/uploads/catalog/{destination_name}"
        product = build_product(match, local_image_url)
        existing_catalog.append(product)
        existing_ids.add(product_id)
        imported.append(product)

    CATALOG_JSON.write_text(json.dumps(existing_catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    return imported, duplicates


def write_summary(
    with_source_rows: List[Dict[str, str]],
    image_dir: Path,
    matches: List[MatchResult],
    unmatched: List[Dict],
    ambiguous: List[Dict],
    imported: List[Dict],
    duplicates: int,
) -> Dict:
    total_images = sum(1 for p in image_dir.rglob("*") if p.is_file())
    summary = {
        "total_csv_rows": len(with_source_rows),
        "total_images": total_images,
        "matched_rows": len(matches),
        "imported_rows": len(imported),
        "skipped_rows": len(unmatched) + len(ambiguous) + duplicates,
        "unmatched_items": unmatched + ambiguous,
        "duplicate_items_skipped": duplicates,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def write_report(
    image_dir: Path,
    with_source_rows: List[Dict[str, str]],
    form_ready_rows: List[Dict[str, str]],
    matches: List[MatchResult],
    unmatched: List[Dict],
    ambiguous: List[Dict],
    imported: List[Dict],
    duplicates: int,
) -> None:
    examples = (unmatched + ambiguous)[:5]
    lines = [
        "# Catalog Bulk Import Report",
        "",
        "## Files and folders inspected",
        "",
        f"- `{CSV_WITH_SOURCE.name}`",
        f"- `{CSV_FORM_READY.name}`",
        f"- `{image_dir.name}`",
        f"- `outfit_generator\\outfit_generator\\catalog\\sample_catalog.json`",
        f"- `outfit_generator\\outfit_generator\\catalog\\database.py`",
        f"- `ai-stylist-platform\\ai-stylist-platform\\main.py`",
        "",
        "## Chosen source of truth",
        "",
        f"- Primary CSV: `{CSV_WITH_SOURCE.name}`",
        "- Reason: it contains the final catalog fields plus `group_id` and `source_image`, which make deterministic image matching possible.",
        f"- Secondary CSV: `{CSV_FORM_READY.name}`",
        "- Use: only as a cross-check for display fields by exact `product_name`.",
        "",
        "## Matching strategy used",
        "",
        "1. Exact `source_image` filename match against the extracted image folder.",
        "2. Exact `group_id` match against the image filename hash suffix when filename match is unavailable.",
        "3. Exact normalized basename match as a conservative final fallback.",
        "",
        "No fuzzy matching was used.",
        "",
        "## Counts",
        "",
        f"- rows in `products_with_source.csv`: {len(with_source_rows)}",
        f"- rows in `products_form_ready.csv`: {len(form_ready_rows)}",
        f"- images found: {sum(1 for p in image_dir.rglob('*') if p.is_file())}",
        f"- confident matches: {len(matches)}",
        f"- imported catalog items: {len(imported)}",
        f"- skipped as duplicates: {duplicates}",
        f"- skipped as unmatched/ambiguous: {len(unmatched) + len(ambiguous)}",
        "",
        "## Import behavior",
        "",
        "- Imported items use local copied images only.",
        "- Images were copied into `ai-stylist-platform\\ai-stylist-platform\\static\\uploads\\catalog`.",
        "- Remote image URLs were not used for catalog item creation.",
        "- `outfit_category` values were normalized into the app's active runtime categories (`top`, `outerwear`, `shoes`).",
        "",
        "## Examples of unmatched or skipped rows",
        "",
    ]
    if examples:
        for item in examples:
            lines.append(f"- `{item}`")
    else:
        lines.append("- None. Every CSV row had a confident image match.")
    lines.extend(
        [
            "",
            "## Assumptions made",
            "",
            "- The extracted `imgi_*` directory in project root is the intended image source for this import.",
            "- `products_with_source.csv` is the authoritative mapping file because it includes `source_image` and `group_id`.",
            "- Bulk-imported IDs use the stable pattern `bulk-<group_id>` to keep reruns idempotent.",
            "",
            "## Manual cleanup still needed",
            "",
            "- Review the imported category normalization if you want finer-grained distinctions than `top`, `outerwear`, and `shoes`.",
            "- If you want product source links preserved, add a safe local metadata field in a future pass; this import intentionally avoided remote image dependency.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    with_source_rows = read_csv(CSV_WITH_SOURCE)
    form_ready_rows = read_csv(CSV_FORM_READY)
    image_dir = find_image_dir()
    matches, unmatched, ambiguous = match_rows(with_source_rows, form_ready_rows, image_dir)
    existing_catalog = load_existing_catalog()
    imported, duplicates = import_matches(matches, existing_catalog)
    write_summary(with_source_rows, image_dir, matches, unmatched, ambiguous, imported, duplicates)
    write_report(image_dir, with_source_rows, form_ready_rows, matches, unmatched, ambiguous, imported, duplicates)
    print(
        json.dumps(
            {
                "matched_rows": len(matches),
                "imported_rows": len(imported),
                "duplicate_items_skipped": duplicates,
                "unmatched_rows": len(unmatched),
                "ambiguous_rows": len(ambiguous),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
