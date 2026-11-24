# PROJECT_REPORT — Scadenzario

Report generated read-only from the code, config files and `git log` (working tree state as of 2026-11-17, branch `feature/carica-scontrino`). Where a datum cannot be verified it says "not determinable".

## 1. Identity

- **Name**: Scadenzario (name used in the code, in `RECEIPT_ROADMAP.md`, in the email sender and in the `scadenzario` DB).
- **Purpose**: mobile-first web app to track the expiry dates of pantry products. The user photographs the title and expiry date of each package (or the grocery receipt). A local OCR reads the data and the app sends an email alert when a product is about to expire (1 and 3 days before).
- **Audience**: people who do grocery shopping and want to avoid wasting expired food. From the code and the roadmap the typical user is Italian and lives in Spain: Italian UI, Spanish receipts (Lidl, Mercadona, Alcampo), `TZ=Europe/Madrid`.

## 2. Actual stack

| Area | Technologies (from `requirements.txt`, `package.json`, `Dockerfile`) |
|---|---|
| Backend | Python 3.12, FastAPI 0.115, Uvicorn, SQLAlchemy 2.0 async + asyncpg, Alembic, Pydantic v2 / pydantic-settings |
| Auth | JWT (python-jose) with access + refresh tokens, password hashing with passlib + bcrypt |
| OCR / vision | PaddleOCR 3.7 + PaddlePaddle 3.3 (PP-OCRv5 mobile det + `latin_PP-OCRv5_mobile_rec` models, CPU only), OpenCV (preprocessing, CLAHE), pillow-heif (HEIC photos) |
| Text / matching | rapidfuzz (fuzzy matching), dateparser (expiry dates) |
| Async / jobs | `ProcessPoolExecutor` for the OCR workers, SSE (sse-starlette) for batch progress, APScheduler for the daily expiry check |
| Notifications | Brevo (transactional email API, `https://api.brevo.com/v3/smtp/email`) via httpx + Jinja2 templates |
| Database | PostgreSQL 16 (`postgres:16-alpine` image) |
| Frontend | React 19, TypeScript 6, Vite 8, Tailwind CSS 4, react-router-dom 7, TanStack Query 5, date-fns; lint with oxlint |
| External data | Product catalog from Open Food Facts (ODbL license), downloaded by `backend/scripts/fetch_product_catalog.py` |
| Build/deploy | Docker (`backend/Dockerfile`) + `docker-compose.yml` (db + backend); frontend with Vite dev server over HTTPS (mkcert certificates) |
| Tests | pytest (backend). Frontend tests: not determinable (none found) |

## 3. Architecture

A React SPA calls the FastAPI REST API (in dev, Vite proxies to `localhost:8000`). The backend stores users, products and batches in Postgres. Images go to a pool of worker processes that keep the OCR model loaded in memory. An `AsyncIOScheduler` checks expiry dates and sends emails.

Main flows:
- **Add photos (batch)**: upload title + date photos → `POST /batches` (202) → background OCR workers → progress via SSE (`/batches/{id}/stream`) → review → `POST /batches/{id}/confirm` creates the products.
- **Upload receipt**: several photos of the product column → `POST /receipts/parse` (stateless, stores nothing) → OCR → line parser → merge of overlapping photos → catalog matching.

```
scadenzario/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, routers, lifespan/scheduler
│   │   ├── api/deps.py        # dependencies (current user, session)
│   │   ├── core/              # config (settings) and security (JWT, hash)
│   │   ├── db/                # async session + SQLAlchemy models
│   │   ├── routers/           # auth, products, batches, ocr, notifications, receipts
│   │   ├── schemas/           # Pydantic models
│   │   ├── services/
│   │   │   ├── ocr/           # engine, preprocess, pipeline, date/name extractor, catalog
│   │   │   ├── receipt/       # parser, merge, matching, foods
│   │   │   ├── batch_processor.py, image_storage.py, notifier.py, scheduler.py
│   │   ├── workers/pool.py    # OCR process pool
│   │   └── data/              # Open Food Facts catalog, fresh, non-food, abbreviations (JSON)
│   ├── alembic/versions/      # 4 migrations
│   ├── scripts/               # debug_ocr.py, fetch_product_catalog.py
│   └── tests/                 # 10 test files
├── frontend/src/
│   ├── pages/                 # 11 pages
│   ├── components/            # CameraCaptureGrid, ExpiryBadge, ReceiptSourceSheet
│   ├── hooks/, api/, context/, lib/
├── docker-compose.yml
├── start_mobile.sh, MOBILE_TESTING.md
└── RECEIPT_ROADMAP.md
```

## 4. Implemented features

