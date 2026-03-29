# Demo Script

## 2-minute demo flow

1. Open `/` and point at the feature cards.
   - Say that the build clearly labels what is ready now versus what still needs local ML setup.
2. Go to `/chat`.
   - Ask for a casual or office outfit under a simple budget like `50000`.
   - Show that the stylist returns real catalog-backed outfits.
3. Save one outfit.
4. Go to `/tryon`.
   - Show the selected item already prepared for try-on.
   - Upload a prepared model photo and run the real Claid flow.
5. Open `/profile` or `/outfits`.
   - Show the saved result.

## 5-minute demo flow

1. Start on `/`.
   - Explain the three main working pieces:
     - catalog
     - stylist chat
     - virtual try-on
2. Open `/catalog`.
   - Pick one or two items and explain that favorites are intentionally disabled until product UUID sync is finished.
3. Open `/chat`.
   - Ask for a budgeted outfit.
   - Mention that the demo build is running in quick fallback mode, but still uses the real catalog and backend contract.
4. Save the best result.
5. Open `/tryon`.
   - Upload the prepared photo.
   - Run try-on and show the resulting image.
   - Mention that fit hints improve further once local measurement assets are installed.
6. Open `/profile`.
   - Show saved outfits and explain that auth + persistence are already real via Supabase.
7. If asked about blocked features:
   - open `/api/health`
   - point to the capability flags and blockers

## Best order of pages

- `/`
- `/catalog`
- `/chat`
- `/tryon`
- `/profile`

## What to avoid clicking live

- Avoid presenting the analysis page as a working ML feature in this build.
- Avoid talking up favorites as if they are almost done in the UI; call them intentionally disabled.
- Avoid promising image-search is one click away unless CLIP runtime and FAISS index are actually prepared beforehand.

## Fallback talking points

- Chat:
  - "The demo build is using a quick fallback stylist mode, but it still works against the real catalog and backend routes."
- Body analysis:
  - "The UI is ready, but this machine is missing the exact local runtime needed for that model path."
- Measurement:
  - "The endpoint is wired; we only need the local pose and segmentation assets on disk."
- Image search:
  - "The route is isolated cleanly, but we have not enabled the CLIP runtime and index for this demo machine."
- Favorites:
  - "We intentionally left favorites off until visible catalog IDs are mapped safely to real product UUIDs in Supabase."

## Sample inputs and assets to prepare

- One clean full-body presenter photo for try-on
- One fallback backup model photo
- One or two product selections already chosen in `/catalog`
- One reliable chat prompt:
  - `Нужен офисный образ до 50000 тенге`
- One reliable fallback chat prompt:
  - `Need a casual outfit under 50000`
