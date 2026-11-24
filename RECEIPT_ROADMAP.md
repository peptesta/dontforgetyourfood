# Upload receipt ("Carica scontrino") — status, ideas and roadmap

Document for a Claude session that continues the work on Scadenzario's **"Carica scontrino"** (Upload receipt) feature. Read it in full before touching the code. The project's language (UI, comments, domain names) is Italian; the receipts to read are Spanish (Lidl, Mercadona, Alcampo).

## 1. What it is and how it fits into the app

Scadenzario tracks the expiry dates of pantry products. The existing "Aggiungi foto" (Add photos) flow (`/batch`) photographs the title and expiry date of each package. "Carica scontrino" is a second entry point: you photograph the receipt, the products are read, matched against the catalog, the expiry date is asked only for fresh products, and they are added to the pantry.

The user defined three steps:

1. **Step 1 (DONE, see §3)** — upload the receipt (possibly several photos, because it is long), read only the product names (not the quantities), remove duplicates caused by overlap between photos, apply the matching algorithm against the supermarket catalog.
2. **Step 2 (TO DO, see §5)** — mark which products are fresh and ask for the expiry photo (same mechanism as "Aggiungi foto"), ask for quantities, show a summary highlighting doubtful products.
3. **Step 3 (TO DO, see §6)** — add the products to the pantry.

Decisions already made by the user (do not reopen them without a reason):

- Reading with **local PaddleOCR + line parser**, no LLM/external API.
- Only **food** products stay in the summary; non-food ones are excluded.
- **Duplicate** products on the receipt count as **one single row**: the quantity is not read from the receipt, it is asked of the user in Step 2.
- There is a **list of common fresh products**; in the future a `fresco` (fresh) yes/no column in the catalog will decide who is asked for the expiry photo.
- **Non-fresh** products do not ask for the expiry photo, but the user can type the date by hand in the summary (optional). Consequence: in Step 3 `products.data_scadenza` will have to become **nullable** (Alembic migration + pantry UI handling "no expiry"). Not touched yet.
- In Step 2 the expiry photo is taken with a **dropdown** indicating which product's date is being photographed; the receipt order is only the default, the user can choose the order of the photos (following how they unpack the groceries).
- "Carica scontrino" opens a menu with *Scatta foto* (Take photo, active), *Carica immagine* (Upload image) and *Carica documento* (Upload document) (disabled, "coming soon").

## 2. Git, environment and how to try