- Registration, login, token refresh, logout, `/auth/me` — `backend/app/routers/auth.py`, `frontend/src/pages/LoginPage.tsx`, `RegisterPage.tsx`, `context/AuthContext.tsx`.
- Pantry: product list, edit, "consumed", delete, title photo — `backend/app/routers/products.py`, `frontend/src/pages/PantryListPage.tsx`.
- Colored expiry badge — `frontend/src/components/ExpiryBadge.tsx`.
- Adding products from photos (title + date) with batch OCR and real-time progress (SSE) — `routers/batches.py`, `services/batch_processor.py`, `frontend/src/pages/UploadPage.tsx`, `ProcessingPage.tsx`, `ReviewPage.tsx`, `hooks/useBatchStream.ts`.
- OCR date preview right after taking the photo — `routers/ocr.py` (`/ocr/date-preview`), `frontend/src/api/ocr.ts`.
- In-browser camera with guide frame and cropping — `hooks/useCameraStream.ts`, `components/CameraCaptureGrid.tsx`, `lib/cameraCrop.ts`.
- Extraction of expiry date and product name from OCR — `services/ocr/date_extractor.py`, `name_extractor.py`.
- Matching the read name against the supermarket catalog — `services/ocr/product_catalog.py`.
- Upload receipt (roadmap Step 1): multi-photo, line reading, overlap deduplication, non-food exclusion, catalog matching, "to verify" flagging — `routers/receipts.py`, `services/receipt/*`, `frontend/src/pages/ReceiptCapturePage.tsx`, `ReceiptResultPage.tsx`, `ReceiptFlowPage.tsx`, `components/ReceiptSourceSheet.tsx`.
- Expiry email notifications (1 and 3 days), idempotent through the `notificato_1gg/3gg` flags — `services/scheduler.py`, `services/notifier.py`, `routers/notifications.py` (`/notifications/check`).
- Saving product photos to disk — `services/image_storage.py`.
- Phone testing over LAN with HTTPS — `start_mobile.sh`, `MOBILE_TESTING.md`.

Not implemented (declared in `RECEIPT_ROADMAP.md`): Steps 2 and 3 of "Upload receipt" (quantities, expiry photos, adding to the pantry), "Upload image"/"Upload document" (disabled entries).

## 5. Technically interesting parts

1. **OCR pipeline for receipts** (`services/ocr/pipeline.py`, `preprocess.py`). Before recognition there is CLAHE with resizing to 2000 px. The detector thresholds are lowered because with PaddleOCR defaults whole lines were skipped. Then comes an ink/paper contrast filter (5th/95th percentiles on the grays *before* CLAHE) that removes show-through text from the back and QR codes. Finally, boxes with confidence < 0.6 are cropped and re-read on their own, and the result is accepted only if ≥ 0.8.
2. **Line parser with deskewing** (`services/receipt/parser.py`). It estimates the skew from the median of the box sides and rotates the coordinates before grouping into lines. Without this, the price silently landed on the wrong line (bug documented in the roadmap). It handles VAT letters, article codes, Mercadona-style weighed products and lines without a price, which it keeps instead of discarding.
3. **Merging overlapping photos** (`services/receipt/merge.py`). It looks for "contact points" between the tail of one photo and the head of the next (similar name + equal price, greedy monotonic chain). It doesn't require contiguous lines, because the OCR makes mistakes precisely in the shared area. It recognizes lines cut by the edge and flags seams without overlap. Then it merges true duplicates by counting `occorrenze`.
4. **Catalog matching** (`services/receipt/matching.py`). It uses `token_sort_ratio` plus a containment criterion with a coverage threshold, because `WRatio` gave false positives on short names (BANANA, KIWI). It expands receipt abbreviations. It searches a brand catalog + a list of generic fresh products.
5. **Async processing and operational robustness** (`workers/pool.py`, `routers/batches.py`, `services/scheduler.py`). Each worker loads the OCR model only once. Batches start with 202 and report progress via SSE. Notifications use `<=` thresholds and per-row flags, so they are idempotent even if the job skips a day. The `Dockerfile` pre-downloads the OCR weights at build time and disables oneDNN because of a paddlepaddle crash on CPU (commented in the code).

## 6. Verifiable numbers

Source: `git ls-files` + `wc -l` (cloc not installed; counts include blank lines and comments).

