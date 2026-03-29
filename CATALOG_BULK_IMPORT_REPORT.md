# Catalog Bulk Import Report

## Files and folders inspected

- `products_with_source.csv`
- `products_form_ready.csv`
- `imgi_16_da9054c1f0723199e15b80e7eb225596 (2)`
- `outfit_generator\outfit_generator\catalog\sample_catalog.json`
- `outfit_generator\outfit_generator\catalog\database.py`
- `ai-stylist-platform\ai-stylist-platform\main.py`

## Chosen source of truth

- Primary CSV: `products_with_source.csv`
- Reason: it contains the final catalog fields plus `group_id` and `source_image`, which make deterministic image matching possible.
- Secondary CSV: `products_form_ready.csv`
- Use: only as a cross-check for display fields by exact `product_name`.

## Matching strategy used

1. Exact `source_image` filename match against the extracted image folder.
2. Exact `group_id` match against the image filename hash suffix when filename match is unavailable.
3. Exact normalized basename match as a conservative final fallback.

No fuzzy matching was used.

## Counts

- rows in `products_with_source.csv`: 23
- rows in `products_form_ready.csv`: 23
- images found: 66
- confident matches: 23
- imported catalog items: 23
- skipped as duplicates: 0
- skipped as unmatched/ambiguous: 0

## Import behavior

- Imported items use local copied images only.
- Images were copied into `ai-stylist-platform\ai-stylist-platform\static\uploads\catalog`.
- Remote image URLs were not used for catalog item creation.
- `outfit_category` values were normalized into the app's active runtime categories (`top`, `outerwear`, `shoes`).

## Examples of unmatched or skipped rows

- None. Every CSV row had a confident image match.

## Assumptions made

- The extracted `imgi_*` directory in project root is the intended image source for this import.
- `products_with_source.csv` is the authoritative mapping file because it includes `source_image` and `group_id`.
- Bulk-imported IDs use the stable pattern `bulk-<group_id>` to keep reruns idempotent.

## Manual cleanup still needed

- Review the imported category normalization if you want finer-grained distinctions than `top`, `outerwear`, and `shoes`.
- If you want product source links preserved, add a safe local metadata field in a future pass; this import intentionally avoided remote image dependency.