- The project **was not a git repo**: I initialized it. `main` contains the previous state (commit `2b51f62`). All the work is on branch **`feature/carica-scontrino`** so that, if it is not liked, one can go back to `main`.
- Backend: FastAPI + SQLAlchemy async + Postgres (docker-compose, host port **5433**, user/password/db `scadenzario`). Venv in `backend/.venv`. Tests: `cd backend && .venv/bin/pytest tests -q` (83 pass).
- Frontend: Vite + React 19 + TypeScript + Tailwind + react-router + TanStack Query. `cd frontend && npx tsc -b` and `npm run lint` (the existing warnings in `useAuthedImageUrl.ts` and `AuthContext.tsx` are not ours).
- To try from a phone: `docker compose up -d`, then `./start_mobile.sh` (see `MOBILE_TESTING.md`).
- The DB was emptied (all accounts deleted at the user's request): you need to register again.
- Test file in the root: `Gemini_Generated_Image_h7wib2h7wib2h7wi.jpeg` — photo of a **real Lidl receipt** (26 product lines, 4 non-food, `CREMAS DE HORTALIZAS` repeated twice, QR codes and back-side text showing through, slightly tilted photo). It is not committed; it should be moved to a fixtures folder (see idea 1.4).

### How to reproduce the tests on the image
The scripts I used live in the session scratchpad and are not in the repo. To redo them (from `backend/`, with `.venv/bin/python`):

```python
from app.services.ocr.engine import OcrEngine
from app.services.ocr.pipeline import run_receipt_pipeline
from app.services.receipt.parser import parse_receipt_photo
from app.services.receipt.merge import merge_photos
from app.services.receipt.matching import match_catalog, is_reliable
from app.services.receipt.foods import is_non_food

eng = OcrEngine()
lines = run_receipt_pipeline(eng, open(path, "rb").read())   # raw OCR lines
parsed = parse_receipt_photo(lines, foto=0)                   # product lines
merged = merge_photos([parsed])                               # several photos: merge_photos([p0, p1, ...])
food = [l for l in merged.lines if not is_non_food(l.nome)]
for l in food: print(l.nome, l.prezzo, l.occorrenze, match_catalog(l.nome)[0])
```

To test the overlap: crop the same image into two overlapping pieces (I used `img.crop((280, 380, 1560, 1500))` and `img.crop((280, 1300, 1560, 2250))` on the 1792×2390 image) and pass the two lists to `merge_photos`. Expected result: same list as the whole photo, no "seam without overlap".

Notes: the first run loads the PaddleOCR models (a few seconds). Very small synthetic images (text < ~40px tall) make the OCR lose lines: for synthetic tests use large fonts and images ≥ 1000px.

## 3. What exists today (Step 1)

### Frontend
- `frontend/src/pages/PantryListPage.tsx` — two fixed buttons side by side: "+ Aggiungi foto" and "🧾 Carica scontrino" (the latter opens `ReceiptSourceSheet`).
- `frontend/src/components/ReceiptSourceSheet.tsx` — bottom sheet with the 3 sources.
- `frontend/src/pages/ReceiptFlowPage.tsx` (route `/receipt` in `App.tsx`) — Capture → Result orchestrator. **The next steps will hook in here.**
- `frontend/src/pages/ReceiptCapturePage.tsx` — multi-photo camera: **vertical** guide frame (the product column, with the giant box-shadow darkening the rest), crop to the column, thumbnails with ✕, "Fine (n)" button. After the first shot it shows, semi-transparent at the top, the **bottom strip of the last photo** to help the user repeat the last 2-3 lines (guarantees the overlap). Shots stay in local memory until "Fine".
- `frontend/src/pages/ReceiptResultPage.tsx` — list of lines read: name, price, catalog match with score, badges "da verificare" (to verify) / "fresco" (fresh) / "N righe sullo scontrino" (N lines on the receipt), warnings (seams without overlap, photos without lines, photos with errors), note about ignored non-food items. **Read-only** except "discard line".
- `frontend/src/api/receipts.ts` — `parseReceipt(files)`; assigns each line a stable client-side `id` (`<timestamp>-<order>`) so that Step 2 refers to lines by id and not by position.
- `frontend/src/lib/cameraCrop.ts` — `guideToVideoRect`, extracted from `UploadPage.tsx` (which now imports it). Reuses the existing `useCameraStream`.

### Backend
**Stateless** endpoint `POST /receipts/parse` (multipart `files`, max 12 photos, in shooting order): it stores neither photos nor lines, no DB migration. Router `backend/app/routers/receipts.py`, schemas `backend/app/schemas/receipt.py`.

Pipeline for each photo (`backend/app/services/ocr/pipeline.py: run_receipt_pipeline`):
1. `preprocess_image(mode="scontrino")` (`preprocess.py`): CLAHE 2.0, long side max 2000px.
2. `OcrEngine.run(..., det_params=...)` with **lower** detector thresholds (`text_det_thresh=0.2`, `text_det_box_thresh=0.4`) only for receipts: with the defaults the detector skipped whole lines (verified).
3. `_drop_faint_boxes`: discards boxes with low **ink/paper contrast** (5th vs 95th percentile of the box pixels on the grayscale *without CLAHE*, `receipt_gray()`), threshold `max(25, 0.4 × median contrast of the photo)`. Real text has contrast 145-199, back-side show-through text and QR codes 4-16. The idea is the user's: products are printed in black, anything light grey is noise.
4. `_recheck_weak_boxes`: boxes with confidence < 0.6 and no digits (max 8 per photo, most doubtful first) are **cropped and re-read on their own**; the result is accepted only if confidence is ≥ 0.8. Recovers lines that fail in the whole photo (e.g. `KIWI VERDE CESTA` read as `IE EE RR` at 0.38 because a QR code was behind it; re-read alone 1.0).

Then, outside the OCR worker (`backend/app/services/receipt/`):
- `parser.py: parse_receipt_photo` — groups boxes into lines after **deskewing** (median angle of the top side of the boxes, `_estimate_skew`): without it, in a tilted photo the price on the right ends up on the wrong line (bug found: `JAMON SERRANO 2,25` instead of 2,75). Discards low-confidence non-price fragments, boxes mostly lowercase after a first uppercase box (`_drop_lowercase_ghosts`), duplicate prices in the same line (`_keep_best_price_box`: typical "2,09 D" fragment of the line above cut off by the edge). For each line: splits off the price on the right (with trailing VAT letter), strips leading quantity, article codes (`-0500229`), `EUR`; discards header, total, VAT, payment, quantity/weight lines, negative discounts, barcodes, dates. Handles the Mercadona weighed product (name on one line, price on the detail line). **Keeps** a line with a name but no price read (`prezzo=None`, to verify) after the first product with a price; discards as header the lines without a price before the first product (photo 0 only). From the `TOTAL` line on it is footer. Fallback: if a photo has no price at all (user framed only the names) every line with text is a product.
- `merge.py: merge_photos` — removes the overlap between consecutive photos: looks for **contact points (anchors)** between the tail of photo k and the head of k+1 (greedy monotonic chain, similar name + equal price; it does **not** require contiguous lines because the OCR skips or misreads lines exactly in the shared area). A single contact is valid only if both lines have a price; otherwise two are needed; the first contact must be within the first 3 lines of the next photo. Handles the **line cut by the edge** (`DATE DE. CERDO` = `PATE DE CERDO`, no price, replaced by the complete version). If there is no overlap it records the seam (`giunture_senza_sovrapposizione`). At the end `_collapse_repeated` merges products with almost identical names (`token_sort_ratio ≥ 92`, **name only, not price**) into a single line with `occorrenze` = how many lines there were.
- `foods.py` — `is_non_food(nome)` (whole words, accent-free, from `backend/app/data/non_food_es.json`, ~144 entries) and `load_fresh_products()` (from `backend/app/data/fresh_products_es.json`, ~320 generic names by category, all with `fresco: true, generico: true`).
- `matching.py: match_catalog(nome, k=3)` — expands receipt abbreviations (`backend/app/data/receipt_abbreviations.json`: `LCHE`→leche, `ENT`→entera…), compares against **supermarket catalog + fresh list**. Scoring: `token_sort_ratio` on the name only (weight 1.0) and on "brand name" (weight 0.95); **containment** (all words of the line are in the catalog name and cover at least half of it: `PAN TOSTADO` ⊂ `Pan tostado classic`, but not `BANANA` ⊂ "yogurt avena, fragola e banana"); **reverse containment only for generic entries** (`KIWI` in `KIWI VERDE CESTA`); on equal score the generic entry wins. "Reliable" threshold = 80 (`MATCH_SCORE_THRESHOLD` in `product_catalog.py`). Returns up to 3 `CatalogMatch` (label, brand, name, score, `fresco`).
- `backend/app/services/ocr/product_catalog.py` — `load_catalog_products()` (catalog from `backend/app/data/product_catalog_es.json`: 3008 **branded** products from Open Food Facts for Lidl/Mercadona/Alcampo, `_complete: false`, no `fresco` field).

Endpoint response (`ReceiptParseResponse`): `righe[]` (`ordine, nome, prezzo, confidence, foto, occorrenze, match, candidati, incerto`), `giunture_senza_sovrapposizione[]`, `foto_senza_righe[]`, `foto_con_errore[]`, `non_alimentari_scartati[]`.

### Verified result on the Lidl image
The whole photo **and** two overlapping photos give the same result: 21 food lines with correct prices, 4 non-food discarded (`ARNES PERRO`, `PAPEL HIGIENICO`, `PIJAMA MUJER`, `GEL DE BAÑO`), `CREMAS DE HORTALIZAS` merged (×2), all reliably matched. This is the **only** receipt everything was tuned on.

### Lessons learned (read them, they will save you hours)
- **Show-through text from the back and QR codes** are the main enemy on thin paper. Filters on text/confidence/lowercase are not enough (some ghosts have confidence 0.9); the **ink contrast** filter is decisive. Measure on the grayscale **before CLAHE**, because CLAHE makes the ghost dark too.
- **Tilted photo ⇒ prices shifted by half a line**: grouping by y without deskewing assigns the price to the wrong line *silently*, which is worse than losing the line.
- **rapidfuzz's `WRatio` is unsuitable** for short names against long labels (it contains a partial comparison): `BANANA`, `KIWI` came out "reliable" on wrong products. Use `token_sort_ratio` + containment with a coverage threshold.
- **The PaddleOCR detector with default thresholds skips whole lines** in receipts; lowering the thresholds recovers lines but introduces spurious fragments at the edges: hence the downstream filters (duplicate prices, contrast, second read).
- **Alignment between photos**: demanding a contiguous overlap fails at the first OCR error in the shared area. Tolerant anchors are needed.
- **Never lose a line silently**: a line with a name but no price is kept (`prezzo=None`); an overlap-only line is removed only with evidence (similar name + equal price).
- On very small images the OCR loses lines; synthetic tests must use large text.
- The **unit tests** of parser/merge/matching use "fake" OCR (lists of boxes with coordinates): see `backend/tests/test_receipt_*.py`, `test_receipt_ink.py`, `test_receipt_foods.py`. The "tilted photo" case is in `test_receipt_parser.py`.

### Known and unresolved
- `JUDIAS VERDES` (fresh or jarred?), `SALMON AL NATURAL` (almost always canned; I removed it from the fresh list), `PECHUGA DE POLLO` (cooked Realvalle vs fresh): the `fresco` flag by name is ambiguous, it must be **correctable by the user**.
- Noise residue inside a name: `CHORIZO IBERICO EXT.IpSS-` (a fragment in the same box); it does not prevent matching.
- `LANGOSTINO COCIDO` could end up on "Langostino crudo" (85%) with the catalog alone: there is now the generic entry "langostino cocido" (100). The cooked/raw risk remains for other products.
- Processing time per photo **has not been measured**; the second read of weak boxes increases it. Measure it with 6-10 photos before thinking about the waiting UX.
- Step 1 only works with **Spanish** receipts (discard words, abbreviations, non-food). Some Italian words are already in the discard lists (TOTALE, CONTANTI, RESTO…), but it is untested.

## 4. Ideas to further improve Step 1

Ordered by value. The first four had been proposed to the user as "to do now"; the user asked to write everything here and **has not yet chosen which to implement**: ask them first.

1. **Reconciliation with the total.** We have the prices and we read the `TOTAL` line (today it is discarded as footer: its amount must be read before stopping). Sum the prices of *all* lines (including discarded non-food and lines without a name) and compare with the total: if 3.09 € is missing we know a line was not read and how much it is worth. It must be exposed in `ReceiptParseResponse` (e.g. `totale_letto`, `somma_righe`, `differenza`). Careful: discounts (`Desc. 0,50`, negative lines) must be subtracted; weighed products have the price on the main line. Linked to 1b.
   - 1b. **Unread line**: when there is a price without a name (unreadable name box) or the reconciliation fails, show "riga non letta (3,09 €)" (unread line) that the user can complete by hand. Today a line with only the price is ignored.
2. **OCR preview per photo, like `previewDatePhoto`.** After each shot send the photo to an endpoint like `POST /receipts/photo-preview` (model: `backend/app/routers/ocr.py` + `frontend/src/api/ocr.ts`) and show "14 products read, linked to the previous photo" or "no line in common, retake the photo higher up". Incremental merging is needed (also send the last lines of the previous photo, or keep them client-side). Avoids discovering at the end of the receipt that a seam was missed.
3. **Corrections in the final screen** (read-only today): choose among the 3 catalog candidates, edit the name, add a missing line, toggle the `fresco` flag, readmit a product excluded as non-food (and vice versa). As important as the reading, because `fresco` and `non-food` rely on word lists and are occasionally wrong.
4. **Evaluation set (golden set).** Tuned on a single receipt ⇒ overfitting risk. Create `backend/tests/fixtures/receipts/` with 5-10 real receipts (Mercadona, Alcampo, Lidl, Carrefour…) + JSON of the expected output (name, price), and `backend/scripts/eval_receipts.py` that runs the pipeline and prints recall/precision of lines and prices. Real photos from the user are needed; **do not commit receipts with personal data** (card, name) — crop or redact. Also include crooked, blurry, shadowed photos, and long receipts in 2-3 photos.
5. **Learned aliases** (big gain over time): table `receipt_aliases` (normalized receipt text → product/label, per supermarket/family), fed by the corrections of idea 3 and consulted **before** the fuzzy match. Requires an Alembic migration.
6. **Recognize store and date from the header** (first photo): the store (LIDL, MERCADONA, ALCAMPO…) chooses line format (Mercadona has the quantity on the left; Lidl has VAT letters on the right), abbreviations and catalog; the **receipt date** helps estimate expiry dates (purchase date + typical shelf life) and, with store and total, recognize an **already uploaded receipt**. Add the fields to the response.
7. **Saved draft**: Step 2 will be long (dozens of expiry photos); closing the app halfway must not lose everything. Save the receipt state (lines, flags, photos taken) server-side (new tables, similar to `batches`/`batch_items` in `backend/app/db/models/batch.py`) or in the browser (IndexedDB for the photos). To be decided before Step 2.
8. **Real-time photo quality**: sharpness (variance of the Laplacian on the crop), too dark, excessive tilt, with a warning and shot blocking; torch with `track.applyConstraints({advanced:[{torch:true}]})` where supported; hint "lay the receipt on a flat surface" (thermal paper curls).
9. **Server-side perspective correction**: recognize the 4 edges of the receipt (OpenCV) and correct the perspective before the OCR. Rotation-only deskewing already exists (only on box coordinates); perspective fixes photos taken from a steep side angle.
10. **Upload image / Upload document**: from the gallery (same `parseReceipt` with several files) and **PDFs of digital receipts** (Mercadona, Lidl Plus): the PDF has selectable text ⇒ no OCR, near-perfect reading (extract lines with coordinates using PyMuPDF/pdfplumber and reuse `parser.py` and `merge.py`). Probably the most accurate way to upload a receipt. The entries are already in `ReceiptSourceSheet`, disabled.
11. **Multilingual**: Italian receipts (the user is Italian, lives in Spain): Italian discard words, non-food, abbreviations and catalog; `TZ=Europe/Madrid` in the env.
12. **Discounts, returns and weighed products**: associate `Desc.`/negative lines with the line above (today they are discarded), recognize returns, and for weighed products use weight and price per kg as extra information.
13. **Performance**: measure time per photo; if needed, SSE with per-photo progress (pattern already in `batches` with `useBatchStream` / `sse-starlette`), limit the second read to the really relevant boxes, or downscale the image.
14. **Richer catalog and fresh list**: the fresh list (`fresh_products_es.json`) is handwritten and must be extended with what appears in real receipts (especially per-supermarket abbreviations: `LONCHAS VACA TIERNO` is a Lidl entry I had to add by hand). A job that, for uncertain lines, reports the most frequent unmatched names to the team.

## 5. Step 2 — implementation ideas

Goal: after reading, mark which products are fresh, ask for the expiry photos, ask for the quantities and show a **summary** highlighting doubts (`ReviewPage` style).

- **`fresco` column in the catalog.** Each entry of `product_catalog_es.json` may have `fresco: true | false | null` (`null` = unknown ⇒ fall back to keywords / fresh list). Populate it in `backend/scripts/fetch_product_catalog.py` from the Open Food Facts categories (meats, fresh dairy, fruit and vegetables, fish, chilled ready meals…). The matching code already propagates `fresco` in `CatalogMatch`. User corrections override (and feed the aliases, idea 4.5).
- **Per-line flag.** The default comes from `match.fresco` (fresh list/catalog); the user corrects it in the summary. For uncertain lines without a match: keywords on the name (insalata, carne, pollo, pesce, succo…).
- **Quantity.** In Step 2 the quantity is asked for each product. `occorrenze` (how many receipt lines were that product) is a good **suggested initial value**. Possible optimization: if the quantity is N > 1 and the product is fresh, choose whether a photo is needed for each unit (different dates) or just one.
- **Expiry photos with dropdown.** Reuse `CameraCaptureGrid`, `useCameraStream` and the flow of `UploadPage.tsx` (today a title+date pair; here the **date alone** is enough, we already know the title from the receipt). A `<select>` at the top indicates the current product, with a tick on the done ones and a count of those missing; it advances to the next product not yet photographed, but the user can choose the order. For the date OCR reuse `previewDatePhoto` (`POST /ocr/date-preview`) and `run_date_pipeline` (`backend/app/services/ocr/pipeline.py`, `date_extractor.py`).
- **Non-fresh products:** no photo; optional date field in the summary (manual typing).
- **Summary.** List of all products with: name (editable, catalog candidates), quantity, fresh flag, date (read or missing), "da verificare" badge for doubts (uncertain match, low-confidence date, fresh product without a date). Reuse the style and components of `frontend/src/pages/ReviewPage.tsx` and `ExpiryBadge`.
- **State to keep** in the frontend (or saved as a draft, idea 4.7): receipt lines with stable `id`, flags, quantities, photos/dates per line.

## 6. Step 3 — implementation ideas

- **Alembic migration**: `products.data_scadenza` → nullable (and the indexes/queries that use it: `idx_products_household_scadenza`, `backend/app/services/scheduler.py` and `notifier.py` for the 3/1-day notifications must ignore products without a date). Update `schemas/product.py`, `PantryListPage`/`ExpiryBadge` ("no expiry").
- **Confirmation endpoint** similar to `POST /batches/{id}/confirm` (`backend/app/routers/batches.py`) but for receipt lines: creates a `Product` for each line (or N if quantity N with different expiry dates; or a `quantita` field on `Product` if you want a single row with a quantity — a product decision to take with the user). Save the product/date photo with `backend/app/services/image_storage.py` (date photos are used for the thumbnail as today's `foto_titolo_key`; for the receipt there is no title photo: consider a generic thumbnail or none).
- **Duplicates with the pantry**: warn about possible duplicates of products already present (same name within N days, or already uploaded receipt: store+date+total, idea 4.6).
- **Expiry estimate for non-fresh products** (optional, postponed by the user): typical shelf life by category (pasta 12 months, canned goods 24…), editable — for now the user chose *not* to estimate it but to leave optional manual entry.
- **Cleanup**: receipt photos must not be kept (privacy: they contain card, time, store). If they are ever saved, crop only the product column.

## 7. Open questions for the user

- Which ideas from §4 to include? (My proposal: 1, 3 and 4 together, because reconciliation is far more useful if the user can then fix the missing line; 2 if a more guided shot is wanted.)
- More real receipts for the golden set (Mercadona, Alcampo, Carrefour, Dia, Italian receipts)?
- Quantity N > 1 of a fresh product: one expiry photo per unit or just one? And in the pantry: N rows or one row with a quantity?
- Receipt draft: server-side or in the browser?
- Should the `fresco` flag decide only "ask for the date photo" or also something else (e.g. earlier notifications)?