| Item | Value |
|---|---|
| Python (tracked files) | 4,424 lines |
| TypeScript `.ts` / `.tsx` | 599 / 1,423 lines |
| CSS / HTML | 17 / 13 lines |
| JSON (mostly catalog) | 14,351 lines |
| HTTP endpoints | 17 routes (auth 5, products 5, batches 4, ocr 1, notifications 1, receipts 1) + `/health` mentioned in `MOBILE_TESTING.md` (not counted) |
| DB tables (models) | 6: `households`, `users`, `batches`, `batch_items`, `refresh_tokens`, `products` |
| Alembic migrations | 4 |
| Tests | 91 pytest tests in 10 files, all passing (`pytest tests -q`: 91 passed) |
| Frontend pages / components | 11 pages, 3 components |
| Product catalog | 3,021 products (Open Food Facts, Spain, `_stores: 4`, `_complete: false`) |
| Non-food list | 144 keywords |
| Fresh list | 10 categories (number of entries not verified; the roadmap says ~320) |
| Receipt abbreviations | 29 |
| OCR model metrics (accuracy etc.) | not determinable: no eval in the repo. The roadmap says everything was tuned on **one single** Lidl receipt (21 food lines read correctly) |

## 7. Timeline

- **First commit**: 2026-10-03 (`2b51f62`, "Stato iniziale prima di Carica scontrino")
- **Last commit**: 2026-10-03 (`a56e937`, RECEIPT_ROADMAP.md)
- **Number of commits**: 5, all on the same day

The repo was initialized in git only on 2026-10-03, so the real prior history is not in the commits. The dates of the oldest files (22-23 September 2026, mtime) show that the project already existed.

Phases seen in the commits:
1. Baseline of the existing app (pantry, OCR batches, auth).
2. "Upload receipt" Step 1: reading, dedup and catalog matching.
3. Deskewing, noise filters, stricter matching, tolerant merge.
4. Ink filter, re-reading of weak boxes, food only, fresh products, merged duplicates.
5. Roadmap document.

## 8. Deploy and status

- **Published URL**: not determinable. No production URL, Procfile, CI or workflow in the files. Only local configuration exists: docker-compose (db on host port 5433, backend on 8000) and Vite over HTTPS.
- **Status**: in development, on branch `feature/carica-scontrino`. The working tree has **42 uncommitted entries** (39 modified files; see below).
- **What is missing** (from `RECEIPT_ROADMAP.md`): Steps 2 and 3 of Upload receipt, nullable `products.data_scadenza` (migration not done), manual corrections in the final screen, evaluation golden set, reconciliation with the total, learned aliases, "Upload image"/"Upload document" sources, Italian receipt support. No frontend tests. `JWT_SECRET` in `.env.example` is a placeholder (`change-me-in-production`).

## 9. Your role

A single author in the commits: **Peppetesta**, 5/5 commits (`git shortlog`). No other contributors. The roadmap is written as a handover to a Claude session, so part of the recent work may have been done with AI assistance; the git log does not say.

## 10. Links and assets

- **Remote repository**: no `remote` configured (not determinable).
- **Demo / site**: not determinable.
- **Documentation**: `RECEIPT_ROADMAP.md`, `MOBILE_TESTING.md`, `frontend/README.md`, `backend/scripts/debug_input/README.md`. There is no README in the root.
- **Images**: `backend/scripts/debug_input/IMG_1057.jpeg`, `IMG_1058.jpeg` and `backend/scripts/debug_output/*/*.png` (intermediate OCR outputs; they are tracked, `IMG_1126.jpeg` is not). There are no app screenshots.
- **Untracked**: `Gemini_Generated_Image_h7wib2h7wib2h7wi.jpeg` (photo of the test Lidl receipt, 2.3 MB), `backend/scripts/debug_receipts/`.
- `frontend/public/favicon.svg`, `icons.svg`.

## Doubts (not verified)

- **Households inconsistency**: in the working tree `routers/households.py`, `schemas/household.py`, `api/households.ts` and `SettingsPage.tsx` are deleted (staged `D`), but models, migrations, FKs and `scheduler.py` still use `household_id`. I don't know whether this is an intentional but incomplete removal. The last migration is called "household_settings…". The numbers on endpoints and pages reflect the working tree, not the commits.
- **Commits vs working tree**: the commits do not contain the 39 uncommitted changes, so the line counts and the described features are those of the working tree.
- **Number of endpoints**: counted with grep on the `@router.<verb>` decorators. `/health` and other routes defined directly in `main.py` were not verified.
- **Fresh list entries**: ~320 according to the roadmap, not counted (the JSON is by category).
- **OCR processing times and accuracy**: never measured (the roadmap says so too).
- **Production deploy, domain, hosting**: not determinable.
- **Login/registration page and the real flow of Brevo email sending**: read in the code, not executed. Only `pytest` was run (91 passed).
- **Historical dates**: the 5 commits are all from 2026-10-03, so the real duration of the earlier development cannot be reconstructed.
- **Repo license**: not determinable (no LICENSE file). The catalog derives from Open Food Facts (ODbL), so it carries attribution obligations.
