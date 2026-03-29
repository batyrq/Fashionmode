# Frontend Integration

This folder is the handoff point for a real frontend.

## API Endpoints

### `POST /api/v1/claid/try-on`
Virtual try-on with:
- `clothing_url` or `clothing_file`
- optional `model_url` or `model_file`
- required `garment_size`
- optional `body_measurements` JSON

Returned fields that the UI should display:
- `output_images[0]`
- `fit_warning`
- `fit_analysis.match_state`
- `fit_analysis.fit_note`
- `claid_prompt`
- `clip_analysis`

### `POST /api/v1/stylist/query`
Chatbot/style planning endpoint.

### `POST /api/v1/stylist/analyze-body`
Body analysis endpoint.

## Recommended Frontend Flow

1. Collect model image and clothing image.
2. Collect garment size.
3. Paste or auto-load body measurements JSON.
4. Call `/api/v1/claid/try-on`.
5. Render the image result and surface `fit_warning` if present.

## Key Files

- `src/tryonClient.js`: browser helper for try-on requests
- `samples/body_measurements.sample.json`: example body-analysis payload
- `samples/tryon_request.sample.json`: example request body
- `contracts/tryon_request.schema.json`: request contract
- `contracts/tryon_response.schema.json`: response contract
